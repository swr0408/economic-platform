"""
日銀 GDPギャップ サービス

日本銀行からExcelファイルを取得してGDPギャップデータをパース

指標:
- GDPギャップ（％）- 日銀推計

データソース:
- Excel: https://www.boj.or.jp/research/research_data/gap/gap.xlsx

発表スケジュール:
- 発表日: 1月・4月・7月・10月の第3営業日
- 発表時刻: 15:00 JST（推定）
- チェック間隔: 発表月の第3〜5営業日 15:00 JST

キャッシュ方式: 発表日時ベース判定方式
"""
import json
import requests
import pandas as pd
from datetime import datetime, date, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "price"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "boj_gdp_gap_cache.json"


class BOJGDPGapService:
    """日銀GDPギャップサービス"""

    DATA_CACHE_KEY = "japan:boj_gdp_gap:data"

    # 日銀GDPギャップExcelファイルURL
    BOJ_GDP_GAP_URL = "https://www.boj.or.jp/research/research_data/gap/gap.xlsx"

    # 発表時刻設定（JST）- 15:00 JST（推定）
    RELEASE_HOUR_JST = 15
    RELEASE_MINUTE_JST = 0

    # 発表月（1, 4, 7, 10月）
    RELEASE_MONTHS = [1, 4, 7, 10]

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """GDPギャップデータを取得"""
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

        # Excelからデータ取得
        result = self._fetch_from_excel()
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

    def _fetch_from_excel(self) -> Optional[Dict[str, Any]]:
        """日銀ExcelファイルからGDPギャップデータを取得"""
        try:
            print(f"Fetching BOJ GDP Gap data from: {self.BOJ_GDP_GAP_URL}")

            response = requests.get(self.BOJ_GDP_GAP_URL, timeout=60)
            response.raise_for_status()
            print(f"Downloaded Excel: {len(response.content)} bytes")

            # Excelをパース（skiprows=4でヘッダーをスキップ）
            df = pd.read_excel(BytesIO(response.content), sheet_name=0, skiprows=4)
            print(f"Excel shape: {df.shape}")
            print(f"Excel columns: {df.columns.tolist()}")

            # 列0: 日付（YYYY.XQ形式）、列1: Output gap (%)
            date_col = df.columns[0]
            output_gap_col = df.columns[1]

            print(f"Date column: {date_col}")
            print(f"Output gap column: {output_gap_col}")

            series_data = []

            for idx, row in df.iterrows():
                try:
                    # 日付を取得
                    date_val = row[date_col]
                    if pd.isna(date_val):
                        continue

                    # 日付形式 "YYYY.XQ" を "YYYY-QX" に変換
                    date_str = str(date_val).strip()

                    # 期待形式: "1983.1Q" -> "1983-Q1"
                    if '.' in date_str and 'Q' in date_str:
                        parts = date_str.split('.')
                        if len(parts) == 2:
                            year = parts[0]
                            quarter = parts[1].replace('Q', '')  # "1Q" -> "1"
                            date_str = f"{year}-Q{quarter}"
                        else:
                            continue
                    else:
                        continue

                    # GDPギャップ値を取得
                    output_gap_value = row[output_gap_col]

                    if pd.isna(output_gap_value):
                        continue

                    # 数値に変換
                    if isinstance(output_gap_value, str):
                        output_gap_value = output_gap_value.strip()
                        if not output_gap_value or output_gap_value == '-':
                            continue
                        output_gap_value = float(output_gap_value)
                    else:
                        output_gap_value = float(output_gap_value)

                    series_data.append({
                        "date": date_str,
                        "value": round(output_gap_value, 2)
                    })

                except Exception as e:
                    print(f"Error processing row {idx}: {e}")
                    continue

            # 日付でソート
            series_data.sort(key=lambda x: (int(x["date"][:4]), int(x["date"][-1])))

            # 2000年以降にフィルタ
            if series_data:
                series_data = [point for point in series_data if point["date"] >= "2000-Q1"]

            print(f"Processed BOJ GDP Gap data: {len(series_data)} data points")
            if series_data:
                print(f"Latest data: {series_data[-1]}")

            return {"data": series_data}

        except Exception as e:
            print(f"Error fetching BOJ GDP Gap data: {e}")
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

            # 発表月（1, 4, 7, 10月）かどうか
            is_release_month = today.month in self.RELEASE_MONTHS

            if is_release_month:
                # 発表月の第3〜5営業日（3〜8日頃）をチェック
                if 3 <= today.day <= 8:
                    # 発表時刻（15:00 JST）以降かどうか
                    if now.hour >= self.RELEASE_HOUR_JST:
                        # キャッシュが今日より古い場合は更新
                        if last_updated.date() < today:
                            return True

            # 1週間以上経過している場合は更新
            if (now - last_updated).days >= 7:
                return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return True

    def _calculate_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表予定日を計算"""
        try:
            now = datetime.now(JST)
            today = now.date()

            # 次の発表月を見つける
            for month in self.RELEASE_MONTHS:
                if month > today.month or (month == today.month and today.day < 8):
                    # 第3営業日を推定（土日を考慮して5日頃）
                    next_date = date(today.year, month, 5)

                    # 土曜日なら月曜日に
                    if next_date.weekday() == 5:
                        next_date = date(today.year, month, 7)
                    # 日曜日なら月曜日に
                    elif next_date.weekday() == 6:
                        next_date = date(today.year, month, 6)

                    return {
                        "date": next_date.strftime("%Y-%m-%d"),
                        "datetime_jst": f"{next_date.strftime('%Y-%m-%d')}T15:00:00+09:00",
                        "label": f"日銀GDPギャップ - {next_date.strftime('%Y/%m/%d')} 15:00 JST（推定）"
                    }

            # 来年の1月
            next_date = date(today.year + 1, 1, 5)
            if next_date.weekday() == 5:
                next_date = date(today.year + 1, 1, 7)
            elif next_date.weekday() == 6:
                next_date = date(today.year + 1, 1, 6)

            return {
                "date": next_date.strftime("%Y-%m-%d"),
                "datetime_jst": f"{next_date.strftime('%Y-%m-%d')}T15:00:00+09:00",
                "label": f"日銀GDPギャップ - {next_date.strftime('%Y/%m/%d')} 15:00 JST（推定）"
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
            "indicator": "BOJ GDP Gap",
            "source": "Bank of Japan",
            "url": self.BOJ_GDP_GAP_URL,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._calculate_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
boj_gdp_gap_service = BOJGDPGapService()
