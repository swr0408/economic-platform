"""
スイス家計消費（Households and NPISH）サービス
SECOから四半期データを取得

指標:
- P31_S14_S15: Households and NPISH（家計および対家計民間非営利団体）
- QoQ（前期比）- 季節調整済み
- YoY（前年比）- 調整前

データソース:
- SECO (State Secretariat for Economic Affairs)
- https://www.seco.admin.ch/seco/en/home/wirtschaftslage---wirtschaftspolitik/Wirtschaftslage/bip-quartalsschaetzungen-.html

Excelファイル:
- qna_e_csa.xlsx: 季節調整済み（QoQ用）- 支出アプローチ
- qna_e_na.xlsx: 調整前（YoY用）- 支出アプローチ

発表スケジュール:
- 四半期ごと（GDPと同時発表、FMPから次回発表日時取得）

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
DATA_CACHE_FILE = CACHE_DIR / "ch_households_and_npish_cache.json"


class CHHouseholdsAndNpishService:
    """スイス家計消費サービス"""

    DATA_CACHE_KEY = "switzerland:ch_households_and_npish:data"
    ECONALPHA_ID = "ch_households_and_npish"
    FMP_COUNTRY = "CH"
    FMP_EVENT_PATTERN = "GDP Growth Rate QoQ"  # GDPと同時発表

    # データソースURL（支出アプローチ Expenditure approach）
    # CSA: 季節調整済み（QoQ用）
    QOQ_URL = "https://www.seco.admin.ch/dam/seco/de/dokumente/Wirtschaft/Wirtschaftslage/VIP%20Quartalssch%C3%A4tzungen/qna_e_csa.xlsx.download.xlsx/qna_e_csa.xlsx"
    # NA: 調整前（YoY用）
    YOY_URL = "https://www.seco.admin.ch/dam/seco/de/dokumente/Wirtschaft/Wirtschaftslage/VIP%20Quartalssch%C3%A4tzungen/qna_e_na.xlsx.download.xlsx/qna_e_na.xlsx"

    # 抽出対象列名
    TARGET_COLUMN = "P31_S14_S15"  # Households and NPISH

    def __init__(self):
        pass

    def get_ch_households_and_npish_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """スイス家計消費データを取得"""
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
                    "indicator": "Households and NPISH",
                    "description": "スイス家計消費（家計および対家計民間非営利団体）",
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
            print(f"[CHHouseholdsAndNpish] Fetching QoQ data from: {self.QOQ_URL}")
            print(f"[CHHouseholdsAndNpish] Fetching YoY data from: {self.YOY_URL}")

            # QoQデータ取得（CSA: 季節調整済み）
            qoq_data = self._fetch_excel_data(self.QOQ_URL, "qoq")
            print(f"[CHHouseholdsAndNpish] QoQ records: {len(qoq_data)}")

            # YoYデータ取得（NA: 調整前）
            yoy_data = self._fetch_excel_data(self.YOY_URL, "yoy")
            print(f"[CHHouseholdsAndNpish] YoY records: {len(yoy_data)}")

            # データをマージ
            result = []
            all_dates = set(qoq_data.keys()) | set(yoy_data.keys())

            for date_str in sorted(all_dates):
                qoq_val = qoq_data.get(date_str)
                yoy_val = yoy_data.get(date_str)

                result.append({
                    "date": date_str,
                    "qoq": round(qoq_val, 2) if qoq_val is not None else None,
                    "yoy": round(yoy_val, 2) if yoy_val is not None else None,
                })

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"[CHHouseholdsAndNpish] Loaded {len(result)} records")
            if result:
                print(f"[CHHouseholdsAndNpish] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CHHouseholdsAndNpish] Latest: QoQ={latest.get('qoq')}, YoY={latest.get('yoy')}")

            return result

        except Exception as e:
            print(f"[CHHouseholdsAndNpish] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_excel_data(self, url: str, data_type: str) -> Dict[str, float]:
        """SECO Excelファイルからデータを取得

        SECO Excel形式（支出アプローチ）:
        - シート: real_q（実質、四半期）
        - Row 10: ヘッダー行（カテゴリコード: B1GQ, P3_P5, P3, P31_S14_S15, ...）
        - Row 11以降: データ行
        - Column 0: 年
        - Column 1: 四半期（1, 2, 3, 4）
        - 偶数列(2,4,6,8...): 値
        - 奇数列(3,5,7,9...): 変化率（小数形式: 0.01 = 1%）
        - 最初のデータ行(Row 11)には変化率がない場合がある
        """
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()

            df = pd.read_excel(io.BytesIO(resp.content), sheet_name='real_q', header=None)

            # 対象列を探す（Row 10のヘッダー行でカテゴリコードを検索）
            target_col_idx = None
            header_row = 10
            for col_idx in range(df.shape[1]):
                cell_value = df.iloc[header_row, col_idx]
                if pd.notna(cell_value) and str(cell_value).strip() == self.TARGET_COLUMN:
                    target_col_idx = col_idx
                    break

            if target_col_idx is None:
                print(f"[CHHouseholdsAndNpish] Column {self.TARGET_COLUMN} not found in {data_type} file (searched row {header_row})")
                return {}

            # 変化率は対象列の隣（+1）
            rate_col_idx = target_col_idx + 1
            print(f"[CHHouseholdsAndNpish] Found {self.TARGET_COLUMN} at column {target_col_idx}, rate at column {rate_col_idx}")

            data = {}
            # データは11行目（インデックス11）から開始
            for i in range(11, len(df)):
                year = df.iloc[i, 0]
                quarter = df.iloc[i, 1]
                rate = df.iloc[i, rate_col_idx]

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
            print(f"[CHHouseholdsAndNpish] Error fetching {data_type} Excel: {e}")
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
            print(f"[CHHouseholdsAndNpish] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CHHouseholdsAndNpish] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Households and NPISH",
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
ch_households_and_npish_service = CHHouseholdsAndNpishService()
