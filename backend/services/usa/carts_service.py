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
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

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
    ECONALPHA_ID = "carts"  # FMPマッピング用ID

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

        return {
            "weekly": weekly_result,
            "price": price_result,
            "next_release": None,
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
                        "next_release": None,
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
                        "next_release": None,
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
                "next_release": None,
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
                "next_release": None,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
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

        FMPスケジュールベースの3分方式で判定
        """
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)


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
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_weekly_exists": WEEKLY_CACHE_FILE.exists(),
            "file_cache_price_exists": PRICE_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
carts_service = CartsService()
