"""
IFO企業景況感指数サービス
IFO研究所のExcelデータからIFO Business Climate Indexデータを取得

指標:
- Geschäftsklima (Business Climate / 景況感): 企業の景況感総合指数
- Geschäftslage (Current Conditions / 現況): 現在の経済状況の評価
- Geschäftserwartungen (Expectations / 期待): 6ヶ月先の経済見通し

データソース:
- IFO研究所 Excel（主データソース）
  https://www.ifo.de/sites/default/files/secure/timeseries/gsk-d-YYYYMM.xlsx
- FMP（次回発表日時のみ）

発表スケジュール:
- 月次（毎月第4週前後 10:00 CET）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import requests
import io
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.eurozone.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ifo_business_climate_cache.json"

# IFO Excel URL テンプレート
IFO_EXCEL_URL_TEMPLATE = "https://www.ifo.de/sites/default/files/secure/timeseries/gsk-d-{yyyymm}.xlsx"


class IfoBusinessClimateService:
    """IFO企業景況感指数サービス (IFO Excel)"""

    DATA_CACHE_KEY = "economy:ifo_business_climate:data"
    ECONALPHA_ID = "ifo_business_climate"

    def __init__(self):
        pass

    def get_ifo_business_climate_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        IFO企業景況感指数データを取得

        Returns:
            {
                "climate": [...],      # 景況感指数データ（総合）
                "current": [...],      # 現況指数データ
                "expectations": [...], # 期待指数データ
                "latest_climate": {...},
                "latest_current": {...},
                "latest_expectations": {...},
                "next_release": {...},
                "cached": bool,
                "source": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
                    return {
                        "climate": cached_data.get("climate", []),
                        "current": cached_data.get("current", []),
                        "expectations": cached_data.get("expectations", []),
                        "latest_climate": cached_data.get("latest_climate"),
                        "latest_current": cached_data.get("latest_current"),
                        "latest_expectations": cached_data.get("latest_expectations"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # IFO Excelからデータを取得
        excel_data = self._load_from_ifo_excel()

        climate_data = excel_data.get("climate", [])
        current_data = excel_data.get("current", [])
        expectations_data = excel_data.get("expectations", [])

        if climate_data or current_data or expectations_data:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            latest_climate = climate_data[-1] if climate_data else None
            latest_current = current_data[-1] if current_data else None
            latest_expectations = expectations_data[-1] if expectations_data else None

            from services.usa.fmp_next_release_utils import guarded_last_updated_keys, _max_date_of
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated_keys(
                self.DATA_CACHE_KEY, ("climate", "current", "expectations"),
                _max_date_of(climate_data, current_data, expectations_data), now_str
            )
            cache_payload = {
                "climate": climate_data,
                "current": current_data,
                "expectations": expectations_data,
                "latest_climate": latest_climate,
                "latest_current": latest_current,
                "latest_expectations": latest_expectations,
                "next_release": next_release,
                "last_updated": last_updated
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "climate": climate_data,
                "current": current_data,
                "expectations": expectations_data,
                "latest_climate": latest_climate,
                "latest_current": latest_current,
                "latest_expectations": latest_expectations,
                "next_release": next_release,
                "cached": False,
                "source": "ifo_excel",
                "last_updated": last_updated
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            return {
                "climate": file_cache.get("climate", []),
                "current": file_cache.get("current", []),
                "expectations": file_cache.get("expectations", []),
                "latest_climate": file_cache.get("latest_climate"),
                "latest_current": file_cache.get("latest_current"),
                "latest_expectations": file_cache.get("latest_expectations"),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "climate": [],
            "current": [],
            "expectations": [],
            "latest_climate": None,
            "latest_current": None,
            "latest_expectations": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    # =========================================================================
    # IFO Excel関連メソッド
    # =========================================================================

    def _load_from_ifo_excel(self) -> Dict[str, List[Dict[str, Any]]]:
        """IFO研究所のExcelファイルからデータを取得"""
        try:
            import pandas as pd

            # 現在の年月から最新のExcelファイルを探す
            now = datetime.now(CET)
            excel_content = None
            used_yyyymm = None

            # 現在月から過去3ヶ月分を試す
            for i in range(4):
                target_date = now - relativedelta(months=i)
                yyyymm = target_date.strftime("%Y%m")
                url = IFO_EXCEL_URL_TEMPLATE.format(yyyymm=yyyymm)

                print(f"[IfoBusinessClimate] Trying to fetch Excel from: {url}")

                try:
                    response = requests.get(url, timeout=30)
                    if response.status_code == 200:
                        excel_content = response.content
                        used_yyyymm = yyyymm
                        print(f"[IfoBusinessClimate] Successfully fetched Excel for {yyyymm}")
                        break
                    else:
                        print(f"[IfoBusinessClimate] HTTP {response.status_code} for {yyyymm}")
                except requests.RequestException as e:
                    print(f"[IfoBusinessClimate] Request failed for {yyyymm}: {e}")

            if not excel_content:
                print("[IfoBusinessClimate] Could not fetch any Excel file")
                return {"climate": [], "current": [], "expectations": []}

            # Excelを読み込み（ヘッダーなしで読み込み、データ構造を解析）
            df = pd.read_excel(io.BytesIO(excel_content), engine='openpyxl', header=None)

            print(f"[IfoBusinessClimate] Excel shape: {df.shape}")

            # IFO Excelの構造:
            # 行0-7: ヘッダー情報
            # 行6: カラム名（Monat/Jahr, Geschäftsklima, Geschäftslage, Geschäftserwartungen, ...）
            # 行8以降: データ（MM/YYYY形式の日付, 景況感, 現況, 期待, ...）

            # カラム位置を特定（Indexwerte列を使用: 列1=景況感, 列2=現況, 列3=期待）
            date_col_idx = 0       # 日付列（A列）
            climate_col_idx = 1    # 景況感（B列: Geschäftsklima）
            current_col_idx = 2    # 現況（C列: Geschäftslage）
            expectations_col_idx = 3  # 期待（D列: Geschäftserwartungen）

            climate_result = []
            current_result = []
            expectations_result = []

            # データ行を処理（行8以降）
            for idx in range(8, len(df)):
                try:
                    row = df.iloc[idx]
                    date_val = row.iloc[date_col_idx]

                    # 日付のパース
                    date_str = None
                    if pd.isna(date_val):
                        continue

                    date_val_str = str(date_val).strip()

                    # MM/YYYY形式（例: 01/2005）
                    if '/' in date_val_str:
                        parts = date_val_str.split('/')
                        if len(parts) == 2:
                            month_part = parts[0].zfill(2)
                            year_part = parts[1]
                            if len(year_part) == 4 and year_part.isdigit():
                                date_str = f"{year_part}-{month_part}"

                    if not date_str:
                        continue

                    # 年が妥当な範囲か確認
                    year = int(date_str[:4])
                    if year < 1990 or year > 2030:
                        continue

                    # 各指標のデータを取得
                    # 景況感（Geschäftsklima）
                    climate_val = row.iloc[climate_col_idx]
                    if not pd.isna(climate_val):
                        try:
                            value = float(climate_val)
                            climate_result.append({
                                "date": date_str,
                                "value": value,
                                "source": "ifo_excel",
                            })
                        except (ValueError, TypeError):
                            pass

                    # 現況（Geschäftslage）
                    current_val = row.iloc[current_col_idx]
                    if not pd.isna(current_val):
                        try:
                            value = float(current_val)
                            current_result.append({
                                "date": date_str,
                                "value": value,
                                "source": "ifo_excel",
                            })
                        except (ValueError, TypeError):
                            pass

                    # 期待（Geschäftserwartungen）
                    expectations_val = row.iloc[expectations_col_idx]
                    if not pd.isna(expectations_val):
                        try:
                            value = float(expectations_val)
                            expectations_result.append({
                                "date": date_str,
                                "value": value,
                                "source": "ifo_excel",
                            })
                        except (ValueError, TypeError):
                            pass

                except Exception as row_error:
                    print(f"[IfoBusinessClimate] Error processing row {idx}: {row_error}")
                    continue

            # 日付でソート
            climate_result.sort(key=lambda x: x["date"])
            current_result.sort(key=lambda x: x["date"])
            expectations_result.sort(key=lambda x: x["date"])

            print(f"[IfoBusinessClimate] Loaded {len(climate_result)} climate, {len(current_result)} current, {len(expectations_result)} expectations records from IFO Excel")

            return {
                "climate": climate_result,
                "current": current_result,
                "expectations": expectations_result
            }

        except Exception as e:
            print(f"[IfoBusinessClimate] Error loading from IFO Excel: {e}")
            import traceback
            traceback.print_exc()
            return {"climate": [], "current": [], "expectations": []}

    # =========================================================================
    # キャッシュ関連メソッド
    # =========================================================================

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日時ベース）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str, max_age_hours=72)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[IfoBusinessClimate] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[IfoBusinessClimate] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "IFO Business Climate",
            "source": "IFO Excel",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "climate_count": len(cached_data.get("climate", [])) if cached_data else 0,
            "current_count": len(cached_data.get("current", [])) if cached_data else 0,
            "expectations_count": len(cached_data.get("expectations", [])) if cached_data else 0,
            "latest_climate": cached_data.get("latest_climate") if cached_data else None,
            "latest_current": cached_data.get("latest_current") if cached_data else None,
            "latest_expectations": cached_data.get("latest_expectations") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
ifo_business_climate_service = IfoBusinessClimateService()
