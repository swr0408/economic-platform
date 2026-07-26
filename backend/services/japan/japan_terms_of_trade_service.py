"""
日本 交易条件（Terms of Trade）サービス

輸出物価指数 / 輸入物価指数 × 100 で計算

交易条件（Terms of Trade）:
- 輸出物価指数÷輸入物価指数×100
- 100を超えると交易条件が改善（輸出価格が輸入価格より上昇）
- 100を下回ると交易条件が悪化（輸入価格が輸出価格より上昇）

データソース:
- BOJ (日本銀行) CGPI ZIPファイル
- URL: https://www.stat-search.boj.or.jp/ssi/docs/info/cgpi_m_jp.zip

発表スケジュール:
- 毎月10日〜18日頃 8:50 JST（CGPIと同一）
"""
import json
import requests
import zipfile
from io import BytesIO
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "price"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "japan_terms_of_trade_cache.json"


class JapanTermsOfTradeService:
    """日本 交易条件（Terms of Trade）サービス"""

    DATA_CACHE_KEY = "japan:terms_of_trade:data"

    # BOJ CGPI ZIP URL
    CGPI_ZIP_URL = "https://www.stat-search.boj.or.jp/ssi/docs/info/cgpi_m_jp.zip"

    # 発表時刻設定（JST）
    RELEASE_HOUR_JST = 8
    RELEASE_MINUTE_JST = 50

    # 対象系列のパターン（指数値）
    EXPORT_YEN_PATTERN = "[輸出物価指数/円ベース] 総平均"
    IMPORT_YEN_PATTERN = "[輸入物価指数/円ベース] 総平均"

    # FMP indicator ID（マッピングテーブル参照用）
    INDICATOR_ID = "japan_cgpi"  # CGPIと同一の発表日

    def __init__(self):
        self._fmp_utils = None

    @property
    def fmp_utils(self):
        """遅延インポートでFMPユーティリティを取得"""
        if self._fmp_utils is None:
            from services.japan.fmp_next_release_utils import (
                get_next_release_from_fmp,
                should_refresh_by_fmp_schedule
            )
            self._fmp_utils = {
                "get_next_release": get_next_release_from_fmp,
                "should_refresh": should_refresh_by_fmp_schedule
            }
        return self._fmp_utils

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """FMPから次回発表日時を取得"""
        try:
            return self.fmp_utils["get_next_release"](self.INDICATOR_ID)
        except Exception as e:
            print(f"Error getting next release: {e}")
            return self._calculate_next_release()

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """交易条件データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    cached_data["cached"] = True
                    cached_data["source"] = "redis"
                    cached_data["next_release"] = self._get_next_release()
                    return cached_data

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    file_cache["cached"] = True
                    file_cache["source"] = "file"
                    file_cache["next_release"] = self._get_next_release()
                    return file_cache

        # BOJからデータ取得
        result = self._fetch_from_boj()
        if result and result.get("data"):
            latest = self._get_latest(result["data"])
            next_release = self._get_next_release()
            from services.usa.fmp_next_release_utils import guarded_last_updated
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY,
                latest.get("date") if isinstance(latest, dict) else None,
                now_str,
            )

            cache_payload = {
                "data": result["data"],
                "latest": latest,
                "metadata": {
                    "source": "Bank of Japan (BOJ)",
                    "source_url": self.CGPI_ZIP_URL,
                    "description": "Japan Terms of Trade (Export Price Index / Import Price Index × 100)",
                    "unit": "Index (2020=100)",
                    "frequency": "Monthly",
                },
                "next_release": next_release,
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result["data"],
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "boj",
                "last_updated": last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            file_cache["cached"] = True
            file_cache["source"] = "file (fallback)"
            file_cache["next_release"] = self._get_next_release()
            return file_cache

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": self._get_next_release(),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _get_latest(self, data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """最新データを取得"""
        if not data:
            return None
        return data[-1]

    def _fetch_from_boj(self) -> Optional[Dict[str, Any]]:
        """BOJ ZIPファイルからデータを取得"""
        try:
            print(f"Fetching Japan Terms of Trade data from BOJ ZIP: {self.CGPI_ZIP_URL}")

            # ZIPファイルをダウンロード
            response = requests.get(self.CGPI_ZIP_URL, timeout=60)
            response.raise_for_status()
            print(f"Downloaded ZIP: {len(response.content)} bytes")

            # ZIPを解凍してCSVを取得
            with zipfile.ZipFile(BytesIO(response.content)) as zf:
                csv_files = [f for f in zf.namelist() if f.endswith('.csv')]
                if not csv_files:
                    print("No CSV files found in ZIP")
                    return None

                csv_content = zf.read(csv_files[0]).decode('shift_jis')

            # CSVをパース
            processed_data = self._parse_csv(csv_content)
            if not processed_data:
                return None

            return {"data": processed_data}

        except Exception as e:
            print(f"Error fetching Terms of Trade data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_csv(self, csv_content: str) -> Optional[List[Dict[str, Any]]]:
        """
        CGPI CSVファイルをパースして交易条件を計算

        交易条件 = 輸出物価指数 / 輸入物価指数 × 100
        """
        try:
            lines = csv_content.strip().split('\n')
            print(f"CSV has {len(lines)} lines")

            if len(lines) < 2:
                return None

            # ヘッダー行から日付を取得
            header_parts = lines[0].split(',')
            date_columns = []
            for i, part in enumerate(header_parts):
                part = part.strip()
                if part.isdigit() and len(part) == 6:
                    date_columns.append((i, part))

            print(f"Found {len(date_columns)} date columns")

            if not date_columns:
                return None

            # 輸出・輸入物価指数の行を探す
            export_yen_row = None
            import_yen_row = None

            for line in lines[1:]:
                parts = line.split(',')
                if len(parts) < 4:
                    continue

                category_name = parts[2].strip().strip('"')

                if self.EXPORT_YEN_PATTERN in category_name and export_yen_row is None:
                    export_yen_row = parts
                    print(f"Found export yen row: {category_name}")

                if self.IMPORT_YEN_PATTERN in category_name and import_yen_row is None:
                    import_yen_row = parts
                    print(f"Found import yen row: {category_name}")

                if export_yen_row and import_yen_row:
                    break

            if not export_yen_row or not import_yen_row:
                print("Could not find export/import price rows")
                return None

            # 指数値を抽出
            export_yen_values = {}
            import_yen_values = {}

            for idx, date_str in date_columns:
                year = date_str[:4]
                month = date_str[4:6]
                date_key = f"{year}-{month}-01"

                if idx < len(export_yen_row):
                    val_str = export_yen_row[idx].strip()
                    if val_str:
                        try:
                            export_yen_values[date_key] = float(val_str)
                        except ValueError:
                            pass

                if idx < len(import_yen_row):
                    val_str = import_yen_row[idx].strip()
                    if val_str:
                        try:
                            import_yen_values[date_key] = float(val_str)
                        except ValueError:
                            pass

            # 交易条件を計算
            all_dates = sorted(set(export_yen_values.keys()) & set(import_yen_values.keys()))
            series_data = []

            for date_key in all_dates:
                export_index = export_yen_values.get(date_key)
                import_index = import_yen_values.get(date_key)

                if export_index is not None and import_index is not None and import_index != 0:
                    # 交易条件 = 輸出物価指数 / 輸入物価指数 × 100
                    terms_of_trade = round((export_index / import_index) * 100, 2)

                    series_data.append({
                        "date": date_key,
                        "value": terms_of_trade,
                        "terms_of_trade": terms_of_trade,
                        "export_price_index": round(export_index, 2),
                        "import_price_index": round(import_index, 2),
                    })

            # 過去15年分にフィルタ
            if series_data:
                cutoff_year = datetime.now().year - 15
                cutoff_date = f"{cutoff_year}-01-01"
                series_data = [point for point in series_data if point["date"] >= cutoff_date]

            print(f"Processed Terms of Trade data: {len(series_data)} data points")
            if series_data:
                print(f"Latest data: {series_data[-1]}")

            return series_data

        except Exception as e:
            print(f"Error parsing CGPI CSV: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日ベース）"""
        try:
            return self.fmp_utils["should_refresh"](
                self.INDICATOR_ID,
                last_updated_str
            )
        except Exception as e:
            print(f"Error in _should_refresh: {e}")
            # フォールバック: 発表期間内なら更新
            try:
                last_updated = datetime.fromisoformat(last_updated_str)
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=JST)

                now = datetime.now(JST)
                today = now.date()

                if 10 <= today.day <= 18:
                    release_time = datetime(
                        today.year, today.month, today.day,
                        self.RELEASE_HOUR_JST, self.RELEASE_MINUTE_JST,
                        tzinfo=JST
                    )
                    if now >= release_time and last_updated < release_time:
                        return True

                return False
            except Exception:
                return True

    def _calculate_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を計算（フォールバック用）"""
        try:
            now = datetime.now(JST)
            today = now.date()

            this_month_10th = date(today.year, today.month, 10)

            if today > this_month_10th or (today == this_month_10th and now.hour >= self.RELEASE_HOUR_JST and now.minute >= self.RELEASE_MINUTE_JST):
                if today.month == 12:
                    next_release_date = date(today.year + 1, 1, 10)
                else:
                    next_release_date = date(today.year, today.month + 1, 10)
            else:
                next_release_date = this_month_10th

            return {
                "date": next_release_date.strftime("%Y-%m-%d"),
                "datetime_jst": f"{next_release_date.strftime('%Y-%m-%d')}T08:50:00+09:00",
                "time_jst": "08:50",
                "label": f"企業物価指数（交易条件含む）- {next_release_date.strftime('%Y/%m/%d')} 8:50 JST（予定）"
            }

        except Exception as e:
            print(f"Error calculating next release: {e}")
            return None

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Japan Terms of Trade",
            "source": "Bank of Japan (BOJ)",
            "url": self.CGPI_ZIP_URL,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
japan_terms_of_trade_service = JapanTermsOfTradeService()
