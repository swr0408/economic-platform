"""
スイスGDP成長率サービス
SECOから四半期GDP成長率データを取得

指標:
- GDP Growth Rate QoQ（前期比）- 季節調整済み
- GDP Growth Rate YoY（前年比）- 調整前
- GDP Growth Rate Annualized（年率換算）

データソース:
- SECO (State Secretariat for Economic Affairs)
- https://www.seco.admin.ch/seco/en/home/wirtschaftslage---wirtschaftspolitik/Wirtschaftslage/bip-quartalsschaetzungen-.html

Excelファイル:
- qna_p_cssa.xlsx: 季節調整 + スポーツ調整済み（QoQ・年率用）
- qna_p_na.xlsx: 調整前（YoY用）

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
DATA_CACHE_FILE = CACHE_DIR / "ch_growth_rate_cache.json"


class CHGrowthRateService:
    """スイスGDP成長率サービス"""

    DATA_CACHE_KEY = "switzerland:ch_growth_rate:data"
    ECONALPHA_ID = "ch_growth_rate"
    FMP_COUNTRY = "CH"
    FMP_EVENT_PATTERN = "GDP Growth Rate QoQ"

    # データソースURL
    # CSSA: 季節調整 + スポーツイベント調整済み（QoQ・年率用）
    QOQ_URL = "https://www.seco.admin.ch/dam/seco/de/dokumente/Wirtschaft/Wirtschaftslage/VIP%20Quartalssch%C3%A4tzungen/qna_p_cssa.xlsx.download.xlsx/qna_p_cssa.xlsx"
    # NA: 調整前（YoY用）
    YOY_URL = "https://www.seco.admin.ch/dam/seco/de/dokumente/Wirtschaft/Wirtschaftslage/VIP%20Quartalssch%C3%A4tzungen/qna_p_na.xlsx.download.xlsx/qna_p_na.xlsx"

    def __init__(self):
        pass

    def get_ch_growth_rate_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """スイスGDP成長率データを取得"""
        # 次回発表日を取得
        next_release = get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY)

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
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # データソースから取得
        result = self._load_from_source()
        if result:
            # 最新値を取得
            latest = result[-1] if result else None

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "SECO",
                    "indicator": "GDP Growth Rate",
                    "description": "スイスGDP成長率",
                    "unit": "%",
                },
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
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
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_source(self) -> List[Dict[str, Any]]:
        """SECOからデータを取得"""
        try:
            print(f"[CHGrowthRate] Fetching QoQ data from: {self.QOQ_URL}")
            print(f"[CHGrowthRate] Fetching YoY data from: {self.YOY_URL}")

            # QoQデータ取得（CSSA: 季節調整 + スポーツ調整済み）
            qoq_data = self._fetch_excel_data(self.QOQ_URL, "qoq")
            print(f"[CHGrowthRate] QoQ records: {len(qoq_data)}")

            # YoYデータ取得（NA: 調整前）
            yoy_data = self._fetch_excel_data(self.YOY_URL, "yoy")
            print(f"[CHGrowthRate] YoY records: {len(yoy_data)}")

            # データをマージ
            result = []
            all_dates = set(qoq_data.keys()) | set(yoy_data.keys())

            for date_str in sorted(all_dates):
                qoq_val = qoq_data.get(date_str)
                yoy_val = yoy_data.get(date_str)

                # 年率換算（QoQから計算: (1 + qoq)^4 - 1）
                annualized = None
                if qoq_val is not None:
                    annualized = round(((1 + qoq_val / 100) ** 4 - 1) * 100, 2)

                result.append({
                    "date": date_str,
                    "qoq": round(qoq_val, 2) if qoq_val is not None else None,
                    "yoy": round(yoy_val, 2) if yoy_val is not None else None,
                    "annualized": annualized,
                })

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"[CHGrowthRate] Loaded {len(result)} records")
            if result:
                print(f"[CHGrowthRate] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CHGrowthRate] Latest: QoQ={latest.get('qoq')}, YoY={latest.get('yoy')}, Annualized={latest.get('annualized')}")

            return result

        except Exception as e:
            print(f"[CHGrowthRate] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_excel_data(self, url: str, data_type: str) -> Dict[str, float]:
        """SECO Excelファイルからデータを取得

        SECO Excel形式:
        - シート: real_q（実質GDP、四半期）
        - Column 0: 年
        - Column 1: 四半期（1, 2, 3, 4）
        - Column 2: GDP値
        - Column 3: 変化率（小数形式: 0.01 = 1%）
        - データ行は11行目から開始
        """
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()

            df = pd.read_excel(io.BytesIO(resp.content), sheet_name='real_q', header=None)

            data = {}
            # データは11行目（インデックス11）から開始
            for i in range(11, len(df)):
                year = df.iloc[i, 0]
                quarter = df.iloc[i, 1]
                rate = df.iloc[i, 3]  # 変化率は列3

                if pd.isna(year) or pd.isna(quarter) or pd.isna(rate):
                    continue

                try:
                    year_int = int(year)
                    quarter_int = int(quarter)

                    # 四半期を月に変換（Q1=01, Q2=04, Q3=07, Q4=10）
                    month = (quarter_int - 1) * 3 + 1
                    date_str = f"{year_int}-{month:02d}-01"

                    # 小数形式からパーセントに変換
                    rate_pct = float(rate) * 100
                    data[date_str] = rate_pct
                except (ValueError, TypeError):
                    continue

            return data
        except Exception as e:
            print(f"[CHGrowthRate] Error fetching {data_type} Excel: {e}")
            return {}

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
            print(f"[CHGrowthRate] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CHGrowthRate] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "GDP Growth Rate",
            "source": "SECO",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ch_growth_rate_service = CHGrowthRateService()
