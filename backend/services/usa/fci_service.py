"""
FCI-G（金融情勢指数）サービス
Federal Reserve から FCI-G データを取得

データソース:
- FCI-G Baseline (3-year): https://www.federalreserve.gov/econres/notes/feds-notes/fci_g_public_monthly_3yr.csv
- FCI-G One-year lookback: https://www.federalreserve.gov/econres/notes/feds-notes/fci_g_public_monthly_1yr.csv

更新スケジュール:
- 月次更新（毎月末のデータが翌月初に公開）
- 具体的な発表日時は不定期のため、TTL方式（1日1回チェック）

キャッシュ方式: TTL方式（24時間）
スケジューラ: 毎日6:00 JSTに更新チェック
"""
import csv
from datetime import datetime, date
from io import StringIO
from typing import Dict, List, Any, Optional

import requests

from core.redis_client import redis_client


class FCIService:
    """FCI-G サービス"""

    BASELINE_URL = "https://www.federalreserve.gov/econres/notes/feds-notes/fci_g_public_monthly_3yr.csv"
    ONEYEAR_URL = "https://www.federalreserve.gov/econres/notes/feds-notes/fci_g_public_monthly_1yr.csv"

    CACHE_KEY_BASELINE = "fed:fci:baseline"
    CACHE_KEY_ONEYEAR = "fed:fci:oneyear"

    # キャッシュTTL: 24時間（秒）
    CACHE_TTL = 24 * 60 * 60

    def get_fci_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        FCI-G データを取得（両シリーズ）

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "baseline": {"data": [...], "latest": {...}},
                "oneyear": {"data": [...], "latest": {...}},
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # キャッシュチェック
        if not force_refresh:
            cached_baseline = redis_client.get(self.CACHE_KEY_BASELINE)
            cached_oneyear = redis_client.get(self.CACHE_KEY_ONEYEAR)

            if cached_baseline and cached_oneyear:
                return {
                    "baseline": {
                        "data": cached_baseline.get("data", []),
                        "latest": cached_baseline.get("latest")
                    },
                    "oneyear": {
                        "data": cached_oneyear.get("data", []),
                        "latest": cached_oneyear.get("latest")
                    },
                    "cached": True,
                    "source": "redis",
                    "last_updated": cached_baseline.get("last_updated")
                }

        # 外部APIから取得
        baseline_data = self._fetch_csv_data(self.BASELINE_URL, "baseline")
        oneyear_data = self._fetch_csv_data(self.ONEYEAR_URL, "oneyear")

        now = datetime.now().isoformat()

        if baseline_data:
            baseline_latest = baseline_data[-1] if baseline_data else None
            cache_payload = {
                "data": baseline_data,
                "latest": baseline_latest,
                "last_updated": now
            }
            redis_client.set(self.CACHE_KEY_BASELINE, cache_payload, expire=self.CACHE_TTL)

        if oneyear_data:
            oneyear_latest = oneyear_data[-1] if oneyear_data else None
            cache_payload = {
                "data": oneyear_data,
                "latest": oneyear_latest,
                "last_updated": now
            }
            redis_client.set(self.CACHE_KEY_ONEYEAR, cache_payload, expire=self.CACHE_TTL)

        return {
            "baseline": {
                "data": baseline_data or [],
                "latest": baseline_data[-1] if baseline_data else None
            },
            "oneyear": {
                "data": oneyear_data or [],
                "latest": oneyear_data[-1] if oneyear_data else None
            },
            "cached": False,
            "source": "api",
            "last_updated": now
        }

    def _fetch_csv_data(
        self,
        url: str,
        series_name: str
    ) -> List[Dict[str, Any]]:
        """
        CSVデータを取得してパース

        Args:
            url: CSVファイルのURL
            series_name: シリーズ名（baseline/oneyear）

        Returns:
            [{"date": "YYYY-MM-DD", "value": float}, ...]
        """
        try:
            print(f"Fetching FCI-G {series_name} from {url}...")

            response = requests.get(url, timeout=30)
            response.raise_for_status()

            csv_content = response.text
            reader = csv.reader(StringIO(csv_content))

            # ヘッダー行をスキップ
            headers = next(reader)

            # FCI-G Index列のインデックスを特定（通常は2列目）
            fci_column_index = 1  # デフォルト
            for i, header in enumerate(headers):
                header_lower = header.strip().lower()
                if 'fci-g index' in header_lower or 'fci_g' in header_lower:
                    fci_column_index = i
                    break

            result = []
            for row in reader:
                if len(row) <= fci_column_index:
                    continue

                date_str = row[0].strip()
                value_str = row[fci_column_index].strip()

                if not date_str or not value_str:
                    continue

                try:
                    value = float(value_str)
                    result.append({
                        "date": date_str,
                        "value": round(value, 4)
                    })
                except (ValueError, TypeError):
                    continue

            # 日付昇順にソート
            result.sort(key=lambda x: x["date"])

            print(f"Fetched {len(result)} records for FCI-G {series_name}")
            return result

        except Exception as e:
            print(f"Error fetching FCI-G {series_name}: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_baseline(self, force_refresh: bool = False) -> Dict[str, Any]:
        """FCI-G Baseline (3-year) データのみ取得"""
        if not force_refresh:
            cached = redis_client.get(self.CACHE_KEY_BASELINE)
            if cached:
                return {
                    "data": cached.get("data", []),
                    "latest": cached.get("latest"),
                    "cached": True,
                    "source": "redis",
                    "last_updated": cached.get("last_updated")
                }

        data = self._fetch_csv_data(self.BASELINE_URL, "baseline")
        now = datetime.now().isoformat()

        if data:
            latest = data[-1] if data else None
            cache_payload = {
                "data": data,
                "latest": latest,
                "last_updated": now
            }
            redis_client.set(self.CACHE_KEY_BASELINE, cache_payload, expire=self.CACHE_TTL)

            return {
                "data": data,
                "latest": latest,
                "cached": False,
                "source": "api",
                "last_updated": now
            }

        return {
            "data": [],
            "latest": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def get_oneyear(self, force_refresh: bool = False) -> Dict[str, Any]:
        """FCI-G One-year lookback データのみ取得"""
        if not force_refresh:
            cached = redis_client.get(self.CACHE_KEY_ONEYEAR)
            if cached:
                return {
                    "data": cached.get("data", []),
                    "latest": cached.get("latest"),
                    "cached": True,
                    "source": "redis",
                    "last_updated": cached.get("last_updated")
                }

        data = self._fetch_csv_data(self.ONEYEAR_URL, "oneyear")
        now = datetime.now().isoformat()

        if data:
            latest = data[-1] if data else None
            cache_payload = {
                "data": data,
                "latest": latest,
                "last_updated": now
            }
            redis_client.set(self.CACHE_KEY_ONEYEAR, cache_payload, expire=self.CACHE_TTL)

            return {
                "data": data,
                "latest": latest,
                "cached": False,
                "source": "api",
                "last_updated": now
            }

        return {
            "data": [],
            "latest": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        result1 = redis_client.delete(self.CACHE_KEY_BASELINE)
        result2 = redis_client.delete(self.CACHE_KEY_ONEYEAR)
        return result1 or result2

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        baseline_exists = redis_client.exists(self.CACHE_KEY_BASELINE)
        oneyear_exists = redis_client.exists(self.CACHE_KEY_ONEYEAR)

        baseline_ttl = redis_client.ttl(self.CACHE_KEY_BASELINE) if baseline_exists else -1
        oneyear_ttl = redis_client.ttl(self.CACHE_KEY_ONEYEAR) if oneyear_exists else -1

        baseline_data = redis_client.get(self.CACHE_KEY_BASELINE) if baseline_exists else None
        oneyear_data = redis_client.get(self.CACHE_KEY_ONEYEAR) if oneyear_exists else None

        return {
            "baseline": {
                "cache_key": self.CACHE_KEY_BASELINE,
                "exists": baseline_exists,
                "ttl_seconds": baseline_ttl,
                "last_updated": baseline_data.get("last_updated") if baseline_data else None,
                "data_count": len(baseline_data.get("data", [])) if baseline_data else 0,
                "latest": baseline_data.get("latest") if baseline_data else None
            },
            "oneyear": {
                "cache_key": self.CACHE_KEY_ONEYEAR,
                "exists": oneyear_exists,
                "ttl_seconds": oneyear_ttl,
                "last_updated": oneyear_data.get("last_updated") if oneyear_data else None,
                "data_count": len(oneyear_data.get("data", [])) if oneyear_data else 0,
                "latest": oneyear_data.get("latest") if oneyear_data else None
            }
        }

    def get_latest_values(self) -> Dict[str, Any]:
        """両シリーズの最新値を取得"""
        result = self.get_fci_data()
        return {
            "baseline": result.get("baseline", {}).get("latest"),
            "oneyear": result.get("oneyear", {}).get("latest")
        }


# シングルトンインスタンス
fci_service = FCIService()
