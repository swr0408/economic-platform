"""
RICS住宅価格サービス
DBからRICS House Price Balanceデータを取得し、PDFから最新データを取得

指標:
- RICS住宅価格バランス（住宅価格の上昇・下落を示すサーベイ指標）

データソース:
- DB: economic_calendar_events（FMP蓄積データ）
- CSV: 過去データインポート
- PDF: 手動ダウンロード（backend/data/manual_update/monthly/uk_rics/YYYYMM-rics-house-price.pdf）

発表スケジュール:
- 月次（不定期・FMPカレンダーから取得）

キャッシュ方式: FMP発表日時ベース判定方式 + PDF自動検知

PDFインポート手順:
1. https://www.rics.org/news-insights/research から UK Residential Market Survey をダウンロード
2. ファイル名を YYYYMM-rics-house-price.pdf に変更（例: 202512-rics-house-price.pdf）
3. backend/data/manual_update/monthly/uk_rics/ に配置
4. PDFの最初のページに House Price Balance の数値がある
"""
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "rics_house_price_cache.json"
IMPORTED_PDF_FILE = CACHE_DIR / "rics_imported_pdfs.json"

# PDFディレクトリ
PDF_DIR = Path(__file__).parent.parent.parent / "data" / "manual_update" / "monthly" / "uk_rics"


