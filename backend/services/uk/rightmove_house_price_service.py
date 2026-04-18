"""
ライトムーブ住宅価格指数サービス
DBからRightmove House Priceデータを取得し、PDFから最新データを取得

指標:
- ライトムーブ住宅価格指数 前月比（MoM）
- ライトムーブ住宅価格指数 前年比（YoY）

データソース:
- DB: economic_calendar_events（CSV蓄積データ）
- CSV: 過去データインポート
- PDF: 手動ダウンロード（backend/data/manual_update/monthly/uk_rightmove/Rightmove-HPI-YYYYMMl.pdf）

発表スケジュール:
- 月次（毎月11日～26日、08:01 UK時間）

キャッシュ方式: 独自更新判定方式（次回発表日ベース + PDF読み取り）

PDFインポート手順:
1. https://www.rightmove.co.uk/news/house-price-index/ からPDFをダウンロード
2. ファイル名を Rightmove-HPI-YYYYMMl.pdf に変更（例: Rightmove-HPI-202601l.pdf）
3. backend/data/manual_update/monthly/uk_rightmove/ に配置
4. PDFの4ページ目に Monthly changes in average asking prices のグラフがある
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
DATA_CACHE_FILE = CACHE_DIR / "rightmove_house_price_cache.json"
IMPORTED_PDF_FILE = CACHE_DIR / "rightmove_imported_pdfs.json"

# PDFディレクトリ
PDF_DIR = Path(__file__).parent.parent.parent / "data" / "manual_update" / "monthly" / "uk_rightmove"


class RightmoveHousePriceService:
    """ライトムーブ住宅価格指数サービス"""

    DATA_CACHE_KEY = "uk:rightmove_house_price:data"

    def __init__(self):
        pass

    def get_rightmove_house_price_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ライトムーブ住宅価格指数データを取得"""
        # 未処理PDFがあればキャッシュを無視して強制更新
        if not force_refresh and self._check_new_pdfs():
            logger.info("[Rightmove] New PDF detected, forcing refresh")
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
                logger.info(f"[Rightmove] DB empty, restored {len(mom_data)} MoM + {len(yoy_data)} YoY from file cache")

        # 未処理のPDFがあれば自動でDBにインポート
        new_pdfs = self._check_new_pdfs()
        for pdf_path in new_pdfs:
            pdf_data = self._extract_data_from_pdf(pdf_path)
            if pdf_data and self._save_pdf_data_to_db(pdf_data):
                self._mark_pdf_as_imported(pdf_path)
                # メモリ上でもマージ（最新月）
                mom_data = self._merge_pdf_data(mom_data, pdf_data.get("mom"))
                yoy_data = self._merge_pdf_data(yoy_data, pdf_data.get("yoy"))
                # 前月データも反映（PDFテーブルに含まれる過去月の修正値/補完値）
                for prev in pdf_data.get("previous_months", []):
                    mom_data = self._merge_pdf_data(mom_data, {"date": prev["date"], "value": prev["mom"]})
                    yoy_data = self._merge_pdf_data(yoy_data, {"date": prev["date"], "value": prev["yoy"]})
                logger.info(f"[Rightmove] Auto-imported new PDF: {pdf_path.name}")

        if mom_data or yoy_data:
            next_release = self._calculate_next_release()
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
                      AND event ILIKE '%Rightmove House Price Index MoM%'
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

                logger.info(f"[Rightmove House Price] Loaded {len(result)} MoM records from DB")
                return result

        except Exception as e:
            logger.error(f"[Rightmove House Price] Error loading MoM from DB: {e}")
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
                      AND event ILIKE '%Rightmove House Price Index YoY%'
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

                logger.info(f"[Rightmove House Price] Loaded {len(result)} YoY records from DB")
                return result

        except Exception as e:
            logger.error(f"[Rightmove House Price] Error loading YoY from DB: {e}")
            return []

    def _load_latest_from_pdf(self) -> Optional[Dict[str, Any]]:
        """
        手動ダウンロードしたPDFから最新データを取得

        PDFファイル名形式: Rightmove-HPI-YYYYMMl.pdf
        例: Rightmove-HPI-202601l.pdf

        PDFの1ページ目から以下を抽出:
        - Monthly change: +2.8%
        - Annual change: +0.5%
        """
        try:
            if not PDF_DIR.exists():
                logger.warning(f"PDF directory not found: {PDF_DIR}")
                return None

            # 最新のPDFファイルを探す
            pdf_files = list(PDF_DIR.glob("*[Rr]ightmove*.pdf"))
            if not pdf_files:
                logger.info("No Rightmove PDF files found")
                return None

            # ファイル名でソートして最新を取得
            pdf_files.sort(reverse=True)
            latest_pdf = pdf_files[0]
            logger.info(f"Found Rightmove PDF: {latest_pdf.name}")

            # ファイル名から対象月を抽出
            # 対応形式: YYYYMMDD(8桁), YYYYMM(6桁), YYYYMMl(6桁+文字)
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
                    # 1ページ目を読む（メインサマリーがある）
                    page = pdf.pages[0]
                    text = page.extract_text()

                    if text:
                        month_names = [
                            "January", "February", "March", "April", "May", "June",
                            "July", "August", "September", "October", "November", "December"
                        ]
                        target_month_name = month_names[month - 1]

                        # 最優先: テキスト内テーブル行（最も信頼性が高い）
                        # "February 2026 £368,019 0.0% 0.0% 284.5" 形式
                        row_pattern = (
                            rf'{target_month_name}\s+{year}\s+\S+\s+'
                            r'([+-]?\d+\.?\d*)\s*%\s+([+-]?\d+\.?\d*)\s*%'
                        )
                        row_match = re.search(row_pattern, text, re.IGNORECASE)
                        if row_match:
                            mom_value = float(row_match.group(1))
                            yoy_value = float(row_match.group(2))
                            logger.info(f"Found Rightmove from text table row: MoM={mom_value}%, YoY={yoy_value}%")

                        # フォールバック: "Monthly change: +2.8%" 形式
                        if mom_value is None:
                            mom_patterns = [
                                r'Monthly\s*change[:\s]*([+-]?\d+\.?\d*)\s*%',
                                r'([+-]?\d+\.?\d*)\s*%\s*Monthly\s*change',
                            ]
                            for pattern in mom_patterns:
                                match = re.search(pattern, text, re.IGNORECASE)
                                if match:
                                    mom_value = float(match.group(1))
                                    logger.info(f"Found Rightmove MoM from PDF: {mom_value}%")
                                    break

                        if yoy_value is None:
                            yoy_patterns = [
                                r'Annual\s*change[:\s]*([+-]?\d+\.?\d*)\s*%',
                                r'([+-]?\d+\.?\d*)\s*%\s*Annual\s*change',
                            ]
                            for pattern in yoy_patterns:
                                match = re.search(pattern, text, re.IGNORECASE)
                                if match:
                                    yoy_value = float(match.group(1))
                                    logger.info(f"Found Rightmove YoY from PDF: {yoy_value}%")
                                    break

                    # structured table フォールバック
                    if mom_value is None or yoy_value is None:
                        tables = page.extract_tables()
                        for table in tables:
                            for row in table:
                                if row and len(row) >= 4:
                                    for i, cell in enumerate(row):
                                        if cell and '%' in str(cell):
                                            value_match = re.search(r'([+-]?\d+\.?\d*)\s*%', str(cell))
                                            if value_match:
                                                value = float(value_match.group(1))
                                                if i == 2 and mom_value is None:
                                                    mom_value = value
                                                    logger.info(f"Found Rightmove MoM from table: {mom_value}%")
                                                elif i == 3 and yoy_value is None:
                                                    yoy_value = value
                                                    logger.info(f"Found Rightmove YoY from table: {yoy_value}%")

            if mom_value is None and yoy_value is None:
                logger.warning("Could not extract values from Rightmove PDF")
                return None

            result = {}
            if mom_value is not None:
                result["mom"] = {"date": data_date, "value": mom_value}
            if yoy_value is not None:
                result["yoy"] = {"date": data_date, "value": yoy_value}

            logger.info(f"Extracted Rightmove data from PDF: {result}")
            return result

        except Exception as e:
            logger.error(f"Error loading Rightmove data from PDF: {e}")
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

        # Rightmove PDFファイルを検索（大文字小文字両対応）
        pdf_files = list(PDF_DIR.glob("*[Rr]ightmove*.pdf"))
        new_pdfs = []

        for pdf_path in pdf_files:
            # ファイル名とサイズでユニーク識別
            pdf_key = f"{pdf_path.name}:{pdf_path.stat().st_size}"
            if pdf_key not in imported_pdfs:
                new_pdfs.append(pdf_path)

        if new_pdfs:
            logger.info(f"[Rightmove] Found {len(new_pdfs)} new PDF(s) to import")

        return new_pdfs

    def _extract_data_from_pdf(self, pdf_path: Path) -> Optional[Dict[str, Any]]:
        """
        指定されたPDFファイルからデータを抽出

        Args:
            pdf_path: PDFファイルパス

        Returns:
            抽出されたデータ {"mom": {...}, "yoy": {...}, "previous_months": [...]}
        """
        try:
            # ファイル名から対象月を抽出
            # 対応形式: YYYYMMDD(8桁), YYYYMM(6桁), YYYYMMl(6桁+文字)
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
            previous_months = []

            month_names = [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]

            with pdfplumber.open(pdf_path) as pdf:
                if len(pdf.pages) > 0:
                    page = pdf.pages[0]
                    text = page.extract_text()

                    if text:
                        target_month_name = month_names[month - 1]

                        # テキスト内テーブルから全月の行を抽出
                        # "February 2026 £368,019 0.0% 0.0% 284.5" 形式
                        # "January 2026 £368,031 +2.8% +0.5% 284.5" 形式
                        all_row_pattern = (
                            r'(January|February|March|April|May|June|July|August|September|October|November|December)'
                            r'\s+(\d{4})\s+\S+\s+'
                            r'([+-]?\d+\.?\d*)\s*%\s+([+-]?\d+\.?\d*)\s*%'
                        )
                        for row_match in re.finditer(all_row_pattern, text, re.IGNORECASE):
                            row_month_name = row_match.group(1)
                            row_year = int(row_match.group(2))
                            row_mom = float(row_match.group(3))
                            row_yoy = float(row_match.group(4))
                            row_month_num = month_names.index(row_month_name) + 1
                            row_date = f"{row_year}-{row_month_num:02d}-01"

                            if row_date == data_date:
                                # 対象月のデータ
                                mom_value = row_mom
                                yoy_value = row_yoy
                                logger.info(f"Found Rightmove from text table row: {row_date} MoM={row_mom}%, YoY={row_yoy}%")
                            else:
                                # 前月のデータ（修正値として保存）
                                previous_months.append({
                                    "date": row_date,
                                    "mom": row_mom,
                                    "yoy": row_yoy,
                                })
                                logger.info(f"Found Rightmove previous month: {row_date} MoM={row_mom}%, YoY={row_yoy}%")

                        # フォールバック: "Monthly change: +2.8%" 形式
                        if mom_value is None:
                            mom_patterns = [
                                r'Monthly\s*change[:\s]*([+-]?\d+\.?\d*)\s*%',
                                r'([+-]?\d+\.?\d*)\s*%\s*Monthly\s*change',
                            ]
                            for pattern in mom_patterns:
                                m = re.search(pattern, text, re.IGNORECASE)
                                if m:
                                    mom_value = float(m.group(1))
                                    logger.info(f"Found Rightmove MoM from text pattern: {mom_value}%")
                                    break

                        if yoy_value is None:
                            yoy_patterns = [
                                r'Annual\s*change[:\s]*([+-]?\d+\.?\d*)\s*%',
                                r'([+-]?\d+\.?\d*)\s*%\s*Annual\s*change',
                            ]
                            for pattern in yoy_patterns:
                                m = re.search(pattern, text, re.IGNORECASE)
                                if m:
                                    yoy_value = float(m.group(1))
                                    logger.info(f"Found Rightmove YoY from text pattern: {yoy_value}%")
                                    break

                    # structured table フォールバック
                    if mom_value is None or yoy_value is None:
                        tables = page.extract_tables()
                        for table in tables:
                            for row in table:
                                if row and len(row) >= 4:
                                    for i, cell in enumerate(row):
                                        if cell and '%' in str(cell):
                                            value_match = re.search(r'([+-]?\d+\.?\d*)\s*%', str(cell))
                                            if value_match:
                                                value = float(value_match.group(1))
                                                if i == 2 and mom_value is None:
                                                    mom_value = value
                                                    logger.info(f"Found Rightmove MoM from table: {mom_value}%")
                                                elif i == 3 and yoy_value is None:
                                                    yoy_value = value
                                                    logger.info(f"Found Rightmove YoY from table: {yoy_value}%")

            if mom_value is None and yoy_value is None:
                logger.warning(f"Could not extract values from PDF: {pdf_path.name}")
                return None

            result = {}
            if mom_value is not None:
                result["mom"] = {"date": data_date, "value": mom_value}
            if yoy_value is not None:
                result["yoy"] = {"date": data_date, "value": yoy_value}
            if previous_months:
                result["previous_months"] = previous_months

            logger.info(f"Extracted from {pdf_path.name}: mom={result.get('mom')}, yoy={result.get('yoy')}, previous_months={len(previous_months)}")
            return result

        except Exception as e:
            logger.error(f"Error extracting data from PDF {pdf_path.name}: {e}")
            return None

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
                # 既存データがあれば値を更新
                if item["value"] != pdf_value:
                    logger.info(f"Updating Rightmove data: {pdf_date} {item['value']} -> {pdf_value}")
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

        対象月の MoM/YoY に加え、PDF内テーブルに含まれる前月データ
        （previous_months）も修正値として保存する。
        """
        if not pdf_data:
            return False

        try:
            from core.database import SessionLocal

            mom_data = pdf_data.get("mom")
            yoy_data = pdf_data.get("yoy")
            previous_months = pdf_data.get("previous_months") or []

            with SessionLocal() as session:
                if mom_data:
                    self._upsert_event(
                        session,
                        event_name="Rightmove House Price Index MoM",
                        date_str=mom_data["date"],
                        value=mom_data["value"]
                    )

                if yoy_data:
                    self._upsert_event(
                        session,
                        event_name="Rightmove House Price Index YoY",
                        date_str=yoy_data["date"],
                        value=yoy_data["value"]
                    )

                for prev in previous_months:
                    self._upsert_event(
                        session,
                        event_name="Rightmove House Price Index MoM",
                        date_str=prev["date"],
                        value=prev["mom"],
                    )
                    self._upsert_event(
                        session,
                        event_name="Rightmove House Price Index YoY",
                        date_str=prev["date"],
                        value=prev["yoy"],
                    )

                session.commit()
                logger.info(f"[Rightmove] Saved PDF data to DB: MoM={mom_data}, YoY={yoy_data}, prev={len(previous_months)}")
                return True

        except Exception as e:
            logger.error(f"[Rightmove] Error saving PDF data to DB: {e}")
            return False

    def _upsert_event(self, session, event_name: str, date_str: str, value: float) -> None:
        """
        イベントをUPSERT（既存なら更新、なければ挿入）

        PDFはデータ対象月ベースで保存するため CSV_IMPORT と同じ形式で格納する。
        """
        from sqlalchemy import text
        from datetime import datetime

        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        datetime_utc = date_obj.replace(hour=8, minute=1, second=0)
        event_key = f"UK_{event_name}_{date_obj.strftime('%Y%m%d')}"

        check_query = text("""
            SELECT id, actual FROM economic_calendar_events
            WHERE country = 'UK'
              AND event ILIKE :event_pattern
              AND provider IN ('CSV_IMPORT', 'PDF_IMPORT')
              AND datetime_utc::date = :target_date
            ORDER BY datetime_utc DESC
            LIMIT 1
        """)
        existing = session.execute(
            check_query,
            {"event_pattern": f"%{event_name}%", "target_date": date_obj.date()}
        ).fetchone()

        if existing:
            existing_id, existing_value = existing
            if existing_value is None or float(existing_value) != value:
                update_query = text("""
                    UPDATE economic_calendar_events
                    SET actual = :value, updated_at = NOW()
                    WHERE id = :id
                """)
                session.execute(update_query, {"value": value, "id": existing_id})
                logger.info(f"[Rightmove] Updated {event_name}: {date_str} {existing_value} -> {value}")
        else:
            insert_query = text("""
                INSERT INTO economic_calendar_events
                (provider, event_key, country, currency, event,
                 datetime_utc, datetime_raw, has_time, impact, actual,
                 raw_json, ingested_at, updated_at)
                VALUES ('PDF_IMPORT', :event_key, 'UK', 'GBP', :event,
                        :datetime_utc, :datetime_raw, TRUE, 'Low', :actual,
                        :raw_json, NOW(), NOW())
            """)
            session.execute(insert_query, {
                "event_key": event_key,
                "event": event_name,
                "datetime_utc": datetime_utc,
                "datetime_raw": datetime_utc.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                "actual": value,
                "raw_json": json.dumps({"source": "PDF", "data_month": date_str}),
            })
            logger.info(f"[Rightmove] Inserted {event_name}: {date_str} = {value}")

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(LONDON)

            # 毎月11日～26日の08:01-09:11 UK時間にチェック
            day = now.day
            hour = now.hour
            minute = now.minute

            # 発表期間内かチェック
            if 11 <= day <= 26:
                # 08:01-08:11 または 09:01-09:11 (冬時間対応)
                if (hour == 8 and 1 <= minute <= 11) or (hour == 9 and 1 <= minute <= 11):
                    # 今日まだ更新していなければ更新
                    if last_updated.date() < now.date():
                        return True

            # 最終更新から24時間以上経過していれば更新
            if (datetime.now(JST) - last_updated).total_seconds() > 86400:
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking refresh status: {e}")
            return True

    def _calculate_next_release(self) -> Optional[str]:
        """次回発表日を計算"""
        try:
            now = datetime.now(LONDON)
            year = now.year
            month = now.month

            # 今月の発表期間（11日～26日）をチェック
            if now.day < 11:
                # 今月の11日が次回発表日
                next_release = datetime(year, month, 11, 8, 1, tzinfo=LONDON)
            elif now.day <= 26:
                # 発表期間中 - 明日の8:01が次回チェック
                next_release = datetime(year, month, now.day + 1, 8, 1, tzinfo=LONDON)
            else:
                # 今月の発表期間終了 - 来月の11日
                if month == 12:
                    next_release = datetime(year + 1, 1, 11, 8, 1, tzinfo=LONDON)
                else:
                    next_release = datetime(year, month + 1, 11, 8, 1, tzinfo=LONDON)

            return next_release.isoformat()

        except Exception as e:
            logger.error(f"Error calculating next release: {e}")
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

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        # 最新PDFを確認
        pdf_files = list(PDF_DIR.glob("*[Rr]ightmove*.pdf")) if PDF_DIR.exists() else []
        latest_pdf = pdf_files[0].name if pdf_files else None

        return {
            "indicator": "Rightmove House Price Index",
            "source": "Database (CSV Import) + PDF",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "mom_count": len(cached_data.get("mom", [])) if cached_data else 0,
            "yoy_count": len(cached_data.get("yoy", [])) if cached_data else 0,
            "latest_mom": cached_data.get("latest_mom") if cached_data else None,
            "latest_yoy": cached_data.get("latest_yoy") if cached_data else None,
            "next_release": self._calculate_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
            "latest_pdf": latest_pdf,
        }


# シングルトンインスタンス
rightmove_house_price_service = RightmoveHousePriceService()
