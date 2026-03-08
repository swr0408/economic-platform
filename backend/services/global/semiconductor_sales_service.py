"""
WSTS 半導体売上高サービス

指標:
- WSTS Historical Billings (月次) - 5地域: Worldwide, Americas, Europe, Japan, Asia Pacific
- WSTS 3-Month Moving Average (3MMA) - 同5地域

データソース:
- WSTS (World Semiconductor Trade Statistics) - Excel

キャッシュ方式: 24時間固定TTL方式
"""
import json
import io
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "global" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CACHE_FILE = CACHE_DIR / "semiconductor_sales_cache.json"

REGION_MAP = {
    "Americas": "americas",
    "Europe": "europe",
    "Japan": "japan",
    "Asia Pacific": "asia_pacific",
    "Worldwide": "worldwide",
}

REGIONS = ["worldwide", "americas", "europe", "japan", "asia_pacific"]


class SemiconductorSalesService:
    """WSTS 半導体売上高サービス"""

    CACHE_KEY = "global:semiconductor_sales:data"

    XLSX_URL = "https://www.wsts.org/esraCMS/extension/media/f/WST/7430/WSTS-Historical-Billings-Report-Dec_2025.xlsx"

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """半導体売上高データを取得"""
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "yoy_data": cached_data.get("yoy_data", []),
                        "mma_data": cached_data.get("mma_data", []),
                        "mma_yoy_data": cached_data.get("mma_yoy_data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": None,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        xlsx_content = self._download_xlsx()
        if xlsx_content:
            raw_data = self._parse_sheet(xlsx_content, "Monthly Data")
            mma_data = self._parse_sheet(xlsx_content, "3MMA")
            yoy_data = self._calculate_yoy(raw_data)
            mma_yoy_data = self._calculate_yoy(mma_data) if mma_data else []
            latest = raw_data[-1] if raw_data else None

            metadata = {
                "source": "WSTS (World Semiconductor Trade Statistics)",
                "indicator": "Semiconductor Sales",
                "unit": "Billion USD",
                "frequency": "Monthly",
                "description": "Monthly semiconductor billings by region",
            }

            cache_payload = {
                "data": raw_data,
                "yoy_data": yoy_data,
                "mma_data": mma_data or [],
                "mma_yoy_data": mma_yoy_data,
                "latest": latest,
                "metadata": metadata,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": raw_data,
                "yoy_data": yoy_data,
                "mma_data": mma_data or [],
                "mma_yoy_data": mma_yoy_data,
                "latest": latest,
                "metadata": metadata,
                "next_release": None,
                "cached": False,
                "source": "xlsx",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "yoy_data": file_cache.get("yoy_data", []),
                "mma_data": file_cache.get("mma_data", []),
                "mma_yoy_data": file_cache.get("mma_yoy_data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": None,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [], "yoy_data": [], "mma_data": [], "mma_yoy_data": [],
            "latest": None, "metadata": {},
            "next_release": None, "cached": False, "source": "none", "last_updated": None,
        }

    def _download_xlsx(self) -> Optional[bytes]:
        """WSTS Excelファイルをダウンロード"""
        try:
            print("[SemiconductorSales] Fetching WSTS Excel...")
            response = requests.get(self.XLSX_URL, timeout=60)
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            print(f"[SemiconductorSales] Excel request error: {e}")
            return None

    def _parse_sheet(self, xlsx_content: bytes, sheet_name: str) -> Optional[List[Dict]]:
        """Excelシートをパース（Monthly Data / 3MMA 共通）"""
        try:
            df = pd.read_excel(
                io.BytesIO(xlsx_content),
                sheet_name=sheet_name,
                header=None,
            )

            # 年ブロックを検出してパース
            # 構造: Row N = 年(int), Row N+1..N+5 = 地域データ
            year_rows = []
            for row_idx in range(df.shape[0]):
                val = df.iloc[row_idx, 0]
                if isinstance(val, (int, float)) and pd.notna(val) and 1900 < val < 2100:
                    year_rows.append((row_idx, int(val)))

            # 月名→月番号 (Col1=Jan=1, Col2=Feb=2, ..., Col12=Dec=12)
            result_map: Dict[str, Dict[str, float]] = {}  # date -> {region: value}

            for year_row_idx, year in year_rows:
                # 次の5行が地域データ
                for offset in range(1, 6):
                    region_row = year_row_idx + offset
                    if region_row >= df.shape[0]:
                        break

                    region_name = str(df.iloc[region_row, 0]).strip()
                    region_key = REGION_MAP.get(region_name)
                    if not region_key:
                        continue

                    for month in range(1, 13):
                        col_idx = month  # Col1=Jan, Col2=Feb, ...
                        if col_idx >= df.shape[1]:
                            break

                        val = df.iloc[region_row, col_idx]
                        if pd.isna(val):
                            continue

                        try:
                            # 1000 US$ → billion USD
                            value_billion = round(float(val) / 1_000_000, 4)
                            date_str = f"{year:04d}-{month:02d}-01"

                            if date_str not in result_map:
                                result_map[date_str] = {}
                            result_map[date_str][region_key] = value_billion
                        except (ValueError, TypeError):
                            continue

            # ソートしてリスト化
            sorted_dates = sorted(result_map.keys())
            result = []
            for date_str in sorted_dates:
                record: Dict[str, Any] = {"date": date_str}
                region_data = result_map[date_str]
                for region in REGIONS:
                    record[region] = region_data.get(region)
                # worldwideがないレコードはスキップ
                if record.get("worldwide") is not None:
                    result.append(record)

            print(f"[SemiconductorSales] Fetched {len(result)} records from '{sheet_name}'")
            return result

        except Exception as e:
            print(f"[SemiconductorSales] Error parsing sheet '{sheet_name}': {e}")
            return None

    def _calculate_yoy(self, data: List[Dict]) -> List[Dict]:
        """前年比（YoY%）を計算"""
        # date -> record マップ
        date_map = {r["date"]: r for r in data}
        yoy_result = []

        for record in data:
            date_str = record["date"]
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                prev_date = f"{dt.year - 1:04d}-{dt.month:02d}-01"
            except ValueError:
                continue

            prev_record = date_map.get(prev_date)
            if not prev_record:
                continue

            yoy_item: Dict[str, Any] = {"date": date_str}
            has_any = False
            for region in REGIONS:
                current = record.get(region)
                prev = prev_record.get(region)
                if current is not None and prev is not None and prev > 0:
                    yoy_item[region] = round((current - prev) / prev * 100, 2)
                    has_any = True
                else:
                    yoy_item[region] = None

            if has_any:
                yoy_result.append(yoy_item)

        return yoy_result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """24時間経過またはJST 6:00を過ぎた新しい日なら更新"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            if (now - last_updated) > timedelta(hours=24):
                return True

            if last_updated.date() < now.date() and now.hour >= 6:
                return True

            return False
        except Exception:
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not CACHE_FILE.exists():
                return None
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[SemiconductorSales] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SemiconductorSales] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        exists = redis_client.exists(self.CACHE_KEY)
        cached = redis_client.get(self.CACHE_KEY) if exists else None
        return {
            "indicator": "WSTS Semiconductor Sales (Monthly)",
            "source": "WSTS Excel",
            "cache_key": self.CACHE_KEY,
            "exists": exists,
            "last_updated": cached.get("last_updated") if cached else None,
            "data_count": len(cached.get("data", [])) if cached else 0,
        }


# シングルトンインスタンス
semiconductor_sales_service = SemiconductorSalesService()
