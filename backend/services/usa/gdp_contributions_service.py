"""
GDP寄与度サービス
FRED APIから5項目の寄与度データを取得

シリーズID:
- DPCERY2Q224SBEA: 個人消費 (PCE) 寄与度
- A822RY2Q224SBEA: 政府支出・投資 寄与度
- A006RY2Q224SBEA: 民間投資 (GPDI) 寄与度
- A020RY2Q224SBEA: 輸出 寄与度
- A021RY2Q224SBEA: 輸入 寄与度

キャッシュ方式: last_updated判定（TTLなし）
更新タイミング: BEA発表スケジュールに基づいて自動更新
"""
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from core.redis_client import redis_client

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# FRED シリーズID（GDP寄与度5項目）
GDP_CONTRIBUTION_SERIES = {
    "pce": {
        "series_id": "DPCERY2Q224SBEA",
        "name": "個人消費 (PCE)",
        "name_en": "Personal Consumption",
        "color": "#1890ff"
    },
    "gpdi": {
        "series_id": "A006RY2Q224SBEA",
        "name": "民間投資 (GPDI)",
        "name_en": "Private Investment",
        "color": "#52c41a"
    },
    "exports": {
        "series_id": "A020RY2Q224SBEA",
        "name": "輸出",
        "name_en": "Exports",
        "color": "#722ed1"
    },
    "imports": {
        "series_id": "A021RY2Q224SBEA",
        "name": "輸入",
        "name_en": "Imports",
        "color": "#fa541c"
    },
    "government": {
        "series_id": "A822RY2Q224SBEA",
        "name": "政府支出・投資",
        "name_en": "Government",
        "color": "#faad14"
    }
}


