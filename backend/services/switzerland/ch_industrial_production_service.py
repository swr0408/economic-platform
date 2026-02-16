"""
スイス鉱工業生産サービス
BFS（連邦統計局）から鉱工業生産データを取得

指標:
- Industrial Production MoM（前月比）- 月次
- Industrial Production YoY（前年比）- 月次
- Industrial Production QoQ（前期比）- 四半期
- Industrial Production QYoY（四半期前年比）- 四半期

データソース:
- BFS (Federal Statistical Office / Bundesamt für Statistik)
- https://www.bfs.admin.ch/

Excelファイル:
- 月次前月比: https://dam-api.bfs.admin.ch/hub/api/dam/assets/36297886/master
- 月次前年比: https://dam-api.bfs.admin.ch/hub/api/dam/assets/36297892/master
- 四半期前期比: https://dam-api.bfs.admin.ch/hub/api/dam/assets/36297868/master
- 四半期前年比: https://dam-api.bfs.admin.ch/hub/api/dam/assets/36297874/master

発表スケジュール:
- 四半期ごと（FMPから次回発表日時取得）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import io
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client
from services.switzerland.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ch_industrial_production_cache.json"


class CHIndustrialProductionService:
    """スイス鉱工業生産サービス"""

    DATA_CACHE_KEY = "switzerland:ch_industrial_production:data"
    ECONALPHA_ID = "ch_industrial_production"
    FMP_COUNTRY = "CH"
    FMP_EVENT_PATTERN = "Industrial Production YoY"

    # データソースURL
    # 月次データ（Production Total - Row 4）
    MONTHLY_MOM_URL = "https://dam-api.bfs.admin.ch/hub/api/dam/assets/36297886/master"
    MONTHLY_YOY_URL = "https://dam-api.bfs.admin.ch/hub/api/dam/assets/36297892/master"
    # 四半期データ（Industrie - Row 5）
    QUARTERLY_QOQ_URL = "https://dam-api.bfs.admin.ch/hub/api/dam/assets/36297868/master"
    QUARTERLY_YOY_URL = "https://dam-api.bfs.admin.ch/hub/api/dam/assets/36297874/master"

    def __init__(self):
        pass

    def get_ch_industrial_production_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """スイス鉱工業生産データを取得"""
        # 次回発表日を取得
        next_release = get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY)

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "monthly_data": cached_data.get("monthly_data", []),
                        "quarterly_data": cached_data.get("quarterly_data", []),
                        "latest_monthly": cached_data.get("latest_monthly"),
                        "latest_quarterly": cached_data.get("latest_quarterly"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # データソースから取得
        monthly_data, quarterly_data = self._load_from_source()
        if monthly_data or quarterly_data:
            # 最新値を取得
            latest_monthly = monthly_data[-1] if monthly_data else None
            latest_quarterly = quarterly_data[-1] if quarterly_data else None

            cache_payload = {
                "monthly_data": monthly_data,
                "quarterly_data": quarterly_data,
                "latest_monthly": latest_monthly,
                "latest_quarterly": latest_quarterly,
                "metadata": {
                    "source": "BFS",
                    "indicator": "Industrial Production",
                    "description": "スイス鉱工業生産",
                    "unit": "%",
                },
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "monthly_data": monthly_data,
                "quarterly_data": quarterly_data,
                "latest_monthly": latest_monthly,
                "latest_quarterly": latest_quarterly,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "monthly_data": file_cache.get("monthly_data", []),
                "quarterly_data": file_cache.get("quarterly_data", []),
                "latest_monthly": file_cache.get("latest_monthly"),
                "latest_quarterly": file_cache.get("latest_quarterly"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "monthly_data": [],
            "quarterly_data": [],
            "latest_monthly": None,
            "latest_quarterly": None,
            "metadata": {},
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_source(self) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """BFSからデータを取得"""
        try:
            print(f"[CHIndustrialProduction] Fetching monthly MoM from: {self.MONTHLY_MOM_URL}")
            print(f"[CHIndustrialProduction] Fetching monthly YoY from: {self.MONTHLY_YOY_URL}")
            print(f"[CHIndustrialProduction] Fetching quarterly QoQ from: {self.QUARTERLY_QOQ_URL}")
            print(f"[CHIndustrialProduction] Fetching quarterly YoY from: {self.QUARTERLY_YOY_URL}")

            # 月次データ取得
            monthly_mom = self._fetch_monthly_data(self.MONTHLY_MOM_URL)
            monthly_yoy = self._fetch_monthly_data(self.MONTHLY_YOY_URL)
            print(f"[CHIndustrialProduction] Monthly MoM records: {len(monthly_mom)}")
            print(f"[CHIndustrialProduction] Monthly YoY records: {len(monthly_yoy)}")

            # 四半期データ取得
            quarterly_qoq = self._fetch_quarterly_data(self.QUARTERLY_QOQ_URL)
            quarterly_yoy = self._fetch_quarterly_data(self.QUARTERLY_YOY_URL)
            print(f"[CHIndustrialProduction] Quarterly QoQ records: {len(quarterly_qoq)}")
            print(f"[CHIndustrialProduction] Quarterly YoY records: {len(quarterly_yoy)}")

            # 月次データをマージ
            monthly_result = []
            all_monthly_dates = set(monthly_mom.keys()) | set(monthly_yoy.keys())
            for date_str in sorted(all_monthly_dates):
                mom_val = monthly_mom.get(date_str)
                yoy_val = monthly_yoy.get(date_str)
                monthly_result.append({
                    "date": date_str,
                    "mom": round(mom_val, 2) if mom_val is not None else None,
                    "yoy": round(yoy_val, 2) if yoy_val is not None else None,
                })

            # 四半期データをマージ
            quarterly_result = []
            all_quarterly_dates = set(quarterly_qoq.keys()) | set(quarterly_yoy.keys())
            for date_str in sorted(all_quarterly_dates):
                qoq_val = quarterly_qoq.get(date_str)
                qyoy_val = quarterly_yoy.get(date_str)
                quarterly_result.append({
                    "date": date_str,
                    "qoq": round(qoq_val, 2) if qoq_val is not None else None,
                    "yoy": round(qyoy_val, 2) if qyoy_val is not None else None,
                })

            print(f"[CHIndustrialProduction] Monthly total: {len(monthly_result)} records")
            print(f"[CHIndustrialProduction] Quarterly total: {len(quarterly_result)} records")

            if monthly_result:
                latest = monthly_result[-1]
                print(f"[CHIndustrialProduction] Latest monthly: {latest['date']}, MoM={latest.get('mom')}, YoY={latest.get('yoy')}")
            if quarterly_result:
                latest = quarterly_result[-1]
                print(f"[CHIndustrialProduction] Latest quarterly: {latest['date']}, QoQ={latest.get('qoq')}, YoY={latest.get('yoy')}")

            return monthly_result, quarterly_result

        except Exception as e:
            print(f"[CHIndustrialProduction] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return [], []

    def _fetch_monthly_data(self, url: str) -> Dict[str, float]:
        """月次Excelファイルからデータを取得

        BFS Excel形式（月次）:
        - シート1: Veränderungsraten（変化率）
        - Row 2: 日付（10.2010形式）
        - Row 4: Produktion Total（データ）
        - Column 3以降がデータ
        """
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()

            xls = pd.ExcelFile(io.BytesIO(resp.content))
            df = pd.read_excel(xls, sheet_name=1, header=None)

            data = {}
            # Column 3以降にデータがある
            for j in range(3, len(df.columns)):
                date_val = df.iloc[2, j]  # Row 2が日付
                value = df.iloc[4, j]     # Row 4がProduction Total

                if pd.isna(date_val) or pd.isna(value):
                    continue

                try:
                    # 日付変換（10.2010 -> 2010-10-01）
                    date_str = self._parse_monthly_date(str(date_val))
                    if date_str:
                        data[date_str] = float(value)
                except (ValueError, TypeError):
                    continue

            return data
        except Exception as e:
            print(f"[CHIndustrialProduction] Error fetching monthly data from {url}: {e}")
            return {}

    def _fetch_quarterly_data(self, url: str) -> Dict[str, float]:
        """四半期Excelファイルからデータを取得

        BFS Excel形式（四半期）:
        - シート1: Veränderungsraten（変化率）
        - Row 2: 日付（2023/IV形式）
        - Row 5: Industrie（データ）
        - Column 3以降がデータ
        """
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()

            xls = pd.ExcelFile(io.BytesIO(resp.content))
            df = pd.read_excel(xls, sheet_name=1, header=None)

            data = {}
            # Column 3以降にデータがある
            for j in range(3, len(df.columns)):
                date_val = df.iloc[2, j]  # Row 2が日付
                value = df.iloc[5, j]     # Row 5がIndustrie

                if pd.isna(date_val) or pd.isna(value):
                    continue

                try:
                    # 日付変換（2023/IV -> 2023-10-01）
                    date_str = self._parse_quarterly_date(str(date_val))
                    if date_str:
                        data[date_str] = float(value)
                except (ValueError, TypeError):
                    continue

            return data
        except Exception as e:
            print(f"[CHIndustrialProduction] Error fetching quarterly data from {url}: {e}")
            return {}

    def _parse_monthly_date(self, date_val: str) -> Optional[str]:
        """月次日付をパース（10.2010 -> 2010-10-01）"""
        try:
            parts = date_val.split('.')
            if len(parts) == 2:
                month = int(parts[0])
                year = int(parts[1])
                return f"{year}-{month:02d}-01"
        except:
            pass
        return None

    def _parse_quarterly_date(self, date_val: str) -> Optional[str]:
        """四半期日付をパース（2023/IV -> 2023-10-01）"""
        try:
            parts = date_val.split('/')
            if len(parts) == 2:
                year = int(parts[0])
                quarter_map = {'I': 1, 'II': 4, 'III': 7, 'IV': 10}
                quarter = parts[1].strip()
                if quarter in quarter_map:
                    month = quarter_map[quarter]
                    return f"{year}-{month:02d}-01"
        except:
            pass
        return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日ベース）"""
        return should_refresh_by_pattern(
            self.FMP_EVENT_PATTERN,
            last_updated_str,
            country=self.FMP_COUNTRY
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CHIndustrialProduction] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CHIndustrialProduction] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Industrial Production",
            "source": "BFS",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "monthly_count": len(cached_data.get("monthly_data", [])) if cached_data else 0,
            "quarterly_count": len(cached_data.get("quarterly_data", [])) if cached_data else 0,
            "latest_monthly": cached_data.get("latest_monthly") if cached_data else None,
            "latest_quarterly": cached_data.get("latest_quarterly") if cached_data else None,
            "next_release": get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ch_industrial_production_service = CHIndustrialProductionService()
