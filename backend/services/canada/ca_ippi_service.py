"""
カナダ工業製品価格指数（IPPI）サービス

Industrial Product Price Index - 製造業の出荷価格の変動を測定

データソース:
- Statistics Canada Table 18-10-0265-01

発表スケジュール:
- 毎月発表
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
DATA_CACHE_FILE = CACHE_DIR / "ca_ippi_cache.json"

# Statistics Canada CSV URL
# Table 18-10-0265-01: Industrial Product Price Index (IPPI)
STATCAN_IPPI_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/18100265-eng.zip"

# FMPイベントパターン
FMP_IPPI_PATTERN = "Producer Price Index"
CA_IPPI_ECONALPHA_ID = "ca_ippi"


class CaIppiService:
    """カナダIPPIサービス"""

    DATA_CACHE_KEY = "canada:ca_ippi:data"
    CACHE_TTL = 86400  # 24時間

    def __init__(self):
        pass

    def get_ca_ippi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダIPPIデータを取得"""
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
            next_release = get_next_release_by_pattern(FMP_IPPI_PATTERN, country="CA")

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Statistics Canada",
                    "table": "18-10-0265-01",
                    "indicator": "Industrial Product Price Index (IPPI)",
                    "description": "カナダ工業製品価格指数",
                    "unit": "%",
                    "frequency": "monthly",
                    "base_year": "2020=100",
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
        """Statistics CanadaからIPPIデータを取得"""
        try:
            # インデックスデータを取得
            index_data = self._fetch_ippi_index()

            # YoYとMoMをインデックスから計算
            yoy_data = self._calculate_yoy_from_index(index_data)
            mom_data = self._calculate_mom_from_index(index_data)

            # データをマージ
            result = self._merge_ippi_data(yoy_data, mom_data, index_data)

            print(f"[CaIppi] Loaded {len(result)} monthly records")
            if result:
                print(f"[CaIppi] Date range: {result[0]['date']} to {result[-1]['date']}")

            return result

        except Exception as e:
            print(f"[CaIppi] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_ippi_index(self) -> Dict[str, float]:
        """
        IPPI指数を取得
        Table 18-10-0265-01: Industrial Product Price Index (2020=100)
        """
        try:
            print(f"[CaIppi] Fetching Index data from: {STATCAN_IPPI_URL}")

            resp = requests.get(STATCAN_IPPI_URL, timeout=90)
            resp.raise_for_status()

            z = zipfile.ZipFile(io.BytesIO(resp.content))
            csv_name = [n for n in z.namelist() if n.endswith('.csv') and not n.startswith('_')][0]

            with z.open(csv_name) as f:
                df = pd.read_csv(f, low_memory=False)

            # Total IPPIのデータを抽出（カナダ全体）
            total_ippi = df[
                (df['North American Product Classification System (NAPCS)'] == 'Total, Industrial product price index (IPPI)') &
                (df['GEO'] == 'Canada')
            ].copy()

            result = {}
            for _, row in total_ippi.iterrows():
                date_str = row['REF_DATE']
                value = row['VALUE']

                if pd.isna(value):
                    continue

                try:
                    formatted_date = f"{date_str}-01"
                    result[formatted_date] = float(value)
                except (ValueError, TypeError):
                    continue

            print(f"[CaIppi] Loaded {len(result)} Index records")
            return result

        except Exception as e:
            print(f"[CaIppi] Error fetching Index: {e}")
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

        print(f"[CaIppi] Calculated {len(result)} YoY records from index")
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

        print(f"[CaIppi] Calculated {len(result)} MoM records from index")
        return result

    def _merge_ippi_data(
        self,
        yoy_data: Dict[str, float],
        mom_data: Dict[str, float],
        index_data: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """IPPIデータをマージ"""
        # すべての日付を収集
        all_dates = set(yoy_data.keys()) | set(mom_data.keys()) | set(index_data.keys())

        # 2010年以降のみ
        filtered_dates = [d for d in all_dates if d >= "2010-01-01"]
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

            # YoYがある場合のみ追加
            if "yoy" in item:
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
            return should_refresh_by_pattern(FMP_IPPI_PATTERN, last_updated_str, country="CA")
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
            print(f"[CaIppi] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaIppi] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Canada IPPI",
            "source": "Statistics Canada",
            "table": "18-10-0265-01",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(FMP_IPPI_PATTERN, country="CA"),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_ippi_service = CaIppiService()
