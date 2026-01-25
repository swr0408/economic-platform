"""
シカゴ連銀小売物価指数（CARTS Fig6）サービス
Retail & Food Services Prices Ex. Auto (SA, y/y % chg.) データを取得

指標:
- BEA: Bureau of Economic Analysis（廃止）
- 商品CPI（自動車除く）: CPI for Commodities Ex. Auto
- CARTS Nowcast: シカゴ連銀CPI予想

データソース:
- ZIP: https://api.data.chicagofed.org/CARTS/carts-dashboard.zip
- Excel: carts-dashboard-figures_real.xlsx (fig6シート)

発表スケジュール:
- 予備版: 毎月第1木曜日 8:30 ET
- 確定版: 毎月第2金曜日 8:30 ET

キャッシュ方式: Chicago Fed発表日ベース判定方式（スクレイピング）
"""
import io
import os
import json
import zipfile
import tempfile
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client
from services.usa.chicago_fed_schedule_utils import (
    get_carts_next_release,
    should_refresh_by_chicago_fed_schedule,
)


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "retail_food_services_price_cache.json"


class RetailFoodServicesPriceService:
    """シカゴ連銀小売物価指数（CARTS Fig6）サービス"""

    DATA_CACHE_KEY = "inflation:retail_food_services_price:data"

    # Chicago Fed CARTS URLs
    CARTS_ZIP_URL = "https://api.data.chicagofed.org/CARTS/carts-dashboard.zip"
    EXCEL_FILENAME = "carts-dashboard-figures_real.xlsx"
    FIG6_SHEET = "fig6"

    def __init__(self):
        pass

    def get_retail_food_services_price_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        シカゴ連銀小売物価指数データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "bea": float|null, "cpi": float|null, "carts_nowcast": float|null}, ...],
                "latest": {...},
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
                        "latest": cached_data.get("latest"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ZIPからデータを取得
        result = self._fetch_from_carts_zip()
        if result:
            latest = result[-1] if result else None
            next_release = get_carts_next_release()

            cache_payload = {
                "data": result,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            # Redisに保存（TTLなし）
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "Chicago Fed CARTS",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": file_cache.get("next_release"),
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

    def _fetch_from_carts_zip(self) -> List[Dict[str, Any]]:
        """Chicago Fed CARTS ZIPファイルからfig6データを取得"""
        try:
            print(f"Fetching CARTS ZIP from {self.CARTS_ZIP_URL}...")

            response = requests.get(self.CARTS_ZIP_URL, timeout=60)
            response.raise_for_status()
            zip_content = response.content

            # ZIPファイルを展開してExcelファイルを読み込み
            data = self._extract_and_read_excel(zip_content)

            print(f"Fetched {len(data)} records from CARTS fig6")
            return data

        except Exception as e:
            print(f"Error fetching CARTS fig6 data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _extract_and_read_excel(self, zip_content: bytes) -> List[Dict[str, Any]]:
        """ZIPファイルからExcelファイルを展開して読み込み"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # ZIPファイルを展開
            with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # Excelファイルのパスを探す
            excel_path = None
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.lower() == self.EXCEL_FILENAME.lower():
                        excel_path = os.path.join(root, file)
                        break
                if excel_path:
                    break

            if excel_path is None:
                raise FileNotFoundError(f"Excel file '{self.EXCEL_FILENAME}' not found in ZIP")

            # fig6シートを読み込み
            return self._read_fig6_sheet(excel_path)

    def _read_fig6_sheet(self, excel_path: str) -> List[Dict[str, Any]]:
        """
        Excelファイルからfig6シートを読み込んでデータを抽出
        BEA、CPI、CARTS Nowcastの3つのデータ系列を抽出
        """
        try:
            # fig6シートを読み込み
            df = pd.read_excel(excel_path, sheet_name=self.FIG6_SHEET, header=None)

            print(f"Fig6 sheet shape: {df.shape}")

            data = []

            # ヘッダー行を特定（通常は最初の行）
            data_start_row = 1

            # 列の特定
            date_col = 0      # 日付列
            bea_col = 1       # BEA列
            cpi_col = 2       # CPI列
            carts_col = 3     # CARTS Nowcast列

            # 各行を処理
            for i in range(data_start_row, len(df)):
                try:
                    date_value = df.iloc[i, date_col]

                    # 空の日付行をスキップ
                    if pd.isna(date_value):
                        continue

                    # 日付の変換
                    if isinstance(date_value, (pd.Timestamp, datetime)):
                        formatted_date = date_value.strftime('%Y-%m-%d')
                    elif isinstance(date_value, str):
                        try:
                            parsed_date = pd.to_datetime(date_value)
                            formatted_date = parsed_date.strftime('%Y-%m-%d')
                        except Exception:
                            continue
                    else:
                        # 数値の場合（Excelの日付シリアル値の可能性）
                        try:
                            parsed_date = pd.to_datetime(
                                date_value, origin='1899-12-30', unit='D'
                            )
                            formatted_date = parsed_date.strftime('%Y-%m-%d')
                        except Exception:
                            continue

                    # BEA値の変換
                    bea_value = None
                    if bea_col < len(df.columns):
                        bea_raw = df.iloc[i, bea_col]
                        if not pd.isna(bea_raw):
                            try:
                                bea_value = round(float(bea_raw), 2)
                            except Exception:
                                pass

                    # CPI値の変換
                    cpi_value = None
                    if cpi_col < len(df.columns):
                        cpi_raw = df.iloc[i, cpi_col]
                        if not pd.isna(cpi_raw):
                            try:
                                cpi_value = round(float(cpi_raw), 2)
                            except Exception:
                                pass

                    # CARTS Nowcast値の変換
                    carts_value = None
                    if carts_col < len(df.columns):
                        carts_raw = df.iloc[i, carts_col]
                        if not pd.isna(carts_raw):
                            try:
                                carts_value = round(float(carts_raw), 2)
                            except Exception:
                                pass

                    # データポイントを追加（少なくとも1つの値が有効な場合）
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

            print(f"Extracted {len(data)} data points from fig6 sheet")

            if len(data) > 0:
                print(f"First data point: {data[0]}")
                print(f"Last data point: {data[-1]}")

            return data

        except Exception as e:
            print(f"Error reading fig6 sheet: {e}")
            raise

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（Chicago Fed発表日ベース）"""
        return should_refresh_by_chicago_fed_schedule(last_updated_str)

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
            "indicator": "Retail & Food Services Prices (CARTS Fig6)",
            "source": "Chicago Fed CARTS",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "next_release": cached_data.get("next_release") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
retail_food_services_price_service = RetailFoodServicesPriceService()
