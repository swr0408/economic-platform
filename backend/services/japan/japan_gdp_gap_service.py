"""
日本 GDPギャップ サービス

内閣府からExcelファイルを取得してGDPギャップデータをパース

指標:
- GDPギャップ（％）

データソース:
- Excel: https://www5.cao.go.jp/keizai3/getsurei/2522gap.xlsx

発表スケジュール:
- 不定期（四半期GDP発表後、月例経済報告に紐づく）
- 発表時刻: 15:00 JST（推定）

キャッシュ方式: 月例経済報告スケジュールベース判定方式
"""
import json
import requests
import pandas as pd
import re
from datetime import datetime, date, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

from core.redis_client import redis_client

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "japan_gdp_gap_cache.json"


class JapanGDPGapService:
    """日本GDPギャップサービス"""

    DATA_CACHE_KEY = "japan:gdp_gap:data"

    # 月例経済報告スケジュールページ（ExcelファイルのURLもここから取得）
    SCHEDULE_URL = "https://www5.cao.go.jp/keizai3/getsurei/getsurei-index.html"

    # 発表時刻設定（JST）- 15:00 JST（推定）
    RELEASE_HOUR_JST = 15
    RELEASE_MINUTE_JST = 0

    def __init__(self):
        pass

    def _get_excel_url(self) -> Optional[str]:
        """月例経済報告ページからGDPギャップExcelファイルのURLを取得"""
        try:
            response = requests.get(self.SCHEDULE_URL, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # gap.xlsxへのリンクを探す
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'gap.xlsx' in href:
                    # 相対パスの場合は絶対パスに変換
                    if href.startswith('/'):
                        return f"https://www.cao.go.jp{href}"
                    elif href.startswith('http'):
                        return href
                    else:
                        return f"https://www5.cao.go.jp/keizai3/getsurei/{href}"

            print("GDP Gap Excel URL not found on schedule page")
            return None

        except Exception as e:
            print(f"Error getting Excel URL: {e}")
            return None

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
                    cached_data["next_release"] = self._get_next_release()
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
                    file_cache["next_release"] = self._get_next_release()
                    return file_cache

        # Excelからデータ取得
        result = self._fetch_from_excel()
        if result and result.get("data"):
            latest = self._get_latest(result["data"])
            next_release = self._get_next_release()

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
                "source": "cao",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            file_cache["cached"] = True
            file_cache["source"] = "file (fallback)"
            file_cache["next_release"] = self._get_next_release()
            return file_cache

        return {
            "data": [],
            "latest": None,
            "next_release": self._get_next_release(),
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
        """内閣府ExcelファイルからGDPギャップデータを取得"""
        try:
            # 動的にExcel URLを取得
            excel_url = self._get_excel_url()
            if not excel_url:
                print("Could not get Excel URL")
                return None

            print(f"Fetching Japan GDP Gap data from: {excel_url}")

            response = requests.get(excel_url, timeout=60)
            response.raise_for_status()
            print(f"Downloaded Excel: {len(response.content)} bytes")

            # Excelをパース
            df = pd.read_excel(BytesIO(response.content), sheet_name=0, skiprows=5)
            print(f"Excel shape: {df.shape}")
            print(f"Excel columns: {df.columns.tolist()}")

            # GDPギャップ列を探す
            gdp_gap_col = None
            for col in df.columns:
                if 'GDP Gap' in str(col) or 'GDP gap' in str(col):
                    gdp_gap_col = col
                    break

            if gdp_gap_col is None:
                print("GDP Gap column not found")
                return None

            print(f"Found GDP Gap column: {gdp_gap_col}")

            # 四半期マッピング
            quarter_map = {
                '\u2160': 'Q1', 'Ⅰ': 'Q1', 'I': 'Q1', '1': 'Q1',
                '\u2161': 'Q2', 'Ⅱ': 'Q2', 'II': 'Q2', '2': 'Q2',
                '\u2162': 'Q3', 'Ⅲ': 'Q3', 'III': 'Q3', '3': 'Q3',
                '\u2163': 'Q4', 'Ⅳ': 'Q4', 'IV': 'Q4', '4': 'Q4',
            }

            series_data = []
            current_year = None

            for idx, row in df.iterrows():
                try:
                    # 年を取得
                    year_val = row.iloc[0]
                    if pd.notna(year_val) and isinstance(year_val, (int, float)):
                        current_year = int(year_val)

                    # 四半期を取得
                    quarter_val = row.iloc[1]
                    if pd.isna(quarter_val) or current_year is None:
                        continue

                    quarter_str = str(quarter_val).strip()
                    quarter = quarter_map.get(quarter_str)

                    if not quarter:
                        quarter_upper = quarter_str.upper()
                        if 'IV' in quarter_upper:
                            quarter = 'Q4'
                        elif 'III' in quarter_upper:
                            quarter = 'Q3'
                        elif 'II' in quarter_upper:
                            quarter = 'Q2'
                        elif 'I' in quarter_upper:
                            quarter = 'Q1'
                        else:
                            continue

                    # GDPギャップ値を取得
                    gdp_gap_value = row[gdp_gap_col]
                    if pd.isna(gdp_gap_value):
                        continue

                    if isinstance(gdp_gap_value, str):
                        gdp_gap_value = gdp_gap_value.strip()
                        if not gdp_gap_value or gdp_gap_value == '-':
                            continue
                        gdp_gap_value = float(gdp_gap_value)
                    else:
                        gdp_gap_value = float(gdp_gap_value)

                    date_str = f"{current_year}-{quarter}"
                    series_data.append({
                        "date": date_str,
                        "value": round(gdp_gap_value, 2)
                    })

                except Exception as e:
                    print(f"Error processing row {idx}: {e}")
                    continue

            # 日付でソート
            series_data.sort(key=lambda x: (int(x["date"][:4]), x["date"][5:]))

            # 2000年以降にフィルタ
            if series_data:
                series_data = [point for point in series_data if point["date"] >= "2000-Q1"]

            print(f"Processed GDP Gap data: {len(series_data)} data points")
            if series_data:
                print(f"Latest data: {series_data[-1]}")

            return {"data": series_data}

        except Exception as e:
            print(f"Error fetching GDP Gap data: {e}")
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

            # 次回発表予定日を取得
            next_release = self._get_next_release()
            if next_release and next_release.get("date"):
                next_date_str = next_release["date"]
                next_date = datetime.strptime(next_date_str, "%Y-%m-%d").replace(tzinfo=JST)

                # 発表予定日から3日以内の場合、毎日チェック
                days_until_release = (next_date.date() - now.date()).days
                if -3 <= days_until_release <= 3:
                    # 発表時刻後かつキャッシュが古い場合は更新
                    if now.hour >= self.RELEASE_HOUR_JST:
                        if last_updated.date() < now.date():
                            return True

            # 1週間以上経過している場合は更新
            if (now - last_updated).days >= 7:
                return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return True

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """月例経済報告スケジュールページから次回発表予定日を取得"""
        try:
            # キャッシュから取得を試みる
            schedule_cache_key = "japan:gdp_gap:schedule"
            cached_schedule = redis_client.get(schedule_cache_key)
            if cached_schedule:
                cache_time = cached_schedule.get("cached_at")
                if cache_time:
                    cache_dt = datetime.fromisoformat(cache_time)
                    if cache_dt.tzinfo is None:
                        cache_dt = cache_dt.replace(tzinfo=JST)
                    # 1日以内のキャッシュなら使用
                    if (datetime.now(JST) - cache_dt).days < 1:
                        return cached_schedule.get("next_release")

            # スケジュールページをスクレイピング
            response = requests.get(self.SCHEDULE_URL, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            text = soup.get_text()

            # 「予定」セクションから日付を抽出
            # パターン: "令和7年1月22日（水）" or "2026年1月22日"
            now = datetime.now(JST)
            current_year = now.year

            # 令和年から西暦年への変換
            reiwa_pattern = r'令和(\d+)年(\d+)月(\d+)日'
            matches = re.findall(reiwa_pattern, text)

            next_date = None
            for match in matches:
                reiwa_year, month, day = int(match[0]), int(match[1]), int(match[2])
                # 令和元年 = 2019年
                western_year = 2018 + reiwa_year
                try:
                    candidate_date = date(western_year, month, day)
                    # 今日以降の日付を探す
                    if candidate_date >= now.date():
                        if next_date is None or candidate_date < next_date:
                            next_date = candidate_date
                except ValueError:
                    continue

            if next_date:
                result = {
                    "date": next_date.strftime("%Y-%m-%d"),
                    "datetime_jst": f"{next_date.strftime('%Y-%m-%d')}T15:00:00+09:00",
                    "label": f"GDPギャップ（月例経済報告）- {next_date.strftime('%Y/%m/%d')} 15:00 JST（予定）"
                }

                # キャッシュに保存
                redis_client.set(schedule_cache_key, {
                    "next_release": result,
                    "cached_at": datetime.now(JST).isoformat()
                }, expire=86400)  # 1日

                return result

            # スクレイピング失敗時のフォールバック
            return self._calculate_fallback_next_release()

        except Exception as e:
            print(f"Error getting next release schedule: {e}")
            return self._calculate_fallback_next_release()

    def _calculate_fallback_next_release(self) -> Optional[Dict[str, Any]]:
        """フォールバック: 次回発表日を推定"""
        try:
            now = datetime.now(JST)
            today = now.date()

            # 毎月下旬（22日頃）に発表されることが多い
            if today.day <= 22:
                next_date = date(today.year, today.month, 22)
            else:
                if today.month == 12:
                    next_date = date(today.year + 1, 1, 22)
                else:
                    next_date = date(today.year, today.month + 1, 22)

            return {
                "date": next_date.strftime("%Y-%m-%d"),
                "datetime_jst": f"{next_date.strftime('%Y-%m-%d')}T15:00:00+09:00",
                "label": f"GDPギャップ - {next_date.strftime('%Y/%m/%d')} 頃（推定）"
            }

        except Exception as e:
            print(f"Error calculating fallback next release: {e}")
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
            "indicator": "Japan GDP Gap",
            "source": "Cabinet Office (CAO)",
            "url": self.GDP_GAP_URL,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
japan_gdp_gap_service = JapanGDPGapService()
