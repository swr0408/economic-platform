"""
カナダGDP成長率サービス

指標:
- GDP成長率（前期比: QoQ simple）
- GDP成長率（前期比年率: QoQ annualized）
- GDP成長率（前年比: YoY）

データソース:
- Statistics Canada Table 36-10-0104-01
- GDP支出ベース、四半期データ

発表スケジュール:
- 四半期ごと（対象期間終了の約2ヶ月後）
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
from services.canada.statcan_utils import fetch_statcan_csv


JST = ZoneInfo("Asia/Tokyo")
TORONTO = ZoneInfo("America/Toronto")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ca_gdp_growth_cache.json"

# Statistics Canada CSV URL
# Table 36-10-0104-01: GDP支出ベース、四半期（季節調整済み、年率）
STATCAN_GDP_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/36100104-eng.zip"

# FMPイベントパターン
FMP_GDP_PATTERN = "Gross Domestic Product"
CA_GDP_ECONALPHA_ID = "ca_gdp_growth"


class CaGdpGrowthService:
    """カナダGDP成長率サービス"""

    DATA_CACHE_KEY = "canada:ca_gdp_growth:data"
    CACHE_TTL = 86400  # 24時間

    def __init__(self):
        pass

    def get_ca_gdp_growth_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダGDP成長率データを取得"""
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
            next_release = get_next_release_by_pattern(FMP_GDP_PATTERN, country="CA")

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Statistics Canada",
                    "table": "36-10-0104-01",
                    "indicator": "GDP Growth Rate",
                    "description": "カナダGDP成長率（四半期）",
                    "unit": "%",
                    "frequency": "quarterly",
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
        """Statistics CanadaからGDPデータを取得"""
        try:
            print(f"[CaGdpGrowth] Fetching data from: {STATCAN_GDP_URL}")

            df = fetch_statcan_csv(STATCAN_GDP_URL)

            print(f"[CaGdpGrowth] Columns: {df.columns.tolist()}")

            # 1. GDP絶対値（Chained 2017 dollars）を取得してYoYを計算
            gdp_level = df[
                (df['Estimates'].str.contains('Gross domestic product at market prices', na=False)) &
                (df['Prices'] == 'Chained (2017) dollars')
            ].copy()

            print(f"[CaGdpGrowth] Found {len(gdp_level)} GDP level records")

            # 2. QoQ percentage changeを取得
            gdp_qoq = df[
                (df['Estimates'].str.contains('Gross domestic product at market prices', na=False)) &
                (df['Prices'] == 'Chained (2017) dollars percentage change')
            ].copy()

            print(f"[CaGdpGrowth] Found {len(gdp_qoq)} QoQ records")

            # GDP絶対値を辞書に格納
            gdp_values = {}
            for _, row in gdp_level.iterrows():
                date_str = row['REF_DATE']  # 形式: "2024-01" (YYYY-MM)
                value = row['VALUE']

                if pd.isna(value):
                    continue

                try:
                    # 月形式を日付に変換 (例: "2024-01" -> "2024-01-01")
                    formatted_date = self._month_to_date(date_str)
                    if formatted_date:
                        gdp_values[formatted_date] = float(value)
                except (ValueError, TypeError):
                    continue

            # QoQを辞書に格納
            qoq_values = {}
            for _, row in gdp_qoq.iterrows():
                date_str = row['REF_DATE']
                value = row['VALUE']

                if pd.isna(value):
                    continue

                try:
                    formatted_date = self._month_to_date(date_str)
                    if formatted_date:
                        qoq_values[formatted_date] = float(value)
                except (ValueError, TypeError):
                    continue

            print(f"[CaGdpGrowth] Parsed {len(gdp_values)} GDP level values, {len(qoq_values)} QoQ values")

            # YoYを計算してデータをマージ
            result = self._calculate_growth_rates(gdp_values, qoq_values)

            print(f"[CaGdpGrowth] Loaded {len(result)} quarterly records")
            if result:
                print(f"[CaGdpGrowth] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaGdpGrowth] Latest: {latest['date']} QoQ={latest.get('qoq')}% YoY={latest.get('yoy')}%")

            return result

        except Exception as e:
            print(f"[CaGdpGrowth] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _month_to_date(self, month_str: str) -> Optional[str]:
        """月形式を日付に変換（例: "2024-01" -> "2024-01-01"）"""
        try:
            month_str = month_str.strip()
            # 形式: "2024-01" -> "2024-01-01"
            if len(month_str) == 7 and '-' in month_str:
                return f"{month_str}-01"
            return None
        except Exception:
            return None

    def _calculate_growth_rates(
        self, gdp_values: Dict[str, float], qoq_values: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """QoQ（前期比年率）とYoY（前年比）を計算

        Args:
            gdp_values: 日付 -> GDP絶対値（Chained 2017 dollars）
            qoq_values: 日付 -> QoQ前期比変化率（Statistics Canadaが提供）
        """
        # 日付でソート
        sorted_dates = sorted(gdp_values.keys())
        result = []

        for date_str in sorted_dates:
            current_value = gdp_values[date_str]
            item = {
                "date": date_str,
                "value": round(current_value, 2),
            }

            # QoQ（前期比・前期比年率）- Statistics Canadaの値を使用
            if date_str in qoq_values:
                qoq_simple_pct = qoq_values[date_str]  # 前期比（%）
                item["qoq_simple"] = round(qoq_simple_pct, 2)
                # 年率換算（4乗）
                qoq_simple = qoq_simple_pct / 100  # パーセント→小数
                qoq_annualized = ((1 + qoq_simple) ** 4 - 1) * 100
                item["qoq"] = round(qoq_annualized, 2)

            # YoY（前年比）を計算
            # 4期前の日付を探す
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            prev_year_date = f"{dt.year - 1}-{dt.month:02d}-01"
            if prev_year_date in gdp_values:
                prev_year_value = gdp_values[prev_year_date]
                if prev_year_value > 0:
                    yoy = ((current_value - prev_year_value) / prev_year_value) * 100
                    item["yoy"] = round(yoy, 2)

            # QoQまたはYoYがある場合のみ追加
            if "qoq" in item or "yoy" in item:
                result.append(item)

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            return should_refresh_by_pattern(FMP_GDP_PATTERN, last_updated_str, country="CA")
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
            print(f"[CaGdpGrowth] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaGdpGrowth] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Canada GDP Growth",
            "source": "Statistics Canada",
            "table": "36-10-0104-01",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(FMP_GDP_PATTERN, country="CA"),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_gdp_growth_service = CaGdpGrowthService()
