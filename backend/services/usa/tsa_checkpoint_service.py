"""
TSA Checkpoint Travel Numbers サービス
TSA公式サイトから旅客データをスクレイピング

データソース: https://www.tsa.gov/travel/passenger-volumes

更新スケジュール:
- 毎日更新（EST 9:00頃）
- 日次データ

キャッシュ方式: last_updated判定（24時間有効、データ更新時に自動リフレッシュ）

データ取得範囲:
- 当年: https://www.tsa.gov/travel/passenger-volumes
- 前年: https://www.tsa.gov/travel/passenger-volumes/{前年}
- 2年分のデータを結合して表示
"""
import requests
from lxml import html
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import calendar

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
EST = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

# TSA データURL（ベース）
TSA_BASE_URL = "https://www.tsa.gov/travel/passenger-volumes"

# ファイルキャッシュ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "economy"
CACHE_FILE = CACHE_DIR / "tsa_checkpoint_data.json"


class TSACheckpointService:
    """
    TSA Checkpoint Travel Numbers サービス
    TSA公式サイトから旅客データをスクレイピング
    """

    CACHE_KEY = "usa:tsa_checkpoint:data"
    # キャッシュTTL: 24時間
    CACHE_TTL = 24 * 60 * 60  # 86400秒

    def get_tsa_checkpoint_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        TSA checkpoint dataを取得

        Returns:
            {
                "data": [...],  # 日次データ（value, ma30含む）
                "latest": {...},  # 最新データ
                "last_updated": str,
                "cached": bool,
                "source": str
            }
        """
        # 1. Redisキャッシュをチェック
        if not force_refresh:
            cached = redis_client.get(self.CACHE_KEY)
            if cached:
                last_updated_str = cached.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str, cached):
                    data = cached.get("data", [])
                    return {
                        "data": data,
                        "latest": self._get_latest(data),
                        "last_updated": last_updated_str,
                        "cached": True,
                        "source": "redis"
                    }

        # 2. ファイルキャッシュをチェック
        if not force_refresh and CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    file_cache = json.load(f)

                last_updated_str = file_cache.get("metadata", {}).get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str, file_cache):
                    data = file_cache.get("data", [])
                    # Redisにも保存
                    redis_client.set(self.CACHE_KEY, {
                        "data": data,
                        "last_updated": last_updated_str,
                        "latest_date": data[-1]["date"] if data else None
                    }, expire=self.CACHE_TTL)
                    return {
                        "data": data,
                        "latest": self._get_latest(data),
                        "last_updated": last_updated_str,
                        "cached": True,
                        "source": "file"
                    }
            except Exception as e:
                print(f"Error reading file cache: {e}")

        # 3. 新しいデータをスクレイピング
        try:
            data = self._scrape_and_process()
            now = datetime.now(JST)

            # キャッシュに保存
            cache_data = {
                "data": data,
                "last_updated": now.isoformat(),
                "latest_date": data[-1]["date"] if data else None
            }
            redis_client.set(self.CACHE_KEY, cache_data, expire=self.CACHE_TTL)
            self._save_file_cache(data, now)

            return {
                "data": data,
                "latest": self._get_latest(data),
                "last_updated": now.isoformat(),
                "cached": False,
                "source": "scrape"
            }

        except Exception as e:
            print(f"Error fetching TSA data: {e}")
            # エラー時は既存キャッシュを返す
            if CACHE_FILE.exists():
                try:
                    with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                        file_cache = json.load(f)
                    data = file_cache.get("data", [])
                    return {
                        "data": data,
                        "latest": self._get_latest(data),
                        "last_updated": file_cache.get("metadata", {}).get("last_updated"),
                        "cached": True,
                        "source": "file_stale",
                        "error": str(e)
                    }
                except Exception:
                    pass

            return {
                "data": [],
                "latest": None,
                "last_updated": None,
                "cached": False,
                "source": "none",
                "error": str(e)
            }

    def _should_refresh(self, last_updated_str: str, cached_data: dict) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        判定ロジック:
        - 最終更新から24時間経過していれば更新
        - または、EST日付が変わり、EST 10:00以降であれば更新
        - または、データソースに新しいデータがあれば更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 24時間経過していれば更新
            if (now - last_updated).total_seconds() >= self.CACHE_TTL:
                return True

            # EST日付が変わり、EST 10:00以降であれば更新（TSAは毎日EST午前に更新）
            last_est_date = last_updated.astimezone(EST).date()
            now_est = now.astimezone(EST)
            if now_est.date() > last_est_date and now_est.hour >= 10:
                return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return True

    def _scrape_and_process(self) -> List[Dict[str, Any]]:
        """
        TSAサイトからデータをスクレイピングし、移動平均を計算
        2年分のデータを取得（当年 + 前年）
        """
        raw_data = self._scrape_tsa_data_two_years()
        return self._calculate_moving_average(raw_data)

    def _get_tsa_urls(self) -> List[str]:
        """
        取得すべきTSA URLを動的に生成
        - 当年: https://www.tsa.gov/travel/passenger-volumes
        - 前年: https://www.tsa.gov/travel/passenger-volumes/{前年}
        """
        current_year = datetime.now().year
        previous_year = current_year - 1

        return [
            TSA_BASE_URL,  # 当年データ
            f"{TSA_BASE_URL}/{previous_year}"  # 前年データ
        ]

    def _scrape_tsa_data_two_years(self) -> List[Dict[str, Any]]:
        """
        TSA checkpoint travel numbersを2年分スクレイピング
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        all_data_points = []
        urls = self._get_tsa_urls()

        for url in urls:
            try:
                print(f"Scraping TSA data from: {url}")
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()

                data_points = self._parse_tsa_table(response.content)
                all_data_points.extend(data_points)
                print(f"Scraped {len(data_points)} data points from {url}")

            except Exception as e:
                print(f"Error scraping {url}: {e}")
                # 前年データの取得に失敗しても当年データがあれば続行
                continue

        # 重複を除去（日付をキーに）
        unique_data = {}
        for point in all_data_points:
            unique_data[point["date"]] = point

        # 日付順にソート（古い順）
        result = list(unique_data.values())
        result.sort(key=lambda x: x["date"])

        print(f"Total TSA data points after deduplication: {len(result)}")
        return result

    def _parse_tsa_table(self, content: bytes) -> List[Dict[str, Any]]:
        """
        TSAページのHTMLテーブルをパース
        """
        tree = html.fromstring(content)
        rows = tree.xpath('//table//tbody//tr')

        data_points = []

        for row in rows:
            cells = row.xpath('.//td')

            if len(cells) >= 2:
                date_text = cells[0].text_content().strip()
                value_text = cells[1].text_content().strip()

                try:
                    # 日付をパース (例: "9/30/2025" -> "2025-09-30")
                    date_obj = datetime.strptime(date_text, "%m/%d/%Y")
                    date_str = date_obj.strftime("%Y-%m-%d")

                    # 数値をパース（カンマを除去）
                    value = int(value_text.replace(",", ""))

                    data_points.append({
                        "date": date_str,
                        "value": value
                    })
                except (ValueError, AttributeError) as e:
                    print(f"Error parsing row: {date_text}, {value_text} - {e}")
                    continue

        return data_points

    def _calculate_moving_average(self, data: List[Dict[str, Any]], window: int = 30) -> List[Dict[str, Any]]:
        """
        30日移動平均を計算
        """
        result = []

        for i, point in enumerate(data):
            if i >= window - 1:
                window_values = [data[j]["value"] for j in range(i - window + 1, i + 1)]
                ma_value = round(sum(window_values) / window)
            else:
                ma_value = None

            result.append({
                "date": point["date"],
                "value": point["value"],
                "ma30": ma_value
            })

        return result

    def _get_latest(self, data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """最新データを取得"""
        if not data:
            return None

        latest = data[-1]
        latest_date = datetime.strptime(latest["date"], "%Y-%m-%d").date()

        # 当月平均と前月平均を計算して前月比を算出
        current_month_avg = self._calculate_month_average(data, latest_date.year, latest_date.month)
        prev_month = latest_date.month - 1 if latest_date.month > 1 else 12
        prev_year = latest_date.year if latest_date.month > 1 else latest_date.year - 1
        prev_month_avg = self._calculate_month_average(data, prev_year, prev_month)

        if current_month_avg is not None and prev_month_avg is not None and prev_month_avg > 0:
            mom_change = current_month_avg - prev_month_avg
            mom_pct = (mom_change / prev_month_avg * 100)
        else:
            mom_change = None
            mom_pct = None

        # 前年同月比を計算
        prev_year_same_month_avg = self._calculate_month_average(data, latest_date.year - 1, latest_date.month)

        if current_month_avg is not None and prev_year_same_month_avg is not None and prev_year_same_month_avg > 0:
            yoy_change = current_month_avg - prev_year_same_month_avg
            yoy_pct = (yoy_change / prev_year_same_month_avg * 100)
        else:
            yoy_change = None
            yoy_pct = None

        return {
            "date": latest["date"],
            "value": latest["value"],
            "ma30": latest.get("ma30"),
            "current_month_avg": round(current_month_avg) if current_month_avg else None,
            "prev_month_avg": round(prev_month_avg) if prev_month_avg else None,
            "mom_change": round(mom_change) if mom_change is not None else None,
            "mom_pct": round(mom_pct, 2) if mom_pct is not None else None,
            "yoy_change": round(yoy_change) if yoy_change is not None else None,
            "yoy_pct": round(yoy_pct, 2) if yoy_pct is not None else None
        }

    def _calculate_month_average(self, data: List[Dict[str, Any]], year: int, month: int) -> Optional[float]:
        """
        指定年月の日次データの平均を計算
        """
        month_data = [
            d["value"] for d in data
            if d["date"].startswith(f"{year}-{month:02d}")
        ]

        if not month_data:
            return None

        return sum(month_data) / len(month_data)

    def _save_file_cache(self, data: List[Dict[str, Any]], updated_at: datetime) -> None:
        """ファイルキャッシュに保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_content = {
                "data": data,
                "metadata": {
                    "source": "TSA Checkpoint Travel Numbers",
                    "url": TSA_URL,
                    "last_updated": updated_at.isoformat(),
                    "count": len(data)
                }
            }
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_content, f, ensure_ascii=False, indent=2)
            print(f"TSA data cached to file: {len(data)} records")
        except Exception as e:
            print(f"Error saving file cache: {e}")

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        exists = redis_client.exists(self.CACHE_KEY)
        cached_data = redis_client.get(self.CACHE_KEY) if exists else None
        file_exists = CACHE_FILE.exists()

        return {
            "cache_key": self.CACHE_KEY,
            "cache_exists": exists,
            "file_exists": file_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "latest_date": cached_data.get("latest_date") if cached_data else None
        }

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)


# シングルトンインスタンス
tsa_checkpoint_service = TSACheckpointService()
