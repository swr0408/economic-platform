"""
ミシガン大学消費者信頼感指数サービス
ミシガン大学 Survey of Consumers からデータを取得

指標:
- Index of Consumer Sentiment (ICS): 消費者信頼感指数

データソース:
- CSV: https://www.sca.isr.umich.edu/files/tbmics.csv
- 次回発表日: https://www.sca.isr.umich.edu/ からスクレイピング

発表スケジュール:
- 毎月2回発表（速報版・確報版）
- 速報版: 毎月第2金曜日 10:00 ET
- 確報版: 毎月最終金曜日 10:00 ET

キャッシュ方式: 発表日時ベース判定方式
"""
import csv
import io
import json
import re
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# データソースURL
MICHIGAN_INDEX_CSV_URL = "https://www.sca.isr.umich.edu/files/tbmics.csv"
MICHIGAN_COMPONENTS_CSV_URL = "https://www.sca.isr.umich.edu/files/tbmiccice.csv"
MICHIGAN_HOMEPAGE_URL = "https://www.sca.isr.umich.edu/"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "michigan_consumer_sentiment_cache.json"

# 月名マッピング
MONTH_MAP = {
    'january': 1,
    'february': 2,
    'march': 3,
    'april': 4,
    'may': 5,
    'june': 6,
    'july': 7,
    'august': 8,
    'september': 9,
    'october': 10,
    'november': 11,
    'december': 12
}


class MichiganConsumerSentimentService:
    """ミシガン大学消費者信頼感指数サービス"""

    DATA_CACHE_KEY = "michigan:consumer_sentiment:data"
    ECONALPHA_ID = "michigan_consumer_sentiment"  # FMPマッピング用ID

    def __init__(self):
        pass

    def get_michigan_consumer_sentiment_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        ミシガン大学消費者信頼感指数データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
                "components": [{"date": "YYYY-MM-DD", "current": float, "expected": float}, ...],
                "latest": {...},
                "latest_components": {...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "components": cached_data.get("components", []),
                        "latest": cached_data.get("latest"),
                        "latest_components": cached_data.get("latest_components"),
                        "next_release": get_next_release_from_fmp('michigan_consumer_sentiment'),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    # Redisにも保存
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)

                    return {
                        "data": file_cache.get("data", []),
                        "components": file_cache.get("components", []),
                        "latest": file_cache.get("latest"),
                        "latest_components": file_cache.get("latest_components"),
                        "next_release": get_next_release_from_fmp('michigan_consumer_sentiment'),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # CSVからデータを取得（指数と構成要素の両方）
        index_data = self._fetch_index_from_csv()
        components_data = self._fetch_components_from_csv()

        if index_data:
            latest = index_data[-1] if index_data else None
            latest_components = components_data[-1] if components_data else None

            cache_payload = {
                "data": index_data,
                "components": components_data,
                "latest": latest,
                "latest_components": latest_components,
                "latest_data_date": latest["date"] if latest else None,
                "last_updated": datetime.now(JST).isoformat()
            }
            # TTLなし（発表日時ベース判定方式）
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            # ファイルにも保存
            self._save_file_cache(cache_payload)

            return {
                "data": index_data,
                "components": components_data,
                "latest": latest,
                "latest_components": latest_components,
                "next_release": get_next_release_from_fmp('michigan_consumer_sentiment'),
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "components": file_cache.get("components", []),
                "latest": file_cache.get("latest"),
                "latest_components": file_cache.get("latest_components"),
                "next_release": get_next_release_from_fmp('michigan_consumer_sentiment'),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "components": [],
            "latest": None,
            "latest_components": None,
            "next_release": get_next_release_from_fmp('michigan_consumer_sentiment'),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_index_from_csv(self) -> List[Dict[str, Any]]:
        """ミシガン大学のCSVから指数データ（ICS_ALL）を取得"""
        try:
            print("Fetching Michigan Consumer Sentiment Index from CSV...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }

            response = requests.get(MICHIGAN_INDEX_CSV_URL, headers=headers, timeout=30)
            response.raise_for_status()

            # CSVを読み込み（BOMを考慮）
            csv_text = response.content.decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(csv_text))

            result = []
            for row in reader:
                try:
                    month_str = row.get('Month', '').strip()
                    year_str = row.get('YYYY', '').strip()
                    value_str = row.get('ICS_ALL', '').strip()

                    if not month_str or not year_str or not value_str:
                        continue

                    # 日付を解析
                    date_obj = self._parse_month_year(month_str, year_str)
                    if not date_obj:
                        continue

                    # 値を解析
                    try:
                        value = float(value_str)
                    except ValueError:
                        continue

                    result.append({
                        "date": date_obj.strftime('%Y-%m-%d'),
                        "value": round(value, 1)
                    })

                except Exception as e:
                    print(f"Error processing index row: {e}")
                    continue

            # 日付順にソート（古い順）
            result.sort(key=lambda x: x["date"])

            print(f"Fetched {len(result)} Michigan Consumer Sentiment Index records")
            return result

        except Exception as e:
            print(f"Error fetching Michigan Consumer Sentiment Index data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_components_from_csv(self) -> List[Dict[str, Any]]:
        """ミシガン大学のCSVから構成要素データ（ICC/ICE）を取得"""
        try:
            print("Fetching Michigan Consumer Sentiment Components from CSV...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }

            response = requests.get(MICHIGAN_COMPONENTS_CSV_URL, headers=headers, timeout=30)
            response.raise_for_status()

            # CSVを読み込み（BOMを考慮）
            csv_text = response.content.decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(csv_text))

            result = []
            for row in reader:
                try:
                    month_str = row.get('Month', '').strip()
                    year_str = row.get('YYYY', '').strip()
                    current_str = row.get('ICC', '').strip()
                    expected_str = row.get('ICE', '').strip()

                    if not month_str or not year_str or not current_str:
                        continue

                    # 日付を解析
                    date_obj = self._parse_month_year(month_str, year_str)
                    if not date_obj:
                        continue

                    # 値を解析
                    try:
                        current_value = float(current_str)
                    except ValueError:
                        continue

                    expected_value = None
                    if expected_str:
                        try:
                            expected_value = float(expected_str)
                        except ValueError:
                            pass

                    result.append({
                        "date": date_obj.strftime('%Y-%m-%d'),
                        "current": round(current_value, 1),
                        "expected": round(expected_value, 1) if expected_value is not None else None
                    })

                except Exception as e:
                    print(f"Error processing components row: {e}")
                    continue

            # 日付順にソート（古い順）
            result.sort(key=lambda x: x["date"])

            print(f"Fetched {len(result)} Michigan Consumer Sentiment Components records")
            return result

        except Exception as e:
            print(f"Error fetching Michigan Consumer Sentiment Components data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_month_year(self, month_str: str, year_str: str) -> Optional[datetime]:
        """月と年の文字列から日付オブジェクトを作成"""
        try:
            month_lower = month_str.lower()
            if month_lower not in MONTH_MAP:
                return None

            month_num = MONTH_MAP[month_lower]
            year_num = int(float(year_str))

            return datetime(year_num, month_num, 1)

        except Exception as e:
            print(f"Error parsing date {month_str} {year_str}: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)


    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None

            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Michigan Consumer Sentiment Index",
            "source": "University of Michigan Survey of Consumers",
            "url": MICHIGAN_INDEX_CSV_URL,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
michigan_consumer_sentiment_service = MichiganConsumerSentimentService()
