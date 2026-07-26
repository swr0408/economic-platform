"""
カナダ小売売上高サービス

指標:
- 小売売上高（前月比: MoM）
- 小売売上高（前年比: YoY）
- 系列: 総合, 除く自動車, 除く自動車+ガソリン

データソース:
- Statistics Canada Table 20-10-0008-01
- Retail trade sales by province and territory (x 1,000)

発表スケジュール:
- 月次（対象月の約2ヶ月後）
- 発表時刻: 08:30 ET
"""
import json
import zipfile
import io
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client
from services.canada.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")
TORONTO = ZoneInfo("America/Toronto")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ca_retail_sales_cache.json"

# Statistics Canada CSV URL
# Table 20-10-0067-01: Retail trade sales by province and territory (newer table, 2017+)
STATCAN_RETAIL_SALES_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/20100067-eng.zip"

# FMPイベントパターン
FMP_RETAIL_SALES_MOM_PATTERN = "Retail Sales MoM"
FMP_RETAIL_SALES_YOY_PATTERN = "Retail Sales YoY"
CA_RETAIL_SALES_ECONALPHA_ID = "ca_retail_sales"

# NAICSカテゴリ (Table 20-10-0067-01)
NAICS_TOTAL = "Retail trade [44-45]"
NAICS_MOTOR_VEHICLE = "Motor vehicle and parts dealers [441]"
NAICS_GASOLINE = "Gasoline stations and fuel vendors [457]"


