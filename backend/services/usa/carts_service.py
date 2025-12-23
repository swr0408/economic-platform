"""
シカゴ連銀小売指数（CARTS: Chicago Fed Advance Retail Trade Summary）サービス
Chicago Fed APIからCARTSデータを取得

データソース:
- Fig1 CSV: Weekly Index of Retail Trade（週次小売売上高）
- Fig6 ZIP/Excel: Price Indicators（価格指標）

発表スケジュール:
- 予備版: 毎月第1木曜日 8:30 ET
- 確定版: 毎月第2金曜日 8:30 ET
- Chicago Fedからスクレイピングして自動取得

キャッシュ方式: 発表日時ベース判定（last_updated判定方式）
"""
import io
import os
import re
import json
import zipfile
import tempfile
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd
from bs4 import BeautifulSoup

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# Chicago Fed CARTS データURL
CARTS_ZIP_URL = "https://api.data.chicagofed.org/CARTS/carts-dashboard.zip"
CARTS_FIG1_CSV_URL = "https://api.data.chicagofed.org/CARTS/carts-dashboard-fig1.csv"

# Chicago Fed Data Release Calendar URL
CARTS_SCHEDULE_URL = "https://www.chicagofed.org/research/data/data-release-calendar"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
WEEKLY_CACHE_FILE = CACHE_DIR / "carts_weekly_cache.json"
PRICE_CACHE_FILE = CACHE_DIR / "carts_price_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "carts_schedule.json"


