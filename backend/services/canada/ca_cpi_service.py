"""
カナダ消費者物価指数（CPI）サービス

指標:
- CPI All-items (総合CPI)
- CPI-trim (刈込平均)
- CPI-median (中央値)
- CPI-common (共通)

データソース:
- Statistics Canada Table 18-10-0004-01 (CPI月次前年比)
- Statistics Canada Table 18-10-0006-01 (CPI月次指数)
- Statistics Canada Table 18-10-0256-02 (CPI-trim, median, common)

発表スケジュール:
- 毎月中旬
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

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ca_cpi_cache.json"

# Statistics Canada CSV URLs
# Table 18-10-0004-01: CPI月次 (季節調整前, 2002=100) - YoYおよびMoM計算用
STATCAN_CPI_INDEX_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/18100004-eng.zip"
# Table 18-10-0256-02: CPI-trim, median, common (前年比)
STATCAN_CPI_CORE_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/18100256-eng.zip"

# FMPイベントパターン
FMP_CPI_PATTERN = "CPI"
CA_CPI_ECONALPHA_ID = "ca_cpi"


class CaCpiService:
    """カナダCPIサービス"""

    DATA_CACHE_KEY = "canada:ca_cpi:data"
    CACHE_TTL = 86400  # 24時間

    def __init__(self):
        pass

    def get_ca_cpi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダCPIデータを取得"""
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
            latest = self._get_latest_values(result)
            next_release = get_next_release_by_pattern(FMP_CPI_PATTERN, country="CA")

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Statistics Canada",
                    "tables": ["18-10-0004-01", "18-10-0006-01", "18-10-0256-02"],
                    "indicator": "Consumer Price Index (CPI)",
                    "description": "カナダ消費者物価指数",
                    "unit": "%",
                    "frequency": "monthly",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
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
                "last_updated": datetime.now(JST).isoformat(),
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
        """Statistics CanadaからCPIデータを取得"""
        try:
            # 1. 総合CPI Indexを取得（YoYおよびMoM計算用）
            # Table 18-10-0004-01: 季節調整前インデックス
            index_data = self._fetch_cpi_index()

            # 2. YoYとMoMをインデックスから計算
            yoy_data = self._calculate_yoy_from_index(index_data)
            mom_data = self._calculate_mom_from_index(index_data)

            # 3. CPI-trim, median, commonを取得
            core_data = self._fetch_cpi_core()

            # データをマージ
            result = self._merge_cpi_data(yoy_data, mom_data, index_data, core_data)

            print(f"[CaCpi] Loaded {len(result)} monthly records")
            if result:
                print(f"[CaCpi] Date range: {result[0]['date']} to {result[-1]['date']}")

            return result

        except Exception as e:
            print(f"[CaCpi] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_cpi_index(self) -> Dict[str, float]:
        """
        総合CPI指数を取得（季節調整前）
        Table 18-10-0004-01: CPI月次（季節調整前、2002=100）
        """
        try:
            print(f"[CaCpi] Fetching Index data from: {STATCAN_CPI_INDEX_URL}")

            resp = requests.get(STATCAN_CPI_INDEX_URL, timeout=90)
            resp.raise_for_status()

            z = zipfile.ZipFile(io.BytesIO(resp.content))
            csv_name = [n for n in z.namelist() if n.endswith('.csv') and not n.startswith('_')][0]

            with z.open(csv_name) as f:
                df = pd.read_csv(f, low_memory=False)

            # All-itemsのデータを抽出（カナダ全体）
            all_items = df[
                (df['Products and product groups'] == 'All-items') &
                (df['GEO'] == 'Canada')
            ].copy()

            result = {}
            for _, row in all_items.iterrows():
                date_str = row['REF_DATE']
                value = row['VALUE']

                if pd.isna(value):
                    continue

                try:
                    formatted_date = f"{date_str}-01"
                    result[formatted_date] = float(value)
                except (ValueError, TypeError):
                    continue

            print(f"[CaCpi] Loaded {len(result)} Index records")
            return result

        except Exception as e:
            print(f"[CaCpi] Error fetching Index: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _calculate_yoy_from_index(self, index_data: Dict[str, float]) -> Dict[str, float]:
        """インデックスから前年比（YoY）を計算"""
        result = {}
        for date_str, current_index in index_data.items():
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                # 12ヶ月前の日付
                prev_year_date = f"{dt.year - 1:04d}-{dt.month:02d}-01"

                if prev_year_date in index_data:
                    prev_index = index_data[prev_year_date]
                    if prev_index > 0:
                        yoy = ((current_index - prev_index) / prev_index) * 100
                        result[date_str] = round(yoy, 2)
            except (ValueError, TypeError):
                continue

        print(f"[CaCpi] Calculated {len(result)} YoY records from index")
        return result

    def _calculate_mom_from_index(self, index_data: Dict[str, float]) -> Dict[str, float]:
        """インデックスから前月比（MoM）を計算"""
        result = {}
        for date_str, current_index in index_data.items():
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                # 前月の日付
                prev_month = dt.month - 1 if dt.month > 1 else 12
                prev_year = dt.year if dt.month > 1 else dt.year - 1
                prev_month_date = f"{prev_year:04d}-{prev_month:02d}-01"

                if prev_month_date in index_data:
                    prev_index = index_data[prev_month_date]
                    if prev_index > 0:
                        mom = ((current_index - prev_index) / prev_index) * 100
                        result[date_str] = round(mom, 2)
            except (ValueError, TypeError):
                continue

        print(f"[CaCpi] Calculated {len(result)} MoM records from index")
        return result

    def _fetch_cpi_core(self) -> Dict[str, Dict[str, float]]:
        """CPI-trim, median, commonを取得（前年比）"""
        try:
            print(f"[CaCpi] Fetching Core data from: {STATCAN_CPI_CORE_URL}")

            resp = requests.get(STATCAN_CPI_CORE_URL, timeout=60)
            resp.raise_for_status()

            z = zipfile.ZipFile(io.BytesIO(resp.content))
            csv_name = [n for n in z.namelist() if n.endswith('.csv') and not n.startswith('_')][0]

            with z.open(csv_name) as f:
                df = pd.read_csv(f)

            # 各コア指標のマッピング（部分一致で検索、YoYのみ）
            # 実際の列値:
            # - 'Measure of core inflation based on a trimmed mean approach, CPI-trim (year-over-year percent change)'
            # - 'Measure of core inflation based on a weighted median approach, CPI-median (year-over-year percent change)'
            # - 'Measure of core inflation based on a factor model, CPI-common (year-over-year percent change)'
            core_indicators = {
                'CPI-trim (year-over-year': 'trim',
                'CPI-median (year-over-year': 'median',
                'CPI-common (year-over-year': 'common',
            }

            result: Dict[str, Dict[str, float]] = {}

            for search_pattern, key in core_indicators.items():
                # 部分一致でフィルタ（regex=Falseでリテラル検索、括弧を含むため）
                indicator_data = df[
                    (df['Alternative measures'].str.contains(search_pattern, na=False, regex=False)) &
                    (df['GEO'] == 'Canada')
                ].copy()

                print(f"[CaCpi] Found {len(indicator_data)} records for {key}")

                for _, row in indicator_data.iterrows():
                    date_str = row['REF_DATE']
                    value = row['VALUE']

                    if pd.isna(value):
                        continue

                    try:
                        formatted_date = f"{date_str}-01"
                        if formatted_date not in result:
                            result[formatted_date] = {}
                        result[formatted_date][key] = float(value)
                    except (ValueError, TypeError):
                        continue

            print(f"[CaCpi] Loaded core data for {len(result)} dates")
            return result

        except Exception as e:
            print(f"[CaCpi] Error fetching Core: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _merge_cpi_data(
        self,
        yoy_data: Dict[str, float],
        mom_data: Dict[str, float],
        index_data: Dict[str, float],
        core_data: Dict[str, Dict[str, float]]
    ) -> List[Dict[str, Any]]:
        """CPIデータをマージ"""
        # すべての日付を収集
        all_dates = set(yoy_data.keys()) | set(mom_data.keys()) | set(index_data.keys()) | set(core_data.keys())

        # 2000年以降のみ
        filtered_dates = [d for d in all_dates if d >= "2000-01-01"]
        filtered_dates.sort()

        result = []
        for date_str in filtered_dates:
            item: Dict[str, Any] = {"date": date_str}

            # YoY
            if date_str in yoy_data:
                item["yoy"] = round(yoy_data[date_str], 2)

            # MoM
            if date_str in mom_data:
                item["mom"] = round(mom_data[date_str], 2)

            # Index
            if date_str in index_data:
                item["index"] = round(index_data[date_str], 2)

            # Core指標
            if date_str in core_data:
                core = core_data[date_str]
                if "trim" in core:
                    item["trim"] = round(core["trim"], 2)
                if "median" in core:
                    item["median"] = round(core["median"], 2)
                if "common" in core:
                    item["common"] = round(core["common"], 2)

            # YoYまたはコア指標がある場合のみ追加
            if "yoy" in item or "trim" in item:
                result.append(item)

        return result

    def _get_latest_values(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """最新値を取得"""
        if not data:
            return {}

        latest = data[-1].copy()
        return latest

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            return should_refresh_by_pattern(FMP_CPI_PATTERN, last_updated_str, country="CA")
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
            print(f"[CaCpi] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaCpi] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Canada CPI",
            "source": "Statistics Canada",
            "tables": ["18-10-0004-01", "18-10-0006-01", "18-10-0256-02"],
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(FMP_CPI_PATTERN, country="CA"),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_cpi_service = CaCpiService()
