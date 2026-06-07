"""
カナダ対米輸出依存度サービス

指標:
- 対米輸出依存度（Dependence on Exports to the United States）
- 米国向け輸出 / 総輸出 × 100

データソース:
- Statistics Canada Table 12-10-0011-01
- International merchandise trade for all countries and by Principal Trading Partners

発表スケジュール:
- 月次（対象月の約2ヶ月後）
- 発表時刻: 08:30 ET

注意:
- 季節調整済みデータを使用
- 単位: %（比率）
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
from services.canada.statcan_utils import fetch_statcan_csv


JST = ZoneInfo("Asia/Tokyo")
TORONTO = ZoneInfo("America/Toronto")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ca_us_export_dependence_cache.json"

# Statistics Canada CSV URL
# Table 12-10-0011-01: International merchandise trade
STATCAN_TRADE_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/12100011-eng.zip"

# FMPイベントパターン（貿易統計の発表タイミングで更新）
FMP_TRADE_PATTERN = "Imports"


class CaUsExportDependenceService:
    """カナダ対米輸出依存度サービス"""

    DATA_CACHE_KEY = "canada:ca_us_export_dependence:data"
    CACHE_TTL = 86400  # 24時間

    def __init__(self):
        pass

    def get_ca_us_export_dependence_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダ対米輸出依存度データを取得"""
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
            next_release = get_next_release_by_pattern(FMP_TRADE_PATTERN, country="CA")

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Statistics Canada",
                    "table": "12-10-0011-01",
                    "indicator": "Dependence on Exports to the United States",
                    "description": "カナダ対米輸出依存度（米国向け輸出/総輸出）",
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
        """Statistics Canadaから対米輸出依存度データを取得"""
        try:
            print(f"[CaUsExportDependence] Fetching data from: {STATCAN_TRADE_URL}")

            df = fetch_statcan_csv(STATCAN_TRADE_URL)

            print(f"[CaUsExportDependence] Columns: {df.columns.tolist()}")
            print(f"[CaUsExportDependence] Total rows: {len(df)}")

            # 季節調整済みデータをフィルタ
            sa_df = df[df['Seasonal adjustment'] == 'Seasonally adjusted'].copy()
            print(f"[CaUsExportDependence] Seasonally adjusted rows: {len(sa_df)}")

            # 輸出データのみを抽出（Trade = 'Export'）
            export_df = sa_df[sa_df['Trade'] == 'Export'].copy()
            print(f"[CaUsExportDependence] Export rows: {len(export_df)}")

            # 取引パートナー別にグループ化
            # - 'All countries' = 総輸出
            # - 'United States' = 米国向け輸出
            partners = export_df['Principal trading partners'].unique().tolist()
            print(f"[CaUsExportDependence] Partners (sample): {partners[:15]}")

            # データを日付ごとに整理
            export_data: Dict[str, Dict[str, float]] = {}

            for _, row in export_df.iterrows():
                date_str = str(row['REF_DATE'])
                partner = row['Principal trading partners']
                value = row['VALUE']

                if pd.isna(value):
                    continue

                formatted_date = self._month_to_date(date_str)
                if not formatted_date:
                    continue

                if formatted_date not in export_data:
                    export_data[formatted_date] = {}

                if partner == 'All countries':
                    export_data[formatted_date]['total'] = float(value)
                elif partner == 'United States':
                    export_data[formatted_date]['us'] = float(value)

            print(f"[CaUsExportDependence] Parsed {len(export_data)} months of data")

            # 依存度を計算
            result = self._calculate_dependence(export_data)

            print(f"[CaUsExportDependence] Loaded {len(result)} monthly records")
            if result:
                print(f"[CaUsExportDependence] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaUsExportDependence] Latest: {latest['date']} Value={latest.get('value')}%")

            return result

        except Exception as e:
            print(f"[CaUsExportDependence] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _month_to_date(self, month_str: str) -> Optional[str]:
        """月形式を日付に変換（例: "2024-01" -> "2024-01-01"）"""
        try:
            month_str = month_str.strip()
            if len(month_str) == 7 and '-' in month_str:
                return f"{month_str}-01"
            return None
        except Exception:
            return None

    def _calculate_dependence(self, export_data: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
        """対米輸出依存度を計算

        依存度 = 米国向け輸出 / 総輸出 × 100
        3MMA = 直近3ヶ月の米国向け輸出合計 / 直近3ヶ月の総輸出合計 × 100
        12MMA = 直近12ヶ月の米国向け輸出合計 / 直近12ヶ月の総輸出合計 × 100

        Args:
            export_data: 日付 -> {total, us} の辞書
        """
        sorted_dates = sorted(export_data.keys())
        result = []

        for i, date_str in enumerate(sorted_dates):
            data = export_data[date_str]
            total_export = data.get('total')
            us_export = data.get('us')

            if total_export is None or us_export is None or total_export <= 0:
                continue

            # 依存度（%）- 単月
            dependence = (us_export / total_export) * 100

            item = {
                "date": date_str,
                "value": round(dependence, 2),
                "us_export": round(us_export, 2),
                "total_export": round(total_export, 2),
            }

            # 3ヶ月移動平均（3MMA）を計算
            if i >= 2:
                us_sum_3m = 0.0
                total_sum_3m = 0.0
                valid_3m = True
                for j in range(3):
                    prev_date = sorted_dates[i - j]
                    prev_data = export_data.get(prev_date, {})
                    prev_us = prev_data.get('us')
                    prev_total = prev_data.get('total')
                    if prev_us is not None and prev_total is not None:
                        us_sum_3m += prev_us
                        total_sum_3m += prev_total
                    else:
                        valid_3m = False
                        break
                if valid_3m and total_sum_3m > 0:
                    ma_3m = (us_sum_3m / total_sum_3m) * 100
                    item["ma_3m"] = round(ma_3m, 2)

            # 12ヶ月移動平均（12MMA）を計算
            if i >= 11:
                us_sum_12m = 0.0
                total_sum_12m = 0.0
                valid_12m = True
                for j in range(12):
                    prev_date = sorted_dates[i - j]
                    prev_data = export_data.get(prev_date, {})
                    prev_us = prev_data.get('us')
                    prev_total = prev_data.get('total')
                    if prev_us is not None and prev_total is not None:
                        us_sum_12m += prev_us
                        total_sum_12m += prev_total
                    else:
                        valid_12m = False
                        break
                if valid_12m and total_sum_12m > 0:
                    ma_12m = (us_sum_12m / total_sum_12m) * 100
                    item["ma_12m"] = round(ma_12m, 2)

            result.append(item)

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            return should_refresh_by_pattern(FMP_TRADE_PATTERN, last_updated_str, country="CA")
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
            print(f"[CaUsExportDependence] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaUsExportDependence] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Canada US Export Dependence",
            "source": "Statistics Canada",
            "table": "12-10-0011-01",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(FMP_TRADE_PATTERN, country="CA"),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_us_export_dependence_service = CaUsExportDependenceService()
