"""
Zillow家賃指数サービス
Zillow Observed Rent Index (ZORI) をCSVから取得

指標:
- Zillow Observed Rent Index (ZORI): 全米の観測家賃指数（前年比）

データソース:
- CSV: Zillow Research Data (Metro_zori_uc_sfrcondomfr_sm_month.csv)
- URL: https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv

発表スケジュール:
- 毎月15日前後に更新

キャッシュ方式: 月次更新（15日以降1日1回チェック、更新があれば反映）
"""
import json
import time
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
ZILLOW_RENT_INDEX_CACHE_FILE = CACHE_DIR / "zillow_rent_index_cache.json"

# Zillow CSV URL
ZILLOW_CSV_URL = "https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv"


class ZillowRentIndexService:
    """Zillow家賃指数サービス"""

    CACHE_KEY = "inflation:zillow_rent_index:data"

    def __init__(self):
        pass

    def get_zillow_rent_index_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Zillow家賃指数データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "yoy": float}, ...],
                "latest": {"date": "YYYY-MM-DD", "yoy": float},
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ZillowのCSVからデータを取得
        zillow_data = self._fetch_zillow_csv()

        if zillow_data:
            latest = zillow_data[-1] if zillow_data else None

            cache_payload = {
                "data": zillow_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": zillow_data,
                "latest": latest,
                "cached": False,
                "source": "Zillow CSV",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_zillow_csv(self) -> List[Dict[str, Any]]:
        """
        ZillowのCSVから家賃指数データを取得し、前年比を計算

        CSV形式: RegionID, SizeRank, RegionName, RegionType, StateName, 2015-01, 2015-02, ...
        United Statesの行から全米データを抽出
        """
        try:
            print("Fetching Zillow CSV data...")

            # キャッシュバスティング用のタイムスタンプを追加
            timestamp = int(time.time())
            url = f"{ZILLOW_CSV_URL}?t={timestamp}"

            response = requests.get(url, timeout=60)
            response.raise_for_status()

            csv_text = response.text
            lines = [line for line in csv_text.split('\n') if line.strip()]

            if len(lines) < 2:
                print("Invalid CSV format")
                return []

            # ヘッダー行を解析
            headers = [h.strip().replace('"', '') for h in lines[0].split(',')]
            print(f"Zillow CSV headers count: {len(headers)}")

            # United States行を検索
            us_row = None
            for line in lines[1:]:
                if 'United States' in line:
                    us_row = line
                    break

            if not us_row:
                print("United States data not found in CSV")
                return []

            # 値を解析
            values = [v.strip().replace('"', '') for v in us_row.split(',')]
            print(f"Found United States row with {len(values)} values")

            # 日付列（インデックス5以降）からデータを抽出
            raw_data = []
            for i in range(5, min(len(headers), len(values))):
                date_str = headers[i]
                value_str = values[i]

                if date_str and value_str and value_str != '' and value_str.lower() != 'null':
                    try:
                        value = float(value_str)
                        # 日付を解析（YYYY-MM形式を想定）
                        if '-' in date_str:
                            parts = date_str.split('-')
                            if len(parts) >= 2:
                                year = int(parts[0])
                                month = int(parts[1])
                                formatted_date = f"{year}-{month:02d}-01"
                                raw_data.append({
                                    "date": formatted_date,
                                    "value": value
                                })
                    except (ValueError, TypeError):
                        continue

            if not raw_data:
                print("No valid data points found in Zillow CSV")
                return []

            # 日付順にソート
            raw_data.sort(key=lambda x: x["date"])
            print(f"Parsed {len(raw_data)} raw data points from Zillow CSV")

            # 前年比を計算（12か月前との比較）
            yoy_data = []
            for i in range(12, len(raw_data)):
                current = raw_data[i]
                year_ago = raw_data[i - 12]

                if current["value"] and year_ago["value"] and year_ago["value"] != 0:
                    yoy_change = ((current["value"] - year_ago["value"]) / year_ago["value"]) * 100
                    yoy_data.append({
                        "date": current["date"],
                        "yoy": round(yoy_change, 2)
                    })

            print(f"Calculated {len(yoy_data)} YoY data points for Zillow")
            return yoy_data

        except Exception as e:
            print(f"Error fetching Zillow CSV: {e}")
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        Zillowは毎月15日以降に更新されるため:
        - 15日以降: 1日1回チェック
        - 15日未満: スキップ（前月のデータが最新）

        ただし、最新データの月が現在の月より古い場合は更新をチェック
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)

            # 日付が変わっていない場合はスキップ
            if last_updated.date() >= now.date():
                return False

            # 15日以降の場合、または月が変わった場合は更新チェック
            if now.day >= 15 or last_updated.month != now.month:
                return True

            return False
        except Exception:
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not ZILLOW_RENT_INDEX_CACHE_FILE.exists():
                return None
            with open(ZILLOW_RENT_INDEX_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存する"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(ZILLOW_RENT_INDEX_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {ZILLOW_RENT_INDEX_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        exists = redis_client.exists(self.CACHE_KEY)
        cached_data = redis_client.get(self.CACHE_KEY) if exists else None

        return {
            "indicator": "Zillow Observed Rent Index (ZORI)",
            "source": "Zillow CSV",
            "cache_key": self.CACHE_KEY,
            "exists": exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "file_cache_exists": ZILLOW_RENT_INDEX_CACHE_FILE.exists()
        }


# シングルトンインスタンス
zillow_rent_index_service = ZillowRentIndexService()
