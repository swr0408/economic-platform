"""
Redfin 全米住宅価格中央値（前年比）サービス

Redfin Data CenterのS3バケットから全米住宅価格中央値の前年比データを取得

指標:
- 全米住宅価格中央値（前年比）

データソース:
- Redfin Data Center (https://www.redfin.com/news/data-center/)
- S3: redfin-public-data.s3.us-west-2.amazonaws.com

発表スケジュール:
- 月次（毎月第3金曜日頃）
- New data will be released monthly during the Friday of the third full week of the month

キャッシュ方式: 月次スケジュールベース（3分方式）
- 第3金曜日にチェック開始
- 以降1日1回チェックし、当月データを取得できたらその月はスキップ
"""
import gzip
import io
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "redfin_median_price_cache.json"

# Redfin S3 データURL
REDFIN_S3_URL = "https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/us_national_market_tracker.tsv000.gz"


class RedfinMedianPriceService:
    """Redfin 全米住宅価格中央値（前年比）サービス"""

    DATA_CACHE_KEY = "housing:redfin_median_price:data"

    # 発表スケジュール（第3金曜日）
    RELEASE_WEEK = 3  # 第3週
    RELEASE_DAY_OF_WEEK = 4  # 金曜日

    def __init__(self):
        pass

    def get_redfin_median_price_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Redfin住宅価格中央値（前年比）データを取得

        Args:
            force_refresh: 強制更新フラグ

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
                "latest": {"date": str, "value": float},
                "next_release": {"date": str, "label": str} | None,
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
                if last_updated_str and not self._should_refresh(last_updated_str, cached_data):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": self._get_next_release(),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ファイルキャッシュチェック
        file_cache = self._load_file_cache()
        if file_cache:
            last_updated_str = file_cache.get("last_updated")
            if not force_refresh and last_updated_str and not self._should_refresh(last_updated_str, file_cache):
                # Redisにも保存
                redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                return {
                    "data": file_cache.get("data", []),
                    "latest": file_cache.get("latest"),
                    "next_release": self._get_next_release(),
                    "cached": True,
                    "source": "file",
                    "last_updated": last_updated_str
                }

        # S3からデータを取得
        api_data = self._fetch_from_s3()

        if api_data:
            latest = api_data[-1] if api_data else None
            latest_data_month = latest["date"][:7] if latest else None  # YYYY-MM形式

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "latest_data_month": latest_data_month,  # 月次更新判定用
                "last_updated": datetime.now(JST).isoformat()
            }

            # キャッシュに保存
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_data,
                "latest": latest,
                "next_release": self._get_next_release(),
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": self._get_next_release(),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": self._get_next_release(),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_s3(self) -> List[Dict[str, Any]]:
        """
        Redfin S3バケットからデータを取得

        Returns:
            [{"date": "YYYY-MM-DD", "value": float}, ...]
        """
        try:
            print("Fetching Redfin data from S3...")

            response = requests.get(REDFIN_S3_URL, timeout=60)
            response.raise_for_status()

            # gzipを解凍
            with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as f:
                content = f.read().decode('utf-8')

            # TSVをパース
            lines = content.strip().split('\n')
            if len(lines) < 2:
                print("No data in Redfin TSV")
                return []

            # ヘッダー行を取得
            header = lines[0].strip('"').split('"\t"')
            header = [h.strip('"') for h in header]

            # 必要なカラムのインデックスを取得
            try:
                period_begin_idx = header.index('PERIOD_BEGIN')
                region_type_idx = header.index('REGION_TYPE')
                property_type_idx = header.index('PROPERTY_TYPE')
                median_sale_price_yoy_idx = header.index('MEDIAN_SALE_PRICE_YOY')
                is_seasonally_adjusted_idx = header.index('IS_SEASONALLY_ADJUSTED')
            except ValueError as e:
                print(f"Required column not found: {e}")
                return []

            # National + All Residential のデータを抽出
            data_map: Dict[str, float] = {}

            for line in lines[1:]:
                if not line.strip():
                    continue

                # タブ区切り、クォート付き
                cols = line.split('\t')
                cols = [c.strip('"') for c in cols]

                if len(cols) <= max(period_begin_idx, region_type_idx, property_type_idx, median_sale_price_yoy_idx):
                    continue

                region_type = cols[region_type_idx].strip()
                property_type = cols[property_type_idx].strip()
                is_seasonally_adjusted = cols[is_seasonally_adjusted_idx].strip().lower()

                # National + All Residential (property_type_id = 1 または "All Residential")
                # 季節調整なしのデータを使用
                if region_type != "national":
                    continue

                # All Residential のデータを優先（property_type が空または "All Residential"）
                if property_type not in ["All Residential", ""]:
                    continue

                # 季節調整なしを優先
                if is_seasonally_adjusted == "true":
                    continue

                period_begin = cols[period_begin_idx]
                yoy_str = cols[median_sale_price_yoy_idx]

                if not yoy_str or yoy_str == "NA":
                    continue

                try:
                    yoy_value = float(yoy_str)
                    # パーセントに変換（元データは小数、例: 0.05 = 5%）
                    yoy_percent = round(yoy_value * 100, 2)

                    # 同じ日付がある場合は上書き（後の方が正確なことが多い）
                    data_map[period_begin] = yoy_percent

                except (ValueError, TypeError):
                    continue

            # 日付順でソート
            result = []
            for date_str in sorted(data_map.keys()):
                result.append({
                    "date": date_str,
                    "value": data_map[date_str]
                })

            print(f"Fetched {len(result)} records from Redfin S3")
            return result

        except Exception as e:
            print(f"Error fetching Redfin data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str, cached_data: Dict[str, Any]) -> bool:
        """
        キャッシュを更新すべきかどうかを判定（3分方式）

        月次スケジュールベース:
        1. 第3金曜日以降にチェック開始
        2. 当月のデータが取得できていれば、その月はスキップ
        3. 当月のデータがまだない場合、1日1回チェック
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # キャッシュに保存されている最新データの月
            latest_data_month = cached_data.get("latest_data_month")

            # 現在の月を取得
            current_month = now.strftime("%Y-%m")

            # 第3金曜日を計算
            third_friday = self._get_third_friday(now.year, now.month)

            # 第3金曜日の9:00 ET = 第3金曜日の22:00 JST（翌日）頃
            # 簡略化: 第3金曜日の日本時間23:00以降にチェック開始
            release_datetime_jst = datetime(
                third_friday.year, third_friday.month, third_friday.day,
                23, 0, 0, tzinfo=JST
            )

            # まだ第3金曜日の23:00に達していない場合は更新不要
            if now < release_datetime_jst:
                return False

            # 当月のデータがすでにある場合はスキップ
            if latest_data_month and latest_data_month >= current_month:
                return False

            # 最終更新から24時間以上経過していれば更新
            elapsed_hours = (now - last_updated).total_seconds() / 3600
            if elapsed_hours >= 24:
                return True

            # 発表時刻から3分以内で、最終更新が発表時刻より前なら更新（3分方式）
            if last_updated < release_datetime_jst:
                update_window_end = release_datetime_jst + timedelta(minutes=3)
                if now <= update_window_end:
                    return True
                # 3分経過後も発表時刻以降に更新していなければ更新
                return True

            return False

        except Exception as e:
            print(f"Error checking refresh: {e}")
            return True

    def _get_third_friday(self, year: int, month: int) -> datetime:
        """指定月の第3金曜日を計算"""
        first_day = datetime(year, month, 1, tzinfo=JST)
        # 最初の金曜日を見つける
        days_to_friday = (self.RELEASE_DAY_OF_WEEK - first_day.weekday()) % 7
        first_friday = first_day + timedelta(days=days_to_friday)
        # 第3金曜日
        third_friday = first_friday + timedelta(weeks=2)
        return third_friday

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日を計算（第3金曜日）
        """
        try:
            now = datetime.now(ET)

            # 今月の第3金曜日を計算
            third_friday = self._get_third_friday(now.year, now.month)
            third_friday_et = third_friday.replace(tzinfo=ET)

            # 今月の第3金曜日がまだ来ていない場合
            if now.date() < third_friday_et.date():
                next_release_date = third_friday_et
            else:
                # 来月の第3金曜日を計算
                if now.month == 12:
                    next_release_date = self._get_third_friday(now.year + 1, 1).replace(tzinfo=ET)
                else:
                    next_release_date = self._get_third_friday(now.year, now.month + 1).replace(tzinfo=ET)

            return {
                "date": next_release_date.strftime("%Y-%m-%d"),
                "label": f"Redfin Housing Report ({next_release_date.strftime('%b %d')})",
            }

        except Exception as e:
            print(f"Error calculating next release: {e}")
            return None

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
            "indicator": "Redfin National Median Sale Price YoY",
            "source": "Redfin Data Center (S3)",
            "cache_method": "月次スケジュールベース（第3金曜日・3分方式）",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "latest_data_month": cached_data.get("latest_data_month") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
redfin_median_price_service = RedfinMedianPriceService()
