"""
日本 POS-UVPI（消費者購買単価指数）サービス

一橋大学経済研究所からCSVデータを取得

指標:
- POS-UVPI (Point of Sale - Unit Value Price Index)
- SRI一橋大学消費者購買単価指数

データソース:
- CSV: https://risk.ier.hit-u.ac.jp/Common/pos-uvpi.csv

発表スケジュール:
- 毎週水曜日 15:15 JST

キャッシュ方式: 独自発表日時ベース判定方式
"""
import csv
import json
import requests
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "price"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "japan_pos_uvpi_cache.json"


class JapanPosUvpiService:
    """日本POS-UVPIサービス"""

    DATA_CACHE_KEY = "japan:pos_uvpi:data"

    # POS-UVPI CSV URL
    POS_UVPI_URL = "https://risk.ier.hit-u.ac.jp/Common/pos-uvpi.csv"

    # 発表時刻設定（JST）- 毎週水曜 15:15 JST
    RELEASE_WEEKDAY = 2  # Wednesday
    RELEASE_HOUR_JST = 15
    RELEASE_MINUTE_JST = 15

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """POS-UVPIデータを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    cached_data["cached"] = True
                    cached_data["source"] = "redis"
                    cached_data["next_release"] = self._calculate_next_release()
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
                    file_cache["next_release"] = self._calculate_next_release()
                    return file_cache

        # CSVからデータ取得
        result = self._fetch_from_csv()
        if result and result.get("data"):
            latest = self._get_latest(result["data"])
            next_release = self._calculate_next_release()

            cache_payload = {
                "data": result["data"],
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result["data"],
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "hitotsubashi",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            file_cache["cached"] = True
            file_cache["source"] = "file (fallback)"
            file_cache["next_release"] = self._calculate_next_release()
            return file_cache

        return {
            "data": [],
            "latest": None,
            "next_release": self._calculate_next_release(),
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

    def _fetch_from_csv(self) -> Optional[Dict[str, Any]]:
        """一橋大学CSVからデータを取得"""
        try:
            print(f"Fetching Japan POS-UVPI data from: {self.POS_UVPI_URL}")

            response = requests.get(self.POS_UVPI_URL, timeout=30)
            response.raise_for_status()

            # CSVをパース
            lines = response.text.strip().split('\n')
            reader = csv.DictReader(lines)

            parsed_data = []
            header_skipped = False

            for row in reader:
                # メタデータ行をスキップ
                time_val = row.get('time', '')
                if not header_skipped and time_val in ['POS-UVPI', 'decomposition', '', 'the first day of a week']:
                    continue
                header_skipped = True

                try:
                    time_str = time_val.strip('"')
                    chg_uvpi_total_str = row.get('chg_uvpi_total', '').strip()

                    if not time_str or not chg_uvpi_total_str:
                        continue

                    # 日付をパース (形式: YYYY/M/D)
                    date_parts = time_str.split('/')
                    if len(date_parts) == 3:
                        year = date_parts[0]
                        month = date_parts[1].zfill(2)
                        day = date_parts[2].zfill(2)
                        date_str = f"{year}-{month}-{day}"
                    else:
                        continue

                    # 値をパース
                    try:
                        value = float(chg_uvpi_total_str)
                        # パーセンテージに変換
                        value_percent = round(value * 100, 4)
                    except (ValueError, TypeError):
                        continue

                    parsed_data.append({
                        "date": date_str,
                        "chg_uvpi_total": value_percent,
                    })

                except Exception as e:
                    print(f"Error parsing row: {e}")
                    continue

            # 過去5年分にフィルタ
            if parsed_data:
                cutoff_year = datetime.now().year - 5
                cutoff_date = f"{cutoff_year}-01-01"
                parsed_data = [point for point in parsed_data if point["date"] >= cutoff_date]

            print(f"Processed POS-UVPI data: {len(parsed_data)} data points")
            if parsed_data:
                print(f"Latest data: {parsed_data[-1]}")

            return {"data": parsed_data}

        except Exception as e:
            print(f"Error fetching POS-UVPI data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            today = now.date()

            # 水曜日かどうか
            if today.weekday() == self.RELEASE_WEEKDAY:
                release_time = datetime(
                    today.year, today.month, today.day,
                    self.RELEASE_HOUR_JST, self.RELEASE_MINUTE_JST,
                    tzinfo=JST
                )
                # 発表時刻後かつキャッシュが発表時刻前の場合は更新
                if now >= release_time:
                    if last_updated < release_time:
                        return True

            # 1日以上経過している場合
            if (now - last_updated).days >= 1:
                return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return True

    def _calculate_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を計算（次の水曜日）"""
        try:
            now = datetime.now(JST)
            today = now.date()

            # 今日が水曜日で発表時刻前なら今日
            if today.weekday() == self.RELEASE_WEEKDAY:
                release_time = datetime(
                    today.year, today.month, today.day,
                    self.RELEASE_HOUR_JST, self.RELEASE_MINUTE_JST,
                    tzinfo=JST
                )
                if now < release_time:
                    next_release_date = today
                else:
                    # 次週の水曜日
                    days_until_next = 7
                    next_release_date = today + timedelta(days=days_until_next)
            else:
                # 次の水曜日を計算
                days_until_wednesday = (self.RELEASE_WEEKDAY - today.weekday()) % 7
                if days_until_wednesday == 0:
                    days_until_wednesday = 7
                next_release_date = today + timedelta(days=days_until_wednesday)

            return {
                "date": next_release_date.strftime("%Y-%m-%d"),
                "datetime_jst": f"{next_release_date.strftime('%Y-%m-%d')}T15:15:00+09:00",
                "label": f"POS-UVPI - {next_release_date.strftime('%Y/%m/%d')} 15:15 JST（予定）"
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
            "indicator": "Japan POS-UVPI",
            "source": "Hitotsubashi University IER",
            "url": self.POS_UVPI_URL,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._calculate_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
japan_pos_uvpi_service = JapanPosUvpiService()