class CaRetailSalesService:
    """カナダ小売売上高サービス"""

    DATA_CACHE_KEY = "canada:ca_retail_sales:data"
    CACHE_TTL = 86400  # 24時間

    def __init__(self):
        pass

    def get_ca_retail_sales_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダ小売売上高データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # データソースから取得
        result = self._load_from_source()
        if result:
            # 最新値を取得
            latest = result[-1] if result else None
            next_release = get_next_release_by_pattern(FMP_RETAIL_SALES_MOM_PATTERN, country="CA")
            from services.usa.fmp_next_release_utils import guarded_last_updated
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Statistics Canada",
                    "table": "20-10-0008-01",
                    "indicator": "Retail Sales",
                    "description": "カナダ小売売上高",
                    "unit": "%",
                    "frequency": "monthly",
                    "series": {
                        "total": "総合",
                        "ex_auto": "除く自動車",
                        "ex_auto_gas": "除く自動車+ガソリン",
                    },
                },
                "next_release": next_release,
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=self.CACHE_TTL)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "api",
                "last_updated": last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_source(self) -> List[Dict[str, Any]]:
        """Statistics Canadaから小売売上高データを取得"""
        try:
            print(f"[CaRetailSales] Fetching data from: {STATCAN_RETAIL_SALES_URL}")

            resp = requests.get(STATCAN_RETAIL_SALES_URL, timeout=90)
            resp.raise_for_status()

            z = zipfile.ZipFile(io.BytesIO(resp.content))
            csv_name = [n for n in z.namelist() if n.endswith('.csv') and not n.startswith('_')][0]

            with z.open(csv_name) as f:
                df = pd.read_csv(f, low_memory=False)

            print(f"[CaRetailSales] Columns: {df.columns.tolist()}")

            # カナダ全体、名目売上高（current prices）をフィルタ
            # Table 20-10-0067-01 uses 'Sales, price and volume' column
            canada_df = df[
                (df['GEO'] == 'Canada') &
                (df['Sales, price and volume'] == 'Retail sales in current prices')
            ].copy()

            print(f"[CaRetailSales] Found {len(canada_df)} current price records")

            # 各カテゴリの売上高を取得
            total_values = self._extract_values(canada_df, NAICS_TOTAL)
            motor_values = self._extract_values(canada_df, NAICS_MOTOR_VEHICLE)
            gas_values = self._extract_values(canada_df, NAICS_GASOLINE)

            print(f"[CaRetailSales] Total: {len(total_values)}, Motor: {len(motor_values)}, Gas: {len(gas_values)}")

            # MoMとYoYを計算
            result = self._calculate_growth_rates(total_values, motor_values, gas_values)

            print(f"[CaRetailSales] Loaded {len(result)} monthly records")
            if result:
                print(f"[CaRetailSales] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaRetailSales] Latest: {latest['date']} total_mom={latest.get('total_mom')}%")

            return result

        except Exception as e:
            print(f"[CaRetailSales] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _extract_values(self, df: pd.DataFrame, naics: str) -> Dict[str, float]:
        """特定NAICSカテゴリの値を抽出"""
        naics_data = df[
            df['North American Industry Classification System (NAICS)'] == naics
        ].copy()

        values = {}
        for _, row in naics_data.iterrows():
            date_str = row['REF_DATE']  # 形式: "2024-01"
            value = row['VALUE']

            if pd.isna(value):
                continue

            try:
                # 月形式を日付に変換 (例: "2024-01" -> "2024-01-01")
                formatted_date = self._month_to_date(date_str)
                if formatted_date:
                    values[formatted_date] = float(value)
            except (ValueError, TypeError):
                continue

        return values

    def _month_to_date(self, month_str: str) -> Optional[str]:
        """月形式を日付に変換（例: "2024-01" -> "2024-01-01"）"""
        try:
            month_str = month_str.strip()
            if len(month_str) == 7 and '-' in month_str:
                return f"{month_str}-01"
            return None
        except Exception:
            return None

    def _calculate_growth_rates(
        self,
        total_values: Dict[str, float],
        motor_values: Dict[str, float],
        gas_values: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """MoM（前月比）とYoY（前年比）を計算

        系列:
        - total: 総合
        - ex_auto: 除く自動車
        - ex_auto_gas: 除く自動車+ガソリン
        """
        # 共通の日付でソート
        all_dates = set(total_values.keys())
        sorted_dates = sorted(all_dates)
        result = []

        for i, date_str in enumerate(sorted_dates):
            if date_str not in total_values:
                continue

            total = total_values[date_str]
            motor = motor_values.get(date_str, 0)
            gas = gas_values.get(date_str, 0)

            # 除く自動車、除く自動車+ガソリンを計算
            ex_auto = total - motor
            ex_auto_gas = total - motor - gas

            item = {
                "date": date_str,
                "total_value": round(total, 2),
                "ex_auto_value": round(ex_auto, 2),
                "ex_auto_gas_value": round(ex_auto_gas, 2),
            }

            # MoM（前月比）を計算
            if i > 0:
                prev_date = sorted_dates[i - 1]
                if prev_date in total_values:
                    prev_total = total_values[prev_date]
                    prev_motor = motor_values.get(prev_date, 0)
                    prev_gas = gas_values.get(prev_date, 0)
                    prev_ex_auto = prev_total - prev_motor
                    prev_ex_auto_gas = prev_total - prev_motor - prev_gas

                    if prev_total > 0:
                        item["total_mom"] = round(((total - prev_total) / prev_total) * 100, 2)
                    if prev_ex_auto > 0:
                        item["ex_auto_mom"] = round(((ex_auto - prev_ex_auto) / prev_ex_auto) * 100, 2)
                    if prev_ex_auto_gas > 0:
                        item["ex_auto_gas_mom"] = round(((ex_auto_gas - prev_ex_auto_gas) / prev_ex_auto_gas) * 100, 2)

            # YoY（前年比）を計算
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            prev_year_date = f"{dt.year - 1}-{dt.month:02d}-01"

            if prev_year_date in total_values:
                prev_total = total_values[prev_year_date]
                prev_motor = motor_values.get(prev_year_date, 0)
                prev_gas = gas_values.get(prev_year_date, 0)
                prev_ex_auto = prev_total - prev_motor
                prev_ex_auto_gas = prev_total - prev_motor - prev_gas

                if prev_total > 0:
                    item["total_yoy"] = round(((total - prev_total) / prev_total) * 100, 2)
                if prev_ex_auto > 0:
                    item["ex_auto_yoy"] = round(((ex_auto - prev_ex_auto) / prev_ex_auto) * 100, 2)
                if prev_ex_auto_gas > 0:
                    item["ex_auto_gas_yoy"] = round(((ex_auto_gas - prev_ex_auto_gas) / prev_ex_auto_gas) * 100, 2)

            # MoMまたはYoYがある場合のみ追加
            if "total_mom" in item or "total_yoy" in item:
                result.append(item)

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            return should_refresh_by_pattern(FMP_RETAIL_SALES_MOM_PATTERN, last_updated_str, country="CA")
        except Exception:
            # FMP判定失敗時は24時間経過でリフレッシュ
            try:
                last_updated = datetime.fromisoformat(last_updated_str)
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=JST)
                now = datetime.now(JST)
                age = now - last_updated
                return age.total_seconds() > 86400
            except Exception:
                return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CaRetailSales] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaRetailSales] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Canada Retail Sales",
            "source": "Statistics Canada",
            "table": "20-10-0008-01",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(FMP_RETAIL_SALES_MOM_PATTERN, country="CA"),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_retail_sales_service = CaRetailSalesService()