class GDPContributionsService:
    """GDP寄与度サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    CACHE_KEY = "fred:series:gdp_contributions"
    # フォールバックTTL: BEA発表直後のFRED反映ラグでstaleキャッシュを掴んだ場合の救済策。
    MAX_CACHE_AGE_DAYS = 7

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def _is_cache_expired(self, cached_data: Dict[str, Any]) -> bool:
        last_updated = cached_data.get("last_updated")
        if not last_updated:
            return True
        try:
            last_dt = datetime.fromisoformat(last_updated)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=JST)
            age = datetime.now(JST) - last_dt
            return age.total_seconds() > self.MAX_CACHE_AGE_DAYS * 86400
        except Exception:
            return True

    def fetch_gdp_contributions(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        GDP寄与度（5項目）を取得

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            end_date: 終了日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [
                    {
                        "date": "YYYY-MM-DD",
                        "quarter": "2024Q1",
                        "pce": float,
                        "gpdi": float,
                        "exports": float,
                        "imports": float,
                        "government": float,
                        "total": float
                    },
                    ...
                ],
                "series_info": {...},
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # キャッシュチェック（7日経過したらフォールバックで再取得）
        cached_data = redis_client.get(self.CACHE_KEY)
        if not force_refresh and cached_data and not self._is_cache_expired(cached_data):
            return {
                "data": cached_data.get("data", []),
                "series_info": cached_data.get("series_info", {}),
                "cached": True,
                "source": "redis",
                "last_updated": cached_data.get("last_updated")
            }

        # 外部APIから取得（並列処理）
        api_data = self._fetch_all_series(start_date, end_date)

        if api_data:
            cache_payload = {
                "data": api_data["data"],
                "series_info": api_data["series_info"],
                "last_updated": datetime.now(JST).isoformat()
            }
            # TTLなし（last_updated判定方式）
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)

            return {
                "data": api_data["data"],
                "series_info": api_data["series_info"],
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # API失敗時: 期限切れでも既存キャッシュを返す（データ欠落防止）
        if cached_data:
            return {
                "data": cached_data.get("data", []),
                "series_info": cached_data.get("series_info", {}),
                "cached": True,
                "source": "redis_stale",
                "last_updated": cached_data.get("last_updated")
            }

        return {
            "data": [],
            "series_info": {},
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_all_series(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """全シリーズを並列で取得し、結合する"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return None

            # デフォルト期間（1990年から）
            if not start_date:
                start_date = "1990-01-01"
            if not end_date:
                end_date = datetime.now().strftime("%Y-%m-%d")

            print(f"Fetching GDP contributions from FRED...")

            series_data = {}

            # 並列で各シリーズを取得
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {}
                for key, info in GDP_CONTRIBUTION_SERIES.items():
                    future = executor.submit(
                        self._fetch_single_series,
                        info["series_id"],
                        start_date,
                        end_date
                    )
                    futures[future] = key

                for future in as_completed(futures):
                    key = futures[future]
                    try:
                        series_data[key] = future.result()
                    except Exception as e:
                        print(f"Error fetching {key}: {e}")
                        series_data[key] = {}

            # データを結合（日付ベースでマージ）
            merged_data = self._merge_series_data(series_data)

            # シリーズ情報を構築
            series_info = {}
            for key, info in GDP_CONTRIBUTION_SERIES.items():
                series_info[key] = {
                    "series_id": info["series_id"],
                    "name": info["name"],
                    "name_en": info["name_en"],
                    "color": info["color"]
                }

            print(f"Fetched {len(merged_data)} quarters of GDP contributions")

            return {
                "data": merged_data,
                "series_info": series_info
            }

        except Exception as e:
            print(f"Error fetching GDP contributions: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_single_series(
        self,
        series_id: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, float]:
        """単一シリーズをFRED APIから取得"""
        try:
            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date,
                "observation_end": end_date,
                "sort_order": "asc"
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            result = {}
            for obs in data.get("observations", []):
                if obs.get("value") and obs["value"] != ".":
                    try:
                        result[obs["date"]] = round(float(obs["value"]), 2)
                    except (ValueError, TypeError):
                        continue

            return result

        except Exception as e:
            print(f"Error fetching series {series_id}: {e}")
            return {}

    def _merge_series_data(
        self,
        series_data: Dict[str, Dict[str, float]]
    ) -> List[Dict[str, Any]]:
        """各シリーズのデータを日付でマージ"""
        # 全ての日付を収集
        all_dates = set()
        for data in series_data.values():
            all_dates.update(data.keys())

        # 日付でソート
        sorted_dates = sorted(all_dates)

        # 結合データを構築
        merged = []
        for date_str in sorted_dates:
            row = {
                "date": date_str,
                "quarter": self._format_quarter(date_str)
            }

            total = 0.0
            has_data = False

            for key in GDP_CONTRIBUTION_SERIES.keys():
                value = series_data.get(key, {}).get(date_str)
                if value is not None:
                    row[key] = value
                    total += value
                    has_data = True
                else:
                    row[key] = None

            # totalを計算（全項目揃っている場合のみ）
            if has_data:
                row["total"] = round(total, 2)
                merged.append(row)

        return merged

    def _format_quarter(self, date_str: str) -> str:
        """日付を四半期形式に変換"""
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            year = date.year
            quarter = (date.month - 1) // 3 + 1
            return f"{year}Q{quarter}"
        except Exception:
            return date_str

    def get_gdp_contributions(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        GDP寄与度データを取得（エイリアス）

        Returns:
            {
                "data": [...],
                "series_info": {...},
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        return self.fetch_gdp_contributions(force_refresh=force_refresh)

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_exists = redis_client.exists(self.CACHE_KEY)
        ttl = redis_client.ttl(self.CACHE_KEY) if cache_exists else -1

        cached_data = redis_client.get(self.CACHE_KEY) if cache_exists else None

        return {
            "series_ids": {k: v["series_id"] for k, v in GDP_CONTRIBUTION_SERIES.items()},
            "cache_key": self.CACHE_KEY,
            "exists": cache_exists,
            "ttl_seconds": ttl,  # -1 = TTLなし
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "record_count": len(cached_data.get("data", [])) if cached_data else 0
        }

    def get_latest_values(self) -> Optional[Dict[str, Any]]:
        """
        最新のGDP寄与度を取得

        Returns:
            {"date": "YYYY-MM-DD", "quarter": "2024Q4", "pce": ..., ...} or None
        """
        result = self.get_gdp_contributions()
        data = result.get("data", [])
        return data[-1] if data else None


# シングルトンインスタンス
gdp_contributions_service = GDPContributionsService()
