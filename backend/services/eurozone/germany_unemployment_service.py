"""
ドイツ失業率サービス
Deutsche Bundesbank APIからドイツ失業率データを取得

指標:
- Unemployment Rate (季節調整済み)
- BBDL1/M.DE.Y.UNE.UBA000.A0000.A01.D00.0.R00.A

データソース:
- Deutsche Bundesbank API

発表スケジュール:
- 毎月27日〜翌月6日 17:55-18:05 CET

キャッシュ方式: FMP発表日時ベース判定方式
"""
import csv
import json
import requests
from io import StringIO
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.eurozone.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "germany_unemployment_cache.json"


class GermanyUnemploymentService:
    """ドイツ失業率サービス (Bundesbank API)"""

    DATA_CACHE_KEY = "eurozone:germany_unemployment:data"
    ECONALPHA_ID = "germany_unemployment"
    FMP_EVENT_PATTERN = "Unemployment Rate"
    FMP_COUNTRY = "DE"

    # Bundesbank API設定
    BUNDESBANK_API_BASE = "https://api.statistiken.bundesbank.de/rest/download"

    # Series key for unemployment rate
    # BBDL1: Bundesbank Data Library
    # M: Monthly
    # DE: Germany
    # Y: Registered Unemployment
    # UNE: Unemployment
    # UBA000: National
    # A0000: Total
    # A01: Seasonally adjusted
    # D00: Original values
    # 0: No flags
    # R00: Rate
    # A: Level
    SERIES_KEY = "BBDL1/M.DE.Y.UNE.UBA000.A0000.A01.D00.0.R00.A"

    def __init__(self):
        pass

    def get_germany_unemployment_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """失業率データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "unemployment_rate": cached_data.get("unemployment_rate", []),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # Bundesbank APIから取得
        api_result = self._fetch_from_bundesbank()
        if api_result:
            next_release = get_next_release_by_pattern(
                self.FMP_EVENT_PATTERN,
                country=self.FMP_COUNTRY
            )

            cache_payload = {
                "unemployment_rate": api_result,
                "metadata": {
                    "source": "Deutsche Bundesbank",
                    "series": self.SERIES_KEY,
                    "indicator": "Unemployment Rate - Germany",
                    "unit": "Percent",
                    "adjustment": "Seasonally adjusted",
                    "description": "失業率（ドイツ、季節調整済み）",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "unemployment_rate": api_result,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "bundesbank_api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "unemployment_rate": file_cache.get("unemployment_rate", []),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "unemployment_rate": [],
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_from_bundesbank(self, start_date: str = "2015-01") -> Optional[List[Dict]]:
        """Bundesbank APIからデータを取得"""
        url = f"{self.BUNDESBANK_API_BASE}/{self.SERIES_KEY}"

        params = {
            "format": "csv",
            "lang": "de"
        }

        try:
            print(f"[GermanyUnemployment] Fetching data from Bundesbank: {self.SERIES_KEY}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            # CSVをパース
            csv_content = response.text
            data = self._parse_bundesbank_csv(csv_content)

            # start_date以降のデータをフィルタ
            if start_date:
                start_date_formatted = f"{start_date}-01"
                data = [d for d in data if d["date"] >= start_date_formatted]

            print(f"[GermanyUnemployment] Fetched {len(data)} data points")
            return data

        except requests.exceptions.RequestException as e:
            print(f"[GermanyUnemployment] Request error: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[GermanyUnemployment] Parse error: {e}")
            return None

    def _parse_bundesbank_csv(self, csv_content: str) -> List[Dict]:
        """
        Bundesbank CSVフォーマットをパース

        Args:
            csv_content: CSVコンテンツ文字列

        Returns:
            日付と値を含むデータポイントのリスト
        """
        result = []

        # BOMがあれば除去
        csv_content = csv_content.lstrip('\ufeff')

        # CSVをパース
        reader = csv.reader(StringIO(csv_content), delimiter=';')

        # メタデータ行をスキップ（日付パターンを持つデータ行を見つけるまで）
        data_started = False
        for row in reader:
            if not row or len(row) < 2:
                continue

            # データ行かどうかチェック（YYYY-MMフォーマット）
            date_str = row[0].strip()
            if not data_started:
                # 日付パターン YYYY-MM を探す
                if len(date_str) == 7 and '-' in date_str:
                    try:
                        year, month = date_str.split('-')
                        if year.isdigit() and month.isdigit():
                            data_started = True
                    except Exception:
                        continue

            if data_started and len(date_str) == 7 and '-' in date_str:
                try:
                    # 値をパース（ドイツ式小数点形式はカンマを使用）
                    value_str = row[1].strip().replace(',', '.')
                    value = float(value_str)

                    # 日付を月の初日に変換
                    date_formatted = f"{date_str}-01"

                    result.append({
                        "date": date_formatted,
                        "value": round(value, 2)
                    })
                except (ValueError, IndexError):
                    continue

        # 日付でソート
        result.sort(key=lambda x: x["date"])

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
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
            print(f"[GermanyUnemployment] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[GermanyUnemployment] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Germany Unemployment Rate",
            "source": "Bundesbank API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("unemployment_rate", [])) if cached_data else 0,
            "next_release": get_next_release_by_pattern(
                self.FMP_EVENT_PATTERN,
                country=self.FMP_COUNTRY
            ),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
germany_unemployment_service = GermanyUnemploymentService()
