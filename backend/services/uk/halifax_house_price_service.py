"""
ハリファックス住宅価格指数サービス
DBからHalifax House Priceデータを取得し、PDFから最新データを取得

指標:
- ハリファックス住宅価格指数 前月比（MoM）
- ハリファックス住宅価格指数 前年比（YoY）

データソース:
- DB: economic_calendar_events（CSV蓄積データ）
- CSV: 過去データインポート
- PDF: 手動ダウンロード（backend/data/pdf/uk/YYYYMM-halifax-house-price-index.pdf）

発表スケジュール:
- 月次（毎月上旬、07:00 UK時間）
- スケジュール: 90日ごとに更新確認

キャッシュ方式: 独自更新判定方式（次回発表日ベース + PDF読み取り）
"""
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "halifax_house_price_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "halifax_schedule_cache.json"
IMPORTED_PDF_FILE = CACHE_DIR / "halifax_imported_pdfs.json"

# PDFディレクトリ
PDF_DIR = Path(__file__).parent.parent.parent / "data" / "pdf" / "uk"


class HalifaxHousePriceService:
    """ハリファックス住宅価格指数サービス"""

    DATA_CACHE_KEY = "uk:halifax_house_price:data"
    SCHEDULE_CACHE_KEY = "uk:halifax_house_price:schedule"

    # スケジュール更新間隔（日）
    SCHEDULE_REFRESH_DAYS = 90

    def __init__(self):
        pass

    def get_halifax_house_price_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ハリファックス住宅価格指数データを取得"""
        # 未処理PDFがあればキャッシュを無視して強制更新
        if not force_refresh and self._check_new_pdfs():
            logger.info("[Halifax] New PDF detected, forcing refresh")
            force_refresh = True

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "mom": cached_data.get("mom", []),
                        "yoy": cached_data.get("yoy", []),
                        "latest_mom": cached_data.get("latest_mom"),
                        "latest_yoy": cached_data.get("latest_yoy"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # DBから取得（DB失敗時はファイルキャッシュから復元）
        mom_data = self._load_mom_from_db()
        yoy_data = self._load_yoy_from_db()
        if not mom_data and not yoy_data:
            file_cache = self._load_file_cache()
            if file_cache:
                mom_data = file_cache.get("mom", [])
                yoy_data = file_cache.get("yoy", [])
                logger.info(f"[Halifax] DB empty, restored {len(mom_data)} MoM + {len(yoy_data)} YoY from file cache")

        # 未処理のPDFがあれば自動でDBにインポート
        new_pdfs = self._check_new_pdfs()
        for pdf_path in new_pdfs:
            pdf_data = self._extract_data_from_pdf(pdf_path)
            if pdf_data:
                self._save_pdf_data_to_db(pdf_data)
                self._mark_pdf_as_imported(pdf_path)
                # メモリ上でもマージ（最新月）
                mom_data = self._merge_pdf_data(mom_data, pdf_data.get("mom"))
                yoy_data = self._merge_pdf_data(yoy_data, pdf_data.get("yoy"))
                # 修正値を反映（前回分の修正）
                for rev in pdf_data.get("revisions", []):
                    mom_data = self._merge_pdf_data(mom_data, {"date": rev["date"], "value": rev["mom"]})
                    yoy_data = self._merge_pdf_data(yoy_data, {"date": rev["date"], "value": rev["yoy"]})
                logger.info(f"[Halifax] Auto-imported new PDF: {pdf_path.name}")

        if mom_data or yoy_data:
            next_release = self._get_next_release()
            latest_mom = mom_data[-1] if mom_data else None
            latest_yoy = yoy_data[-1] if yoy_data else None

            cache_payload = {
                "mom": mom_data,
                "yoy": yoy_data,
                "latest_mom": latest_mom,
                "latest_yoy": latest_yoy,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "mom": mom_data,
                "yoy": yoy_data,
                "latest_mom": latest_mom,
                "latest_yoy": latest_yoy,
                "next_release": next_release,
                "cached": False,
                "source": "database + pdf",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "mom": file_cache.get("mom", []),
                "yoy": file_cache.get("yoy", []),
                "latest_mom": file_cache.get("latest_mom"),
                "latest_yoy": file_cache.get("latest_yoy"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "mom": [],
            "yoy": [],
            "latest_mom": None,
            "latest_yoy": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _load_mom_from_db(self) -> List[Dict[str, Any]]:
        """DBから前月比データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'UK'
                      AND event ILIKE '%Halifax House Price Index MoM%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                result = []
                seen_dates = set()

                for row in rows:
                    dt_utc, actual, estimate, previous = row
                    if dt_utc:
                        date_str = dt_utc.strftime("%Y-%m-01")
                        if date_str in seen_dates:
                            continue
                        seen_dates.add(date_str)

                        result.append({
                            "date": date_str,
                            "value": float(actual) if actual else None,
                            "forecast": float(estimate) if estimate else None,
                            "previous": float(previous) if previous else None,
                        })

                logger.info(f"[Halifax House Price] Loaded {len(result)} MoM records from DB")
                return result

        except Exception as e:
            logger.error(f"[Halifax House Price] Error loading MoM from DB: {e}")
            return []

    def _load_yoy_from_db(self) -> List[Dict[str, Any]]:
        """DBから前年比データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'UK'
                      AND event ILIKE '%Halifax House Price Index YoY%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                result = []
                seen_dates = set()

                for row in rows:
                    dt_utc, actual, estimate, previous = row
                    if dt_utc:
                        date_str = dt_utc.strftime("%Y-%m-01")
                        if date_str in seen_dates:
                            continue
                        seen_dates.add(date_str)

                        result.append({
                            "date": date_str,
                            "value": float(actual) if actual else None,
                            "forecast": float(estimate) if estimate else None,
                            "previous": float(previous) if previous else None,
                        })

                logger.info(f"[Halifax House Price] Loaded {len(result)} YoY records from DB")
                return result

        except Exception as e:
            logger.error(f"[Halifax House Price] Error loading YoY from DB: {e}")
            return []

    def _load_latest_from_pdf(self) -> Optional[Dict[str, Any]]:
        """
        手動ダウンロードしたPDFから最新データを取得

        PDFファイル名形式: YYYYMM-halifax-house-price-index.pdf
        例: 202512-halifax-house-price-index.pdf

        PDFの1ページ目から以下を抽出:
        - Monthly change: -0.6%
        - Annual change: +0.3%
        """
        try:
            if not PDF_DIR.exists():
                logger.warning(f"PDF directory not found: {PDF_DIR}")
                return None

            # 最新のPDFファイルを探す
            pdf_files = list(PDF_DIR.glob("*halifax*.pdf"))
            if not pdf_files:
                logger.info("No Halifax PDF files found")
                return None

            # ファイル名でソートして最新を取得
            pdf_files.sort(reverse=True)
            latest_pdf = pdf_files[0]
            logger.info(f"Found Halifax PDF: {latest_pdf.name}")

            # ファイル名から対象月を抽出
            # 対応形式: YYYYMMDD(8桁), YYYYMM(6桁)
            match = re.search(r'(\d{8}|\d{6})', latest_pdf.name)
            if not match:
                logger.warning(f"Could not extract date from PDF filename: {latest_pdf.name}")
                return None

            date_str = match.group(1)
            year = int(date_str[:4])
            month = int(date_str[4:6])
            data_date = f"{year}-{month:02d}-01"

            # PDFからテキストを抽出
            try:
                import pdfplumber
            except ImportError:
                logger.warning("pdfplumber not installed, cannot read PDF")
                return None

            mom_value = None
            yoy_value = None

            with pdfplumber.open(latest_pdf) as pdf:
                if len(pdf.pages) > 0:
                    # 1ページ目を読む
                    page = pdf.pages[0]
                    text = page.extract_text()

                    if text:
                        # Monthly change を探す
                        mom_patterns = [
                            r'Monthly\s*change[:\s]*([+-]?\d+\.?\d*)\s*%',
                            r'monthly\s*%?\s*change[:\s]*([+-]?\d+\.?\d*)\s*%',
                            r'([+-]?\d+\.?\d*)\s*%\s*Monthly\s*change',
                        ]
                        for pattern in mom_patterns:
                            match = re.search(pattern, text, re.IGNORECASE)
                            if match:
                                mom_value = float(match.group(1))
                                logger.info(f"Found Halifax MoM from PDF: {mom_value}%")
                                break

                        # Annual change を探す
                        yoy_patterns = [
                            r'Annual\s*change[:\s]*([+-]?\d+\.?\d*)\s*%',
                            r'annual\s*%?\s*change[:\s]*([+-]?\d+\.?\d*)\s*%',
                            r'([+-]?\d+\.?\d*)\s*%\s*Annual\s*change',
                        ]
                        for pattern in yoy_patterns:
                            match = re.search(pattern, text, re.IGNORECASE)
                            if match:
                                yoy_value = float(match.group(1))
                                logger.info(f"Found Halifax YoY from PDF: {yoy_value}%")
                                break

            if mom_value is None and yoy_value is None:
                logger.warning("Could not extract values from Halifax PDF")
                return None

            result = {}
            if mom_value is not None:
                result["mom"] = {"date": data_date, "value": mom_value}
            if yoy_value is not None:
                result["yoy"] = {"date": data_date, "value": yoy_value}

            logger.info(f"Extracted Halifax data from PDF: {result}")
            return result

        except Exception as e:
            logger.error(f"Error loading Halifax data from PDF: {e}")
            return None

    def _check_new_pdfs(self) -> List[Path]:
        """
        未処理のPDFファイルをチェック

        Returns:
            未処理のPDFファイルパスのリスト
        """
        if not PDF_DIR.exists():
            return []

        # 処理済みPDFリストを読み込み
        imported_pdfs = self._load_imported_pdfs()

        # Halifax PDFファイルを検索
        pdf_files = list(PDF_DIR.glob("*halifax*.pdf"))
        new_pdfs = []

        for pdf_path in pdf_files:
            # ファイル名とサイズでユニーク識別
            pdf_key = f"{pdf_path.name}:{pdf_path.stat().st_size}"
            if pdf_key not in imported_pdfs:
                new_pdfs.append(pdf_path)

        if new_pdfs:
            logger.info(f"[Halifax] Found {len(new_pdfs)} new PDF(s) to import")

        return new_pdfs

    def _extract_data_from_pdf(self, pdf_path: Path) -> Optional[Dict[str, Any]]:
        """
        指定されたPDFファイルからデータを抽出

        Args:
            pdf_path: PDFファイルパス

        Returns:
            抽出されたデータ {"mom": {...}, "yoy": {...}}
        """
        try:
            # ファイル名から対象月を抽出
            # 対応形式: YYYYMMDD(8桁), YYYYMM(6桁)
            match = re.search(r'(\d{8}|\d{6})', pdf_path.name)
            if not match:
                logger.warning(f"Could not extract date from PDF filename: {pdf_path.name}")
                return None

            date_str = match.group(1)
            year = int(date_str[:4])
            month = int(date_str[4:6])
            data_date = f"{year}-{month:02d}-01"

            try:
                import pdfplumber
            except ImportError:
                logger.warning("pdfplumber not installed, cannot read PDF")
                return None

            mom_value = None
            yoy_value = None

            with pdfplumber.open(pdf_path) as pdf:
                if len(pdf.pages) > 0:
                    page = pdf.pages[0]
                    text = page.extract_text()

                    if text:
                        # Monthly change を探す
                        mom_patterns = [
                            r'Monthly\s*change[:\s]*([+-]?\d+\.?\d*)\s*%',
                            r'monthly\s*%?\s*change[:\s]*([+-]?\d+\.?\d*)\s*%',
                            r'([+-]?\d+\.?\d*)\s*%\s*Monthly\s*change',
                        ]
                        for pattern in mom_patterns:
                            m = re.search(pattern, text, re.IGNORECASE)
                            if m:
                                mom_value = float(m.group(1))
                                break

                        # Annual change を探す
                        yoy_patterns = [
                            r'Annual\s*change[:\s]*([+-]?\d+\.?\d*)\s*%',
                            r'annual\s*%?\s*change[:\s]*([+-]?\d+\.?\d*)\s*%',
                            r'([+-]?\d+\.?\d*)\s*%\s*Annual\s*change',
                        ]
                        for pattern in yoy_patterns:
                            m = re.search(pattern, text, re.IGNORECASE)
                            if m:
                                yoy_value = float(m.group(1))
                                break

                        # ヘッダー行+値行形式のフォールバック
                        # "Monthly change Quarterly change Annual change\n£300,077 +0.7% +0.1% +1.0%"
                        if mom_value is None or yoy_value is None:
                            m = re.search(
                                r'Monthly\s+change\s+Quarterly\s+change\s+Annual\s+change\s*\n'
                                r'[£\d,]+\s+([+-]?\d+\.?\d*)\s*%\s+([+-]?\d+\.?\d*)\s*%\s+([+-]?\d+\.?\d*)\s*%',
                                text, re.IGNORECASE
                            )
                            if m:
                                if mom_value is None:
                                    mom_value = float(m.group(1))
                                    logger.info(f"Found Halifax MoM from header-row format: {mom_value}%")
                                if yoy_value is None:
                                    yoy_value = float(m.group(3))
                                    logger.info(f"Found Halifax YoY from header-row format: {yoy_value}%")

            if mom_value is None and yoy_value is None:
                logger.warning(f"Could not extract values from PDF: {pdf_path.name}")
                return None

            result = {}
            if mom_value is not None:
                result["mom"] = {"date": data_date, "value": mom_value}
            if yoy_value is not None:
                result["yoy"] = {"date": data_date, "value": yoy_value}

            # 3ページ目（または4ページ目）の履歴テーブルから修正値を抽出
            with pdfplumber.open(pdf_path) as pdf:
                revisions = []
                # 3ページ目と4ページ目の両方をチェック（PDFによりテーブル位置が異なる）
                for page_idx in [2, 3]:
                    if len(pdf.pages) > page_idx:
                        hist_text = pdf.pages[page_idx].extract_text()
                        if hist_text:
                            found = self._extract_historical_table(hist_text)
                            if found:
                                revisions = found
                                logger.info(f"[Halifax] Extracted {len(revisions)} revision rows from PDF page {page_idx + 1}")
                                break
                if revisions:
                    result["revisions"] = revisions

            logger.info(f"Extracted from {pdf_path.name}: mom={result.get('mom')}, yoy={result.get('yoy')}, revisions={len(result.get('revisions', []))}")
            return result

        except Exception as e:
            logger.error(f"Error extracting data from PDF {pdf_path.name}: {e}")
            return None

    def _extract_historical_table(self, text: str) -> List[Dict[str, Any]]:
        """
        PDF 4ページ目の履歴テーブルを解析して修正値を抽出

        テーブル形式:
          January 2025 512.4 297,118 0.1 1.1 2.3
          February 514.3 298,274 0.4 0.7 2.8
          ...
          December 513.8 297,938 -0.5 0.2 0.4
          January 2026 517.5 300,077 0.7 0.1 1.0
        """
        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        results = []
        current_year = None

        for line in text.split('\n'):
            # "January 2025 512.4 297,118 0.1 1.1 2.3" or "February 514.3 298,274 0.4 0.7 2.8"
            m = re.match(
                r'(January|February|March|April|May|June|July|August|September|October|November|December)'
                r'(?:\s+(\d{4}))?\s+[\d.]+\s+[\d,]+\s+([+-]?\d+\.?\d*)\s+[+-]?\d+\.?\d*\s+([+-]?\d+\.?\d*)',
                line.strip()
            )
            if m:
                month_name = m.group(1)
                if m.group(2):
                    current_year = int(m.group(2))
                if current_year is None:
                    continue
                month_num = month_names.index(month_name) + 1
                # 年を跨ぐ場合: January YYYY の後の February は同年
                # ただし December の次の January は翌年（年が明示される）
                date_str = f"{current_year}-{month_num:02d}-01"
                mom = float(m.group(3))
                yoy = float(m.group(4))
                results.append({"date": date_str, "mom": mom, "yoy": yoy})

        return results

    def _load_imported_pdfs(self) -> set:
        """処理済みPDFリストを読み込む"""
        try:
            if IMPORTED_PDF_FILE.exists():
                with open(IMPORTED_PDF_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(data.get("imported", []))
        except Exception as e:
            logger.error(f"Error loading imported PDFs list: {e}")
        return set()

    def _mark_pdf_as_imported(self, pdf_path: Path) -> None:
        """PDFを処理済みとしてマーク"""
        try:
            imported = self._load_imported_pdfs()
            pdf_key = f"{pdf_path.name}:{pdf_path.stat().st_size}"
            imported.add(pdf_key)

            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(IMPORTED_PDF_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    "imported": list(imported),
                    "last_updated": datetime.now(JST).isoformat()
                }, f, ensure_ascii=False, indent=2)
            logger.info(f"Marked PDF as imported: {pdf_path.name}")
        except Exception as e:
            logger.error(f"Error marking PDF as imported: {e}")

    def _merge_pdf_data(self, db_data: List[Dict], pdf_data: Optional[Dict]) -> List[Dict]:
        """PDFデータをDBデータにマージ（メモリ上）"""
        if not pdf_data:
            return db_data

        merged = db_data.copy()
        pdf_date = pdf_data["date"]
        pdf_value = pdf_data["value"]

        # 既存データを検索して更新または追加
        found = False
        for item in merged:
            if item["date"] == pdf_date:
                # 既存データがあれば値を更新（ハリファックスは修正が入る可能性あり）
                if item["value"] != pdf_value:
                    logger.info(f"Updating Halifax data: {pdf_date} {item['value']} -> {pdf_value}")
                    item["value"] = pdf_value
                found = True
                break

        if not found:
            # 新規追加
            merged.append({
                "date": pdf_date,
                "value": pdf_value,
                "forecast": None,
                "previous": None,
            })
            # 日付順でソート
            merged.sort(key=lambda x: x["date"])

        return merged

    def _save_pdf_data_to_db(self, pdf_data: Dict[str, Any]) -> bool:
        """
        PDFデータをDBに保存（UPSERT方式）

        ハリファックスは前回分の修正が入る可能性があるため、
        同じ日付のデータがあれば更新する
        """
        if not pdf_data:
            return False

        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            mom_data = pdf_data.get("mom")
            yoy_data = pdf_data.get("yoy")

            with SessionLocal() as session:
                # MoMデータをUPSERT
                if mom_data:
                    self._upsert_event(
                        session,
                        event_name="Halifax House Price Index MoM",
                        date_str=mom_data["date"],
                        value=mom_data["value"]
                    )

                # YoYデータをUPSERT
                if yoy_data:
                    self._upsert_event(
                        session,
                        event_name="Halifax House Price Index YoY",
                        date_str=yoy_data["date"],
                        value=yoy_data["value"]
                    )

                session.commit()
                logger.info(f"[Halifax] Saved PDF data to DB: MoM={mom_data}, YoY={yoy_data}")
                return True

        except Exception as e:
            logger.error(f"[Halifax] Error saving PDF data to DB: {e}")
            return False

    def _upsert_event(self, session, event_name: str, date_str: str, value: float) -> None:
        """
        イベントをUPSERT（既存なら更新、なければ挿入）
        """
        from sqlalchemy import text
        from datetime import datetime

        # 日付をdatetime_utcに変換（07:00 UK時間）
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        datetime_utc = date_obj.replace(hour=7, minute=0, second=0)

        # 既存レコードを検索
        check_query = text("""
            SELECT id, actual FROM economic_calendar_events
            WHERE country = 'UK'
              AND event ILIKE :event_pattern
              AND datetime_utc::date = :target_date
            ORDER BY datetime_utc DESC
            LIMIT 1
        """)
        existing = session.execute(
            check_query,
            {"event_pattern": f"%{event_name}%", "target_date": date_obj.date()}
        ).fetchone()

        if existing:
            # 既存レコードがあり、値が異なる場合のみ更新
            existing_id, existing_value = existing
            if existing_value != value:
                update_query = text("""
                    UPDATE economic_calendar_events
                    SET actual = :value, updated_at = NOW()
                    WHERE id = :id
                """)
                session.execute(update_query, {"value": value, "id": existing_id})
                logger.info(f"[Halifax] Updated {event_name}: {date_str} {existing_value} -> {value}")
        else:
            # 新規挿入
            insert_query = text("""
                INSERT INTO economic_calendar_events
                (country, event, datetime_utc, actual, estimate, previous, impact, source, created_at, updated_at)
                VALUES ('UK', :event, :datetime_utc, :actual, NULL, NULL, 'Medium', 'PDF Import', NOW(), NOW())
            """)
            session.execute(insert_query, {
                "event": event_name,
                "datetime_utc": datetime_utc,
                "actual": value
            })
            logger.info(f"[Halifax] Inserted {event_name}: {date_str} = {value}")

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            # 次回発表日を確認
            next_release = self._get_next_release()
            if next_release:
                next_release_dt = datetime.fromisoformat(next_release)
                if next_release_dt.tzinfo is None:
                    next_release_dt = next_release_dt.replace(tzinfo=LONDON)

                now = datetime.now(LONDON)

                # 発表日を3分過ぎて、最終更新が発表前の場合は更新
                if now > next_release_dt and last_updated < next_release_dt:
                    from datetime import timedelta
                    if now > next_release_dt + timedelta(minutes=3):
                        return True

            return False

        except Exception as e:
            logger.error(f"Error checking refresh status: {e}")
            return True

    def _get_next_release(self) -> Optional[str]:
        """次回発表日を取得（キャッシュ付き）"""
        # キャッシュチェック
        cached_schedule = redis_client.get(self.SCHEDULE_CACHE_KEY)
        if cached_schedule:
            cache_date_str = cached_schedule.get("cache_date")
            if cache_date_str:
                try:
                    cache_date = datetime.fromisoformat(cache_date_str)
                    days_old = (datetime.now(JST) - cache_date).days
                    if days_old < self.SCHEDULE_REFRESH_DAYS:
                        return cached_schedule.get("next_release")
                except Exception:
                    pass

        # ファイルキャッシュフォールバック
        file_cache = self._load_schedule_cache()
        if file_cache:
            return file_cache.get("next_release")

        # 推定次回発表日を計算（毎月7日〜10日、07:00 UK時間）
        return self._calculate_estimated_next_release()

    def _calculate_estimated_next_release(self) -> Optional[str]:
        """推定次回発表日を計算（毎月7日〜10日、07:00 UK時間）"""
        try:
            now = datetime.now(LONDON)
            year = now.year
            month = now.month

            # Halifaxは通常毎月7日〜10日に発表
            # 8日を基準とする
            release_day = 8

            # 今月の発表日を計算
            if now.day < release_day:
                # 今月の発表日がまだ
                next_release = datetime(year, month, release_day, 7, 0, tzinfo=LONDON)
            else:
                # 今月の発表は終了、来月
                if month == 12:
                    next_release = datetime(year + 1, 1, release_day, 7, 0, tzinfo=LONDON)
                else:
                    next_release = datetime(year, month + 1, release_day, 7, 0, tzinfo=LONDON)

            return next_release.isoformat()

        except Exception as e:
            logger.error(f"Error calculating estimated next release: {e}")
            return None

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save file cache: {e}")

    def _load_schedule_cache(self) -> Optional[Dict[str, Any]]:
        """スケジュールキャッシュを読み込む"""
        try:
            if not SCHEDULE_CACHE_FILE.exists():
                return None
            with open(SCHEDULE_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load schedule cache: {e}")
            return None

    def _save_schedule_cache(self, data: Dict[str, Any]) -> None:
        """スケジュールキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(SCHEDULE_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save schedule cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        redis_client.delete(self.SCHEDULE_CACHE_KEY)
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        # 最新PDFを確認
        pdf_files = list(PDF_DIR.glob("*halifax*.pdf")) if PDF_DIR.exists() else []
        latest_pdf = pdf_files[0].name if pdf_files else None

        return {
            "indicator": "Halifax House Price Index",
            "source": "Database (CSV Import) + PDF",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "mom_count": len(cached_data.get("mom", [])) if cached_data else 0,
            "yoy_count": len(cached_data.get("yoy", [])) if cached_data else 0,
            "latest_mom": cached_data.get("latest_mom") if cached_data else None,
            "latest_yoy": cached_data.get("latest_yoy") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
            "latest_pdf": latest_pdf,
        }


# シングルトンインスタンス
halifax_house_price_service = HalifaxHousePriceService()
