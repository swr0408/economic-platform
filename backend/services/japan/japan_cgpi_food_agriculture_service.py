"""
日本 企業物価指数：飲食料品・農林水産物 サービス

BOJ (日本銀行) からCGPI詳細データを取得

指標:
- 飲食料品 (Food & Beverages) - 前年比
- 農林水産物 (Agriculture, Forestry & Fishery) - 前年比

データソース:
- BOJ ZIP ファイル: https://www.stat-search.boj.or.jp/ssi/docs/info/cgpi_m_jp.zip
  ※ 詳細品目データが含まれるZIPファイル

発表スケジュール:
- 毎月10日〜18日頃 8:50 JST（CGPIと同一）

キャッシュ方式: 独自発表日時ベース判定方式
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
DATA_CACHE_FILE = CACHE_DIR / "japan_cgpi_food_agriculture_cache.json"


class JapanCGPIFoodAgricultureService:
    """日本企業物価指数：飲食料品・農林水産物サービス"""

    DATA_CACHE_KEY = "japan:cgpi_food_agriculture:data"

    # BOJ CGPI ZIP URL（詳細品目データ）
    CGPI_ZIP_URL = "https://www.stat-search.boj.or.jp/ssi/docs/info/cgpi_m_jp.zip"

    # 発表時刻設定（JST）- 8:50 JST
    RELEASE_HOUR_JST = 8
    RELEASE_MINUTE_JST = 50

    # 対象系列のパターン
    FOOD_PATTERN = "類別/_飲食料品"
    AGRICULTURE_PATTERN = "大類別/農林水産物"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """飲食料品・農林水産物データを取得"""
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

        # BOJからデータ取得
        result = self._fetch_from_boj()
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
                "source": "boj",
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

    def _fetch_from_boj(self) -> Optional[Dict[str, Any]]:
        """BOJ ZIPファイルからデータを取得"""
        try:
            print(f"Fetching Japan CGPI Food/Agriculture data from BOJ ZIP: {self.CGPI_ZIP_URL}")

            # ZIPファイルをダウンロード
            response = requests.get(self.CGPI_ZIP_URL, timeout=60)
            response.raise_for_status()
            print(f"Downloaded ZIP: {len(response.content)} bytes")

            # ZIPを解凍してCSVを取得
            with zipfile.ZipFile(BytesIO(response.content)) as zf:
                # CSVファイルを探す
                csv_files = [f for f in zf.namelist() if f.endswith('.csv')]
                if not csv_files:
                    print("No CSV files found in ZIP")
                    return None

                # 最初のCSVファイルを読み込む
                csv_content = zf.read(csv_files[0]).decode('shift_jis')

            # CSVをパース
            processed_data = self._parse_csv(csv_content)
            if not processed_data:
                return None

            return {"data": processed_data}

        except Exception as e:
            print(f"Error fetching CGPI Food/Agriculture data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_csv(self, csv_content: str) -> Optional[List[Dict[str, Any]]]:
        """
        CGPI CSVファイルをパース

        CSV形式（ZIPファイル版）:
        - 行0: ヘッダー（空,空,空,YYYYMM,YYYYMM,...）
        - 行1以降: データ（コード,説明,カテゴリ名,値,値,...）

        抽出対象:
        - 飲食料品: カテゴリ名に「類別/_飲食料品」を含む行
        - 農林水産物: カテゴリ名に「大類別/農林水産物」を含む行
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

            # 飲食料品と農林水産物の行を探す
            food_row = None
            agriculture_row = None

            for line in lines[1:]:
                parts = line.split(',')
                if len(parts) < 4:
                    continue

                category_name = parts[2].strip().strip('"')

                if self.FOOD_PATTERN in category_name and food_row is None:
                    food_row = parts
                    print(f"Found food row: {category_name}")

                if self.AGRICULTURE_PATTERN in category_name and agriculture_row is None:
                    agriculture_row = parts
                    print(f"Found agriculture row: {category_name}")

                if food_row and agriculture_row:
                    break

            if not food_row and not agriculture_row:
                print("Could not find food or agriculture rows")
                return None

            # データを抽出（指数値から前年比を計算）
            food_values = {}
            agriculture_values = {}

            for idx, date_str in date_columns:
                year = date_str[:4]
                month = date_str[4:6]
                date_key = f"{year}-{month}-01"

                if food_row and idx < len(food_row):
                    val_str = food_row[idx].strip()
                    if val_str:
                        try:
                            food_values[date_key] = float(val_str)
                        except ValueError:
                            pass

                if agriculture_row and idx < len(agriculture_row):
                    val_str = agriculture_row[idx].strip()
                    if val_str:
                        try:
                            agriculture_values[date_key] = float(val_str)
                        except ValueError:
                            pass

            # 前年比を計算してデータを構築
            all_dates = sorted(set(food_values.keys()) | set(agriculture_values.keys()))
            series_data = []

            for date_key in all_dates:
                food_index = food_values.get(date_key)
                agriculture_index = agriculture_values.get(date_key)

                # 前年同月の日付を計算
                year = int(date_key[:4])
                year_ago_key = f"{year - 1}{date_key[4:]}"

                food_yoy = None
                agriculture_yoy = None

                # 飲食料品の前年比
                if food_index is not None:
                    food_prev = food_values.get(year_ago_key)
                    if food_prev and food_prev != 0:
                        food_yoy = round(((food_index - food_prev) / food_prev) * 100, 2)

                # 農林水産物の前年比
                if agriculture_index is not None:
                    agriculture_prev = agriculture_values.get(year_ago_key)
                    if agriculture_prev and agriculture_prev != 0:
                        agriculture_yoy = round(((agriculture_index - agriculture_prev) / agriculture_prev) * 100, 2)

                # 両方の前年比がある場合のみ追加
                if food_yoy is not None or agriculture_yoy is not None:
                    series_data.append({
                        "date": date_key,
                        "food_yoy": food_yoy,
                        "agriculture_yoy": agriculture_yoy,
                    })

            # 過去10年分にフィルタ
            if series_data:
                cutoff_year = datetime.now().year - 10
                cutoff_date = f"{cutoff_year}-01-01"
                series_data = [point for point in series_data if point["date"] >= cutoff_date]

            print(f"Processed Food/Agriculture data: {len(series_data)} data points")
            if series_data:
                print(f"Latest data: {series_data[-1]}")

            return series_data

        except Exception as e:
            print(f"Error parsing CGPI CSV: {e}")
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

            # 今月の発表期間（10日〜18日）内かどうか
            if 10 <= today.day <= 18:
                release_time = datetime(
                    today.year, today.month, today.day,
                    self.RELEASE_HOUR_JST, self.RELEASE_MINUTE_JST,
                    tzinfo=JST
                )
                if now >= release_time:
                    if last_updated < release_time:
                        return True

            if (now - last_updated).days >= 1:
                if 10 <= today.day <= 18:
                    return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return True

    def _calculate_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を計算"""
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
                "label": f"企業物価指数 - {next_release_date.strftime('%Y/%m/%d')} 8:50 JST（予定）"
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
            "indicator": "Japan CGPI Food & Agriculture",
            "source": "Bank of Japan (BOJ)",
            "url": self.CGPI_ZIP_URL,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._calculate_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
japan_cgpi_food_agriculture_service = JapanCGPIFoodAgricultureService()
