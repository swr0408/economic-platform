"""
Bank of England OIS Forward Curve Service
BOE OIS フォワードカーブデータを取得

指標:
- OIS フォワードカーブ (1M-12M)
- 当日と前日の比較データ

データソース:
- Bank of England Yield Curves ZIP file
- ファイル: OIS daily data current month.xlsx
- シート: 1. fwds, short end

更新スケジュール:
- 1日2回 16:00、3:00 JST

キャッシュ方式: 時刻ベース判定方式
"""
import json
import requests
import pandas as pd
import zipfile
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path
from io import BytesIO

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "boe_ois_curve_cache.json"


class BOEOISCurveService:
    """BOE OIS フォワードカーブサービス"""

    DATA_CACHE_KEY = "uk:boe_ois_curve:data"

    # BOE Yield Curves ZIP URL
    BOE_ZIP_URL = "https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/latest-yield-curve-data.zip"
    EXCEL_FILENAME = "OIS daily data current month.xlsx"
    SHEET_NAME = "1. fwds, short end"

    def __init__(self):
        pass

    def get_ois_curve_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        OISカーブデータを取得

        Args:
            force_refresh: 強制更新フラグ

        Returns:
            OISカーブデータ
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", {}),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ZIPファイルからデータ取得
        zip_result = self._fetch_zip_data()
        if zip_result:
            cache_payload = {
                "data": zip_result,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": zip_result,
                "cached": False,
                "source": "boe_zip",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", {}),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": {
                "current": None,
                "previous": None,
                "metadata": {}
            },
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def get_chart_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        チャート表示用のデータを取得

        Returns:
            チャート用データ (current, previous)
        """
        data = self.get_ois_curve_data(force_refresh=force_refresh)

        if not data or not data.get("data"):
            return {
                "current": None,
                "previous": None,
                "metadata": {}
            }

        ois_data = data.get("data", {})

        return {
            "current": ois_data.get("current"),
            "previous": ois_data.get("previous"),
            "metadata": ois_data.get("metadata", {})
        }

    def _fetch_zip_data(self) -> Optional[Dict[str, Any]]:
        """
        BOEのZIPファイルからOISカーブデータを取得
        """
        try:
            print(f"[BOE OIS Curve] Fetching data from {self.BOE_ZIP_URL}")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(self.BOE_ZIP_URL, headers=headers, timeout=120)
            response.raise_for_status()

            print(f"[BOE OIS Curve] Successfully downloaded ZIP file: {len(response.content)} bytes")

            # ZIPからExcelファイルを抽出
            with zipfile.ZipFile(BytesIO(response.content)) as z:
                if self.EXCEL_FILENAME not in z.namelist():
                    print(f"[BOE OIS Curve] File {self.EXCEL_FILENAME} not found in ZIP")
                    print(f"[BOE OIS Curve] Available files: {z.namelist()}")
                    return None

                with z.open(self.EXCEL_FILENAME) as excel_file:
                    df = pd.read_excel(excel_file, sheet_name=self.SHEET_NAME, header=None)

            print(f"[BOE OIS Curve] Excel file loaded, shape: {df.shape}")

            # データを処理
            return self._process_ois_data(df)

        except Exception as e:
            print(f"[BOE OIS Curve] Error fetching ZIP data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _process_ois_data(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        OIS Excelデータを構造化されたフォーマットに処理

        Args:
            df: ExcelファイルからのDataFrame

        Returns:
            current と previous の日付を含む処理済みデータ
        """
        try:
            # Row 0: カラムラベル
            # Row 1: 日付ヘッダー
            # Row 2: "Month" ラベルと月番号 (1-12)
            # Row 3+: 日付とOISレートのデータ行

            month_row_idx = 2

            # 月カラムを抽出 (Month1 to Month12)
            month_columns = []
            for col_idx in range(1, len(df.columns)):
                cell_value = df.iloc[month_row_idx, col_idx]
                if pd.notna(cell_value):
                    try:
                        month_num = int(cell_value)
                        if 1 <= month_num <= 12:
                            month_columns.append((col_idx, f"Month{month_num}"))
                    except (ValueError, TypeError):
                        continue

            print(f"[BOE OIS Curve] Found {len(month_columns)} month columns")

            # データ行を抽出 (row 3から開始)
            data_start_row = 3
            dates = []
            data_by_date = {}

            for row_idx in range(data_start_row, len(df)):
                date_cell = df.iloc[row_idx, 0]

                if pd.isna(date_cell):
                    continue

                try:
                    if isinstance(date_cell, datetime):
                        date_obj = date_cell
                    else:
                        date_obj = pd.to_datetime(date_cell)

                    date_str = date_obj.strftime('%Y-%m-%d')

                    # 各月のOISレートを抽出
                    month_data = {}
                    for col_idx, month_name in month_columns:
                        value = df.iloc[row_idx, col_idx]
                        if pd.notna(value):
                            try:
                                month_data[month_name] = float(value)
                            except (ValueError, TypeError):
                                month_data[month_name] = None
                        else:
                            month_data[month_name] = None

                    if month_data:
                        dates.append(date_str)
                        data_by_date[date_str] = month_data

                except Exception as e:
                    print(f"[BOE OIS Curve] Error processing row {row_idx}: {e}")
                    continue

            # 日付をソート
            dates = sorted(dates)

            if len(dates) < 1:
                print("[BOE OIS Curve] No valid dates found")
                return {
                    "current": None,
                    "previous": None,
                    "metadata": {"error": "No valid data found"}
                }

            # 最新と前日のデータを取得
            current_date = dates[-1]
            previous_date = dates[-2] if len(dates) >= 2 else None

            result = {
                "current": {
                    "date": current_date,
                    "data": data_by_date[current_date]
                },
                "previous": {
                    "date": previous_date,
                    "data": data_by_date[previous_date]
                } if previous_date else None,
                "metadata": {
                    "source": "Bank of England",
                    "indicator": "OIS Forward Curve",
                    "total_dates": len(dates),
                    "date_range": {
                        "start": dates[0],
                        "end": dates[-1]
                    }
                }
            }

            print(f"[BOE OIS Curve] Processed data: current={current_date}, previous={previous_date}")
            return result

        except Exception as e:
            print(f"[BOE OIS Curve] Error processing data: {e}")
            import traceback
            traceback.print_exc()
            return {
                "current": None,
                "previous": None,
                "metadata": {"error": str(e)}
            }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        更新タイミング: 16:00 と 3:00 JST
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 1日以上経過していたら更新
            if (now - last_updated) > timedelta(days=1):
                return True

            # 更新時刻を確認 (16:00 と 3:00 JST)
            update_hours = [3, 16]

            for update_hour in update_hours:
                update_time = now.replace(hour=update_hour, minute=0, second=0, microsecond=0)

                # 更新時刻を過ぎていて、前回更新が更新時刻より前なら更新
                if now >= update_time and last_updated < update_time:
                    return True

            return False
        except Exception as e:
            print(f"[BOE OIS Curve] Error checking refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[BOE OIS Curve] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[BOE OIS Curve] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "BOE OIS Curve",
            "source": "Bank of England ZIP",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
boe_ois_curve_service = BOEOISCurveService()