class RICSHousePriceService:
    """RICS住宅価格サービス"""

    DATA_CACHE_KEY = "uk:rics_house_price:data"
    ECONALPHA_ID = "rics_house_price"

    def __init__(self):
        pass

    def get_rics_house_price_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """RICS住宅価格データを取得"""
        # 未処理PDFがあればキャッシュを無視して強制更新
        if not force_refresh and self._check_new_pdfs():
            logger.info("[RICS] New PDF detected, forcing refresh")
            force_refresh = True

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # DBから取得（DB失敗時はファイルキャッシュから復元）
        db_result = self._load_from_db()
        if not db_result:
            file_cache = self._load_file_cache()
            if file_cache:
                db_result = file_cache.get("data", [])
                logger.info(f"[RICS] DB empty, restored {len(db_result)} records from file cache")

        # 未処理のPDFがあれば自動でDBにインポート
        new_pdfs = self._check_new_pdfs()
        for pdf_path in new_pdfs:
            pdf_data = self._extract_data_from_pdf(pdf_path)
            if pdf_data and self._save_pdf_data_to_db(pdf_data):
                self._mark_pdf_as_imported(pdf_path)
                # メモリ上でもマージ
                db_result = self._merge_pdf_data(db_result, pdf_data)
                logger.info(f"[RICS] Auto-imported new PDF: {pdf_path.name}")

        if db_result:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            latest = db_result[-1] if db_result else None

            cache_payload = {
                "data": db_result,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": db_result,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "database",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBから履歴データを取得

        注意: FMPデータは発表月で保存されているため、-1ヶ月してデータ対象月として返す
        CSVデータはデータ対象月で保存されているため、そのまま返す
        """
        try:
            from core.database import SessionLocal
            from sqlalchemy import text
            from dateutil.relativedelta import relativedelta

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc, actual, estimate, previous, provider
                    FROM economic_calendar_events
                    WHERE country = 'UK'
                      AND event ILIKE '%RICS House Price Balance%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                result = []
                seen_dates = set()

                for row in rows:
                    dt_utc, actual, estimate, previous, provider = row
                    if dt_utc:
                        # FMPデータは発表月なので-1ヶ月してデータ対象月に変換
                        # CSVデータはデータ対象月のまま
                        if provider == "FMP":
                            data_month = dt_utc - relativedelta(months=1)
                            date_str = data_month.strftime("%Y-%m-01")
                        else:
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

                # 日付順にソート
                result.sort(key=lambda x: x["date"])
                logger.info(f"[RICS House Price] Loaded {len(result)} records from DB")
                return result

        except Exception as e:
            logger.error(f"[RICS House Price] Error loading from DB: {e}")
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def _check_new_pdfs(self) -> List[Path]:
        """未処理のPDFファイルをチェック"""
        if not PDF_DIR.exists():
            return []

        imported_pdfs = self._load_imported_pdfs()
        pdf_files = list(PDF_DIR.glob("*rics*.pdf"))
        new_pdfs = []

        for pdf_path in pdf_files:
            pdf_key = f"{pdf_path.name}:{pdf_path.stat().st_size}"
            if pdf_key not in imported_pdfs:
                new_pdfs.append(pdf_path)

        if new_pdfs:
            logger.info(f"[RICS] Found {len(new_pdfs)} new PDF(s) to import")

        return new_pdfs

    def _extract_data_from_pdf(self, pdf_path: Path) -> Optional[Dict[str, Any]]:
        """PDFファイルからRICS House Price Balanceを抽出

        手順:
        1. 表紙ページからデータ対象月を抽出（例: "January 2026"）
        2. ファイル名からのフォールバック（YYYYMM形式）
        3. 全ページをスキャンしてHouse Price Balance値を抽出
        """
        try:
            try:
                import pdfplumber
            except ImportError:
                logger.warning("pdfplumber not installed, cannot read PDF")
                return None

            data_date = None
            value = None

            # 月名マッピング
            month_names = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                'september': 9, 'october': 10, 'november': 11, 'december': 12,
            }

            with pdfplumber.open(pdf_path) as pdf:
                # Step 1: 表紙からデータ対象月を抽出
                if len(pdf.pages) > 0:
                    cover_text = pdf.pages[0].extract_text() or ""
                    # "January 2026" のようなパターンを探す
                    month_pattern = r'(' + '|'.join(month_names.keys()) + r')\s+(\d{4})'
                    m = re.search(month_pattern, cover_text, re.IGNORECASE)
                    if m:
                        month_num = month_names[m.group(1).lower()]
                        year_num = int(m.group(2))
                        data_date = f"{year_num}-{month_num:02d}-01"
                        logger.info(f"[RICS] Extracted data month from cover: {data_date}")

                # Step 2: 表紙から取れなければファイル名フォールバック（YYYYMM or YYYYMMDD）
                if not data_date:
                    fname_match = re.search(r'(\d{6})', pdf_path.name)
                    if fname_match:
                        ds = fname_match.group(1)
                        year = int(ds[:4])
                        month = int(ds[4:6])
                        data_date = f"{year}-{month:02d}-01"
                        logger.info(f"[RICS] Extracted data month from filename: {data_date}")

                if not data_date:
                    logger.warning(f"Could not extract date from PDF: {pdf_path.name}")
                    return None

                # Step 3: 全ページをスキャンしてHouse Price Balance値を抽出
                # 2段階: まず「house price」文脈のパターンで全ページ検索し、
                # 見つからなければ汎用パターンにフォールバック

                # 優先パターン: 明示的に「house price」文脈を含むもの
                hp_patterns = [
                    # "House Price Balance: -25" / "House Price Balance -25%"
                    r'House\s*Price\s*Balance[:\s]*([+-]?\d+)',
                    # "-25% House Price Balance"
                    r'([+-]?\d+)\s*%?\s*House\s*Price\s*Balance',
                    # "aggregate net balance stands at -10%"（house pricesセクション内）
                    r'aggregate\s+net\s*\n?\s*balance\s+stands?\s+at\s+([+-]?\d+)\s*%',
                ]

                # 文脈パターン: 「house price」から近い距離にある「balance ... 数値」
                def _find_hp_balance_in_text(text: str) -> Optional[float]:
                    """house price の近く（200文字以内）にあるbalance値を抽出"""
                    for m in re.finditer(r'house\s+prices?', text, re.IGNORECASE):
                        # house price出現位置から200文字以内を探索
                        window = text[m.start():m.start() + 200]
                        bal = re.search(
                            r'(?:net\s+)?balance\s+(?:stands?\s+at|of|is|was|:)\s*([+-]?\d+)\s*%',
                            window, re.IGNORECASE
                        )
                        if bal:
                            return float(bal.group(1))
                    return None

                # 汎用フォールバックパターン
                fallback_patterns = [
                    r'(?:price)\s*(?:balance|net\s*balance)\s*(?:stands?\s*at|of|is|was|:)\s*([+-]?\d+)\s*%?',
                ]

                # Step 3a: 固定パターンで全ページ検索
                for page in pdf.pages[:6]:
                    text = page.extract_text()
                    if not text:
                        continue
                    for pattern in hp_patterns:
                        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                        if m:
                            value = float(m.group(1))
                            logger.info(f"[RICS] Found House Price Balance: {value} (page {page.page_number}, hp_pattern)")
                            break
                    if value is not None:
                        break

                # Step 3b: 文脈パターンで全ページ検索
                if value is None:
                    for page in pdf.pages[:6]:
                        text = page.extract_text()
                        if not text:
                            continue
                        found = _find_hp_balance_in_text(text)
                        if found is not None:
                            value = found
                            logger.info(f"[RICS] Found House Price Balance: {value} (page {page.page_number}, context)")
                            break

                # Step 3c: フォールバック
                if value is None:
                    for page in pdf.pages[:6]:
                        text = page.extract_text()
                        if not text:
                            continue
                        for pattern in fallback_patterns:
                            m = re.search(pattern, text, re.IGNORECASE)
                            if m:
                                value = float(m.group(1))
                                logger.info(f"[RICS] Found House Price Balance: {value} (page {page.page_number}, fallback)")
                                break
                        if value is not None:
                            break

            if value is None:
                logger.warning(f"Could not extract House Price Balance value from PDF: {pdf_path.name}")
                return None

            result = {
                "date": data_date,
                "value": value,
            }
            logger.info(f"[RICS] Extracted from {pdf_path.name}: {result}")
            return result

        except Exception as e:
            logger.error(f"Error extracting data from PDF {pdf_path.name}: {e}")
            return None

    def _merge_pdf_data(self, db_data: List[Dict], pdf_data: Optional[Dict]) -> List[Dict]:
        """PDFデータをDBデータにマージ（メモリ上）"""
        if not pdf_data or not db_data:
            if pdf_data and not db_data:
                return [{
                    "date": pdf_data["date"],
                    "value": pdf_data["value"],
                    "forecast": None,
                    "previous": None,
                }]
            return db_data or []

        merged = db_data.copy()
        pdf_date = pdf_data["date"]
        pdf_value = pdf_data["value"]

        found = False
        for item in merged:
            if item["date"] == pdf_date:
                if item["value"] != pdf_value:
                    logger.info(f"Updating RICS data: {pdf_date} {item['value']} -> {pdf_value}")
                    item["value"] = pdf_value
                found = True
                break

        if not found:
            merged.append({
                "date": pdf_date,
                "value": pdf_value,
                "forecast": None,
                "previous": None,
            })
            merged.sort(key=lambda x: x["date"])

        return merged

    def _save_pdf_data_to_db(self, pdf_data: Dict[str, Any]) -> bool:
        """PDFデータをDBに保存（UPSERT方式）

        PDF はデータ対象月で抽出されるため、CSV_IMPORT と同じ形式で保存する
        （datetime_utc = データ対象月の1日 12:00 UTC）。
        """
        if not pdf_data:
            return False

        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            date_str = pdf_data["date"]
            value = pdf_data["value"]

            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            datetime_utc = date_obj.replace(hour=12, minute=0, second=0)
            event_key = f"UK_RICS House Price Balance_{date_obj.strftime('%Y%m%d')}"

            with SessionLocal() as session:
                # CSV_IMPORT/PDF_IMPORT の既存レコード（データ対象月ベース）を検索
                check_query = text("""
                    SELECT id, actual FROM economic_calendar_events
                    WHERE country = 'UK'
                      AND event ILIKE '%RICS House Price Balance%'
                      AND provider IN ('CSV_IMPORT', 'PDF_IMPORT')
                      AND datetime_utc::date = :target_date
                    ORDER BY datetime_utc DESC
                    LIMIT 1
                """)
                existing = session.execute(
                    check_query,
                    {"target_date": date_obj.date()}
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
                        logger.info(f"[RICS] Updated: {date_str} {existing_value} -> {value}")
                    else:
                        logger.info(f"[RICS] Unchanged: {date_str} = {value}")
                else:
                    insert_query = text("""
                        INSERT INTO economic_calendar_events
                        (provider, event_key, country, currency, event,
                         datetime_utc, datetime_raw, has_time, impact, actual,
                         raw_json, ingested_at, updated_at)
                        VALUES ('PDF_IMPORT', :event_key, 'UK', 'GBP', 'RICS House Price Balance',
                                :datetime_utc, :datetime_raw, TRUE, 'Medium', :actual,
                                :raw_json, NOW(), NOW())
                    """)
                    session.execute(insert_query, {
                        "event_key": event_key,
                        "datetime_utc": datetime_utc,
                        "datetime_raw": datetime_utc.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                        "actual": value,
                        "raw_json": json.dumps({
                            "source": "PDF",
                            "pdf_file": pdf_data.get("pdf_file"),
                            "data_month": date_str,
                        }),
                    })
                    logger.info(f"[RICS] Inserted: {date_str} = {value}")

                session.commit()
                return True

        except Exception as e:
            logger.error(f"[RICS] Error saving PDF data to DB: {e}")
            return False

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

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[RICS House Price] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[RICS House Price] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "RICS House Price Balance",
            "source": "Database (FMP)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
rics_house_price_service = RICSHousePriceService()
