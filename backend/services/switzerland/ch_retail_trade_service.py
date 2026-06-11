"""
スイス小売売上高（Retail Trade）サービス
BFS（スイス連邦統計局）から小売売上高データを取得

指標:
- 小売売上高 前月比（Retail Sales MoM）
- 小売売上高 前年比（Retail Sales YoY）

データソース:
- BFS DAM API:
  - 前月比: https://dam-api.bfs.admin.ch/hub/api/dam/assets/36354635/master
  - 前年比: https://dam-api.bfs.admin.ch/hub/api/dam/assets/36354641/master

発表スケジュール:
- 月次（Monthly）
- FMPから次回発表日時取得

キャッシュ方式: FMP発表日時ベース判定
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

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ch_retail_trade_cache.json"


class CHRetailTradeService:
    """スイス小売売上高サービス"""

    DATA_CACHE_KEY = "switzerland:ch_retail_trade:data"
    ECONALPHA_ID = "ch_retail_trade"
    FMP_COUNTRY = "CH"
    FMP_EVENT_PATTERN = "Retail Sales YoY"

    # BFS DAM API URLs
    MOM_ASSET_URL = "https://dam-api.bfs.admin.ch/hub/api/dam/assets/36354635/master"
    YOY_ASSET_URL = "https://dam-api.bfs.admin.ch/hub/api/dam/assets/36354641/master"

    def __init__(self):
        pass

    def get_ch_retail_trade_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """スイス小売売上高データを取得"""
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

        # BFS APIからデータ取得
        result = self._load_from_bfs()
        if result:
            latest = result[-1] if result else None

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "BFS (Swiss Federal Statistical Office)",
                    "indicator": "Retail Trade",
                    "description": "小売売上高（前月比・前年比）",
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

    def _load_from_bfs(self) -> List[Dict[str, Any]]:
        """BFS APIからデータを取得"""
        try:
            print("[CHRetailTrade] Fetching MoM data from BFS...")
            mom_data = self._fetch_excel_data(self.MOM_ASSET_URL, "mom")

            print("[CHRetailTrade] Fetching YoY data from BFS...")
            yoy_data = self._fetch_excel_data(self.YOY_ASSET_URL, "yoy")

            # データを結合
            result = self._merge_data(mom_data, yoy_data)

            print(f"[CHRetailTrade] Loaded {len(result)} records")
            if result:
                print(f"[CHRetailTrade] Date range: {result[0]['date']} to {result[-1]['date']}")
                print(f"[CHRetailTrade] Latest: mom={result[-1].get('mom')}, yoy={result[-1].get('yoy')}")

            return result

        except Exception as e:
            print(f"[CHRetailTrade] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_excel_data(self, url: str, data_type: str) -> Dict[str, float]:
        """Excelファイルからデータを取得

        BFS小売売上高Excelの形式:
        - シート: "Variation rates"（変化率）
        - 実質売上高（Real turnover）の変化率を使用
        - MoM: Row 30 (47: Total retail sector)
        - YoY: Row 30 (47: Total retail sector)

        Args:
            url: BFS DAM API URL
            data_type: 'mom' or 'yoy'

        Returns:
            {date: value} の辞書
        """
        try:
            from services.switzerland.bfs_asset_resolver import resolve_master_url_from_url
            resp = requests.get(resolve_master_url_from_url(url), timeout=60)
            resp.raise_for_status()

            # Variation ratesシートを読み込み
            df = pd.read_excel(io.BytesIO(resp.content), sheet_name='Variation rates', header=None)

            print(f"[CHRetailTrade] Excel shape: {df.shape}")

            data = {}

            # 固定行インデックス（実質売上高 Real turnover のTotal）
            # MoM: Row 30, YoY: Row 30
            DATA_ROW_INDEX = 30

            # 日付行を特定（Row 2付近にdatetimeが並ぶ）
            date_row_idx = 2

            # 検証: 日付行にdatetimeがあることを確認
            sample_cell = df.iloc[date_row_idx, 2] if len(df.columns) > 2 else None
            if not isinstance(sample_cell, (datetime, pd.Timestamp)):
                # 日付行を探す
                for i in range(min(10, len(df))):
                    datetime_count = 0
                    for j in range(2, min(20, len(df.columns))):
                        cell = df.iloc[i, j]
                        if isinstance(cell, (datetime, pd.Timestamp)):
                            datetime_count += 1
                    if datetime_count >= 5:
                        date_row_idx = i
                        break

            print(f"[CHRetailTrade] Using date row: {date_row_idx}, data row: {DATA_ROW_INDEX}")

            # データ行の内容を確認
            data_row_label = df.iloc[DATA_ROW_INDEX, 1] if pd.notna(df.iloc[DATA_ROW_INDEX, 1]) else ""
            print(f"[CHRetailTrade] Data row label: {data_row_label}")

            # 日付行とデータ行からデータを抽出
            for col in range(2, len(df.columns)):
                date_cell = df.iloc[date_row_idx, col]
                value_cell = df.iloc[DATA_ROW_INDEX, col]

                if pd.isna(date_cell) or pd.isna(value_cell):
                    continue

                try:
                    # 日付を解析
                    if isinstance(date_cell, (datetime, pd.Timestamp)):
                        date_str = date_cell.strftime('%Y-%m-01')
                    elif isinstance(date_cell, str):
                        # 文字列形式の場合
                        date_str = str(date_cell)[:7] + '-01'
                    else:
                        continue

                    # 値を解析
                    value = float(value_cell)
                    data[date_str] = value
                except (ValueError, TypeError) as e:
                    continue

            print(f"[CHRetailTrade] Extracted {len(data)} {data_type} records")
            if data:
                dates = sorted(data.keys())
                print(f"[CHRetailTrade] Date range: {dates[0]} to {dates[-1]}")

            return data

        except Exception as e:
            print(f"[CHRetailTrade] Error fetching {data_type} data: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _merge_data(self, mom_data: Dict[str, float], yoy_data: Dict[str, float]) -> List[Dict[str, Any]]:
        """前月比と前年比のデータを結合"""
        all_dates = set(mom_data.keys()) | set(yoy_data.keys())

        result = []
        for date in sorted(all_dates):
            record = {
                "date": date,
                "mom": mom_data.get(date),
                "yoy": yoy_data.get(date),
            }
            result.append(record)

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
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
            print(f"[CHRetailTrade] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CHRetailTrade] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "CH Retail Trade",
            "source": "BFS (Swiss Federal Statistical Office)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ch_retail_trade_service = CHRetailTradeService()