class CartsService:
    """シカゴ連銀小売指数（CARTS）サービス"""

    # Redisキャッシュキー
    WEEKLY_CACHE_KEY = "chicagofed:carts:weekly"
    PRICE_CACHE_KEY = "chicagofed:carts:price"
    SCHEDULE_CACHE_KEY = "chicagofed:carts:schedule"

    # スケジュールキャッシュの有効期間（30日 = 1ヶ月）
    SCHEDULE_CACHE_TTL = 30 * 24 * 60 * 60  # 2592000秒

    # 発表時刻設定
    RELEASE_HOUR_ET = 8
    RELEASE_MINUTE_ET = 30

    def __init__(self):
        pass

    def get_carts_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        CARTSデータを取得（週次データ + 価格データ）

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "weekly": {...},  # 週次データ
                "price": {...},   # 価格データ（前年比）
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # 週次データを取得
        weekly_result = self.get_weekly_data(force_refresh)

        # 価格データを取得
        price_result = self.get_price_data(force_refresh)

        # 次回発表日を取得
        next_release = self._get_next_release()

        return {
            "weekly": weekly_result,
            "price": price_result,
            "next_release": next_release,
            "cached": weekly_result.get("cached", False) and price_result.get("cached", False),
            "source": "combined",
            "last_updated": datetime.now(JST).isoformat()
        }

    def get_weekly_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        週次小売売上高データを取得（Fig1 CSV）

        Returns:
            {
                "data": [{"date": str, "nominal": float, "real": float, "mom": float, "yoy": float}, ...],
                "latest": {...},
                "next_release": {...} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.WEEKLY_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": self._get_next_release(),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache(WEEKLY_CACHE_FILE)
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    data = file_cache.get("data", [])
                    # Redisにも保存
                    redis_client.set(self.WEEKLY_CACHE_KEY, file_cache, expire=0)
                    return {
                        "data": data,
                        "latest": file_cache.get("latest"),
                        "next_release": self._get_next_release(),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # 外部APIから取得
        api_data = self._fetch_weekly_data()

        if api_data:
            latest = api_data[-1] if api_data else None
            cache_payload = {
                "data": api_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            # Redisに保存（TTLなし）
            redis_client.set(self.WEEKLY_CACHE_KEY, cache_payload, expire=0)
            # ファイルにも保存
            self._save_file_cache(WEEKLY_CACHE_FILE, cache_payload)

            return {
                "data": api_data,
                "latest": latest,
                "next_release": self._get_next_release(),
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache(WEEKLY_CACHE_FILE)
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

    def get_price_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        価格データを取得（Fig6: 前年比）

        Returns:
            {
                "data": [{"date": str, "bea": float, "cpi": float, "carts_nowcast": float}, ...],
                "latest": {...},
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.PRICE_CACHE_KEY)
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

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache(PRICE_CACHE_FILE)
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    data = file_cache.get("data", [])
                    # Redisにも保存
                    redis_client.set(self.PRICE_CACHE_KEY, file_cache, expire=0)
                    return {
                        "data": data,
                        "latest": file_cache.get("latest"),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # 外部APIから取得
        api_data = self._fetch_price_data()

        if api_data:
            latest = api_data[-1] if api_data else None
            cache_payload = {
                "data": api_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            # Redisに保存（TTLなし）
            redis_client.set(self.PRICE_CACHE_KEY, cache_payload, expire=0)
            # ファイルにも保存
            self._save_file_cache(PRICE_CACHE_FILE, cache_payload)

            return {
                "data": api_data,
                "latest": latest,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache(PRICE_CACHE_FILE)
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

    def _fetch_weekly_data(self) -> List[Dict[str, Any]]:
        """Chicago Fed Fig1 CSVから週次データを取得"""
        try:
            print("Fetching CARTS weekly data from Chicago Fed...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = requests.get(CARTS_FIG1_CSV_URL, headers=headers, timeout=30)
            response.raise_for_status()

            # CSVをパース
            result = self._parse_weekly_csv(response.text)

            print(f"Fetched {len(result)} weekly data points from CARTS")
            return result

        except Exception as e:
            print(f"Error fetching CARTS weekly data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_weekly_csv(self, csv_text: str) -> List[Dict[str, Any]]:
        """
        週次データCSVをパース

        CSV形式:
        date,Mils. $,Mils. 2017$
        2018-01-07,377714.64546037023,374358.7570799168
        """
        lines = csv_text.strip().split('\n')
        if len(lines) < 2:
            return []

        result = []

        # データ行を処理（ヘッダーをスキップ）
        for line in lines[1:]:
            parts = line.split(',')
            if len(parts) < 3:
                continue

            date_str = parts[0].strip()
            nominal_str = parts[1].strip()
            real_str = parts[2].strip()

            # 値を変換
            nominal_value = None
            if nominal_str:
                try:
                    nominal_value = round(float(nominal_str), 2)
                except ValueError:
                    pass

            real_value = None
            if real_str:
                try:
                    real_value = round(float(real_str), 2)
                except ValueError:
                    pass

            if date_str and (nominal_value is not None or real_value is not None):
                result.append({
                    "date": date_str,
                    "nominal": nominal_value,
                    "real": real_value,
                    "mom": None,  # 後で計算
                    "yoy": None   # 後で計算
                })

        # 日付順にソート
        result.sort(key=lambda x: x["date"])

        # 前週比と前年比を計算
        for i, item in enumerate(result):
            # 前週比（1週間前のデータがあれば）
            if i >= 1:
                prev_real = result[i - 1].get("real")
                curr_real = item.get("real")
                if prev_real and prev_real != 0 and curr_real:
                    item["mom"] = round((curr_real - prev_real) / prev_real * 100, 2)

            # 前年比（52週前のデータがあれば）
            if i >= 52:
                year_ago_real = result[i - 52].get("real")
                curr_real = item.get("real")
                if year_ago_real and year_ago_real != 0 and curr_real:
                    item["yoy"] = round((curr_real - year_ago_real) / year_ago_real * 100, 2)

        return result

    def _fetch_price_data(self) -> List[Dict[str, Any]]:
        """Chicago Fed Fig6 ZIPからExcelの価格データを取得"""
        try:
            print("Fetching CARTS price data from Chicago Fed ZIP...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = requests.get(CARTS_ZIP_URL, headers=headers, timeout=60)
            response.raise_for_status()

            # ZIPを解凍してExcelを読み込む
            result = self._extract_fig6_from_zip(response.content)

            print(f"Fetched {len(result)} price data points from CARTS")
            return result

        except Exception as e:
            print(f"Error fetching CARTS price data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _extract_fig6_from_zip(self, zip_content: bytes) -> List[Dict[str, Any]]:
        """ZIPファイルからFig6シートを抽出"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # ZIPを解凍
            with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # Excelファイルを探す
            excel_path = None
            for root, dirs, files in os.walk(temp_dir):
                for f in files:
                    if f.lower() == "carts-dashboard-figures.xlsx":
                        excel_path = os.path.join(root, f)
                        break
                if excel_path:
                    break

            if not excel_path:
                print("Excel file not found in ZIP")
                return []

            # Fig6シートを読み込み
            return self._read_fig6_sheet(excel_path)

    def _read_fig6_sheet(self, excel_path: str) -> List[Dict[str, Any]]:
        """ExcelのFig6シートを読み込み（前年比価格データ）"""
        try:
            df = pd.read_excel(excel_path, sheet_name="fig6", header=None)

            data = []

            # データ行を処理（ヘッダーは1行目）
            for i in range(1, len(df)):
                try:
                    date_value = df.iloc[i, 0]
                    if pd.isna(date_value):
                        continue

                    # 日付の変換
                    if isinstance(date_value, (pd.Timestamp, datetime)):
                        formatted_date = date_value.strftime('%Y-%m-%d')
                    elif isinstance(date_value, str):
                        try:
                            parsed_date = pd.to_datetime(date_value)
                            formatted_date = parsed_date.strftime('%Y-%m-%d')
                        except:
                            continue
                    else:
                        try:
                            parsed_date = pd.to_datetime(date_value, origin='1899-12-30', unit='D')
                            formatted_date = parsed_date.strftime('%Y-%m-%d')
                        except:
                            continue

                    # 各列の値を取得
                    bea_value = None
                    cpi_value = None
                    carts_value = None

                    if len(df.columns) > 1 and not pd.isna(df.iloc[i, 1]):
                        try:
                            bea_value = round(float(df.iloc[i, 1]), 2)
                        except:
                            pass

                    if len(df.columns) > 2 and not pd.isna(df.iloc[i, 2]):
                        try:
                            cpi_value = round(float(df.iloc[i, 2]), 2)
                        except:
                            pass

                    if len(df.columns) > 3 and not pd.isna(df.iloc[i, 3]):
                        try:
                            carts_value = round(float(df.iloc[i, 3]), 2)
                        except:
                            pass

                    if bea_value is not None or cpi_value is not None or carts_value is not None:
                        data.append({
                            'date': formatted_date,
                            'bea': bea_value,
                            'cpi': cpi_value,
                            'carts_nowcast': carts_value
                        })

                except Exception as e:
                    print(f"Error processing row {i}: {e}")
                    continue

            return data

        except Exception as e:
            print(f"Error reading fig6 sheet: {e}")
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        判定ロジック:
        - 次回発表日時を過ぎており、かつ最終更新がそれより前なら更新が必要
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 次回発表情報を取得
            next_release = self._get_next_release()
            if not next_release:
                # 発表情報がない場合は7日に1回の更新を想定
                days_since_update = (now - last_updated).days
                return days_since_update >= 7

            # 発表日時をパース
            release_date_str = next_release.get("date")
            if not release_date_str:
                return False

            release_date = datetime.strptime(release_date_str, "%Y-%m-%d")

            # 夏時間判定
            is_dst = self._is_dst(now)
            release_hour = 21 if is_dst else 22  # 8:30 ET → 21:30/22:30 JST

            release_datetime = datetime(
                release_date.year, release_date.month, release_date.day,
                release_hour, 30, 0, tzinfo=JST
            )

            # 発表日時を過ぎており、かつ最終更新が発表日時より前なら更新が必要
            if now >= release_datetime and last_updated < release_datetime:
                return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return False

    def _is_dst(self, dt: datetime) -> bool:
        """米国東部時間が夏時間かどうかを判定"""
        try:
            et_time = dt.astimezone(ET)
            return bool(et_time.dst())
        except Exception:
            # 3月第2日曜〜11月第1日曜を夏時間と仮定
            if dt.month > 3 and dt.month < 11:
                return True
            if dt.month == 3:
                second_sunday = 14 - (date(dt.year, 3, 1).weekday() + 1) % 7
                return dt.day >= second_sunday
            if dt.month == 11:
                first_sunday = 7 - (date(dt.year, 11, 1).weekday() + 1) % 7
                return dt.day < first_sunday
            return False

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日を取得

        Chicago Fed Data Release Calendarからスクレイピングして取得
        キャッシュがあればそれを使用（1ヶ月間有効）
        """
        # Redisキャッシュをチェック
        cached = redis_client.get(self.SCHEDULE_CACHE_KEY)
        if cached:
            cached_at = cached.get("cached_at")
            if cached_at:
                try:
                    cached_dt = datetime.fromisoformat(cached_at)
                    if cached_dt.tzinfo is None:
                        cached_dt = cached_dt.replace(tzinfo=JST)
                    # キャッシュは1ヶ月間有効
                    if (datetime.now(JST) - cached_dt).total_seconds() < self.SCHEDULE_CACHE_TTL:
                        release_date_str = cached.get("date")
                        if release_date_str:
                            release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
                            if release_date >= date.today():
                                return {
                                    "date": cached.get("date"),
                                    "label": cached.get("label")
                                }
                except Exception:
                    pass

        # ファイルキャッシュをチェック
        schedule_cache = self._load_file_cache(SCHEDULE_CACHE_FILE)
        if schedule_cache:
            cached_at = schedule_cache.get("cached_at")
            if cached_at:
                try:
                    cached_dt = datetime.fromisoformat(cached_at)
                    if cached_dt.tzinfo is None:
                        cached_dt = cached_dt.replace(tzinfo=JST)
                    if (datetime.now(JST) - cached_dt).total_seconds() < self.SCHEDULE_CACHE_TTL:
                        release_date_str = schedule_cache.get("date")
                        if release_date_str:
                            release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
                            if release_date >= date.today():
                                # Redisにも保存
                                redis_client.set(self.SCHEDULE_CACHE_KEY, schedule_cache, expire=self.SCHEDULE_CACHE_TTL)
                                return {
                                    "date": schedule_cache.get("date"),
                                    "label": schedule_cache.get("label")
                                }
                except Exception:
                    pass

        # Chicago Fedページからスクレイピング
        scraped = self._scrape_next_release()
        if scraped:
            # キャッシュに保存（1ヶ月間有効）
            cache_data = {
                **scraped,
                "cached_at": datetime.now(JST).isoformat()
            }
            redis_client.set(self.SCHEDULE_CACHE_KEY, cache_data, expire=self.SCHEDULE_CACHE_TTL)
            self._save_file_cache(SCHEDULE_CACHE_FILE, cache_data)
            return scraped

        return None

    def _scrape_next_release(self) -> Optional[Dict[str, Any]]:
        """
        Chicago Fed Data Release Calendarから次回CARTS発表日をスクレイピング
        """
        try:
            print("Scraping next CARTS release date from Chicago Fed...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = requests.get(CARTS_SCHEDULE_URL, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            today = date.today()

            # CARTSテーブルを探す（id="carts-table"）
            carts_table = soup.find("table", id="carts-table")

            if carts_table:
                rows = carts_table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    if len(cells) >= 2:
                        # 1列目: Reference Period, 2列目: Preliminary Release, 3列目: Final Release
                        # 予備版の日付を優先
                        for i, cell in enumerate(cells[1:], 1):
                            date_text = cell.get_text(strip=True)
                            parsed_date = self._parse_date_string(date_text)
                            if parsed_date and parsed_date >= today:
                                reference_period = cells[0].get_text(strip=True)
                                release_type = "Preliminary" if i == 1 else "Final"
                                return {
                                    "date": parsed_date.strftime("%Y-%m-%d"),
                                    "label": f"CARTS ({reference_period}) {release_type} - {parsed_date.strftime('%b %d, %Y')}"
                                }

            # テーブルが見つからない場合は一般的なパターンで検索
            # 「CARTS」を含む行を探す
            for table in soup.find_all("table"):
                text = table.get_text()
                if "CARTS" in text.upper() or "Advance Retail" in text:
                    rows = table.find_all("tr")
                    for row in rows:
                        cells = row.find_all(["td", "th"])
                        for cell in cells:
                            date_text = cell.get_text(strip=True)
                            parsed_date = self._parse_date_string(date_text)
                            if parsed_date and parsed_date >= today:
                                return {
                                    "date": parsed_date.strftime("%Y-%m-%d"),
                                    "label": f"CARTS - {parsed_date.strftime('%b %d, %Y')}"
                                }

            print("Could not find next CARTS release date on Chicago Fed page")
            return None

        except Exception as e:
            print(f"Error scraping Chicago Fed page: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_date_string(self, date_str: str) -> Optional[date]:
        """日付文字列をパース"""
        date_str = date_str.strip()
        if not date_str or date_str.lower() in ["to be announced", "tba", "-", ""]:
            return None

        try:
            formats = [
                "%B %d, %Y",     # January 02, 2025
                "%b %d, %Y",     # Jan 02, 2025
                "%B %d %Y",      # January 02 2025
                "%b %d %Y",      # Jan 02 2025
                "%m/%d/%Y",      # 01/02/2025
                "%Y-%m-%d",      # 2025-01-02
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt).date()
                except ValueError:
                    continue

            # 時刻部分を除去して再試行
            date_str_clean = re.sub(r'\s*\([^)]*\)', '', date_str)
            date_str_clean = re.sub(r'\s*at\s+\d+:\d+.*', '', date_str_clean, flags=re.IGNORECASE)
            for fmt in formats:
                try:
                    return datetime.strptime(date_str_clean.strip(), fmt).date()
                except ValueError:
                    continue

        except Exception:
            pass

        return None

    def _load_file_cache(self, cache_file: Path) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not cache_file.exists():
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, cache_file: Path, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {cache_file}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        redis_client.delete(self.SCHEDULE_CACHE_KEY)
        redis_client.delete(self.PRICE_CACHE_KEY)
        return redis_client.delete(self.WEEKLY_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        weekly_exists = redis_client.exists(self.WEEKLY_CACHE_KEY)
        price_exists = redis_client.exists(self.PRICE_CACHE_KEY)

        weekly_data = redis_client.get(self.WEEKLY_CACHE_KEY) if weekly_exists else None
        price_data = redis_client.get(self.PRICE_CACHE_KEY) if price_exists else None

        return {
            "weekly": {
                "cache_key": self.WEEKLY_CACHE_KEY,
                "exists": weekly_exists,
                "last_updated": weekly_data.get("last_updated") if weekly_data else None,
                "data_count": len(weekly_data.get("data", [])) if weekly_data else 0,
                "latest": weekly_data.get("latest") if weekly_data else None,
            },
            "price": {
                "cache_key": self.PRICE_CACHE_KEY,
                "exists": price_exists,
                "last_updated": price_data.get("last_updated") if price_data else None,
                "data_count": len(price_data.get("data", [])) if price_data else 0,
                "latest": price_data.get("latest") if price_data else None,
            },
            "next_release": self._get_next_release(),
            "file_cache_weekly_exists": WEEKLY_CACHE_FILE.exists(),
            "file_cache_price_exists": PRICE_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
carts_service = CartsService()
