"""
RBA政策金利（Cash Rate Target）サービス

指標:
- RBA Cash Rate Target（オーストラリア準備銀行キャッシュレート目標）

データソース:
- RBA Statistical Tables F1 (Money Market Rates - Daily)
- https://www.rba.gov.au/statistics/tables/csv/f1-data.csv

発表スケジュール:
- 年11回（2月除く毎月第1火曜、12月は第2火曜の場合あり）
- 発表時刻: 14:30 シドニー時間

キャッシュ方式:
- 通常時: RBA CSVから週次取得
- 発表日: FMPから発表値を検出し更新
"""
import json
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client
from services.australia.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")
SYDNEY = ZoneInfo("Australia/Sydney")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "australia" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "au_rba_rate_cache.json"


class RbaPolicyRateService:
    """RBA政策金利サービス"""

    DATA_CACHE_KEY = "australia:au_rba_rate:data"
    ECONALPHA_ID = "au_rba_rate"
    FMP_COUNTRY = "AU"
    FMP_EVENT_PATTERN = "RBA Interest Rate Decision"

    # RBA Statistical Tables F1 (Daily Money Market Rates)
    RBA_CSV_URL = "https://www.rba.gov.au/statistics/tables/csv/f1-data.csv?v=2026-02-15-00-56-56"
    # Cash Rate Target の Series ID
    SERIES_ID = "FIRMMCRTD"

    def __init__(self):
        pass

    def get_au_rba_rate_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """RBA政策金利データを取得"""
        # 次回発表日を取得
        next_release = get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY)

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # データソースから取得
        result = self._load_from_source()
        if result:
            # 最新値を取得
            latest = result[-1] if result else None
            from services.usa.fmp_next_release_utils import guarded_last_updated
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Reserve Bank of Australia",
                    "indicator": "Cash Rate Target",
                    "description": "RBA政策金利（キャッシュレート目標）",
                    "unit": "%",
                    "series_id": "FIRMMCRTD",
                    "table": "F1 - Money Market Rates",
                },
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "api",
                "last_updated": last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_source(self) -> List[Dict[str, Any]]:
        """RBA CSVからCash Rate Targetデータを取得"""
        try:
            print(f"[RbaPolicyRate] Fetching data from: {self.RBA_CSV_URL}")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            resp = requests.get(self.RBA_CSV_URL, headers=headers, timeout=60)
            resp.raise_for_status()

            return self._parse_rba_csv(resp.text)

        except Exception as e:
            print(f"[RbaPolicyRate] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_rba_csv(self, csv_text: str) -> List[Dict[str, Any]]:
        """RBA CSVを解析してCash Rate Targetを抽出（Series ID: FIRMMCRTD）"""
        lines = csv_text.strip().split("\n")

        # Series ID行を検索してFIRMMCRTDの列インデックスを特定
        target_col = None
        series_id_row_idx = None
        data_start_idx = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.split(",")

            # "Series ID" で始まる行からFIRMMCRTDの列を特定
            if parts[0].strip() == "Series ID":
                series_id_row_idx = i
                for col_idx, sid in enumerate(parts):
                    if sid.strip() == self.SERIES_ID:
                        target_col = col_idx
                        print(f"[RbaPolicyRate] Found {self.SERIES_ID} at column {target_col}")
                        break
                continue

            # DD-MMM-YYYY形式の日付で始まる行を探す
            if len(parts) >= 2 and len(parts[0]) >= 9:
                try:
                    datetime.strptime(parts[0].strip(), "%d-%b-%Y")
                    data_start_idx = i
                    break
                except ValueError:
                    continue

        if target_col is None:
            print(f"[RbaPolicyRate] Could not find Series ID '{self.SERIES_ID}' in CSV")
            return []

        if data_start_idx == 0:
            print("[RbaPolicyRate] Could not find data section in CSV")
            return []

        result = []

        for line in lines[data_start_idx:]:
            stripped = line.strip()
            if not stripped:
                continue

            parts = stripped.split(",")
            if len(parts) <= target_col:
                continue

            date_str = parts[0].strip()
            value_str = parts[target_col].strip()

            # 空値をスキップ
            if not value_str:
                continue

            try:
                dt = datetime.strptime(date_str, "%d-%b-%Y")
                formatted_date = dt.strftime("%Y-%m-%d")
                value = float(value_str)

                result.append({
                    "date": formatted_date,
                    "value": value,
                })
            except (ValueError, TypeError):
                continue

        # 日付でソート
        result.sort(key=lambda x: x["date"])

        print(f"[RbaPolicyRate] Loaded {len(result)} daily records")
        if result:
            print(f"[RbaPolicyRate] Date range: {result[0]['date']} to {result[-1]['date']}")
            latest = result[-1]
            print(f"[RbaPolicyRate] Latest: {latest['date']} = {latest['value']}%")

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日ベース）"""
        return should_refresh_by_pattern(
            self.FMP_EVENT_PATTERN,
            last_updated_str,
            country=self.FMP_COUNTRY
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[RbaPolicyRate] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[RbaPolicyRate] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "RBA Cash Rate Target",
            "source": "Reserve Bank of Australia",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
rba_policy_rate_service = RbaPolicyRateService()
