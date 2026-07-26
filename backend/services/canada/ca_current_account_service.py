"""
カナダ経常収支サービス

指標:
- 経常収支（Current Account Balance）
- 前期比変化額（QoQ Change）

データソース:
- Statistics Canada Table 36-10-0018-01
- Balance of international payments, current account

発表スケジュール:
- 四半期ごと（対象期間終了の約2ヶ月後）
- 発表時刻: 08:30 ET

注意:
- 季節調整済みデータを使用
- 単位: Millions of CAD
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
DATA_CACHE_FILE = CACHE_DIR / "ca_current_account_cache.json"

# Statistics Canada CSV URL
# Table 36-10-0018-01: Balance of international payments, current account
STATCAN_CURRENT_ACCOUNT_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/36100018-eng.zip"

# FMPイベントパターン
FMP_CURRENT_ACCOUNT_PATTERN = "Current Account"


class CaCurrentAccountService:
    """カナダ経常収支サービス"""

    DATA_CACHE_KEY = "canada:ca_current_account:data"
    CACHE_TTL = 86400  # 24時間

    def __init__(self):
        pass

    def get_ca_current_account_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダ経常収支データを取得"""
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
            from services.usa.fmp_next_release_utils import guarded_last_updated
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )
            next_release = get_next_release_by_pattern(FMP_CURRENT_ACCOUNT_PATTERN, country="CA")

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Statistics Canada",
                    "table": "36-10-0018-01",
                    "indicator": "Current Account Balance",
                    "description": "カナダ経常収支（季節調整済み）",
                    "unit": "Millions CAD",
                    "frequency": "quarterly",
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
        """Statistics Canadaから経常収支データを取得"""
        try:
            print(f"[CaCurrentAccount] Fetching data from: {STATCAN_CURRENT_ACCOUNT_URL}")

            df = fetch_statcan_csv(STATCAN_CURRENT_ACCOUNT_URL)

            print(f"[CaCurrentAccount] Columns: {df.columns.tolist()}")
            print(f"[CaCurrentAccount] Total rows: {len(df)}")

            # Table 36-10-0018-01のカラム構造:
            # - 'Receipts, payments and balances': 'Balances, seasonally adjusted'
            # - 'Current account': 'Total current account'
            print(f"[CaCurrentAccount] Unique 'Receipts, payments and balances': {df['Receipts, payments and balances'].unique().tolist()}")
            print(f"[CaCurrentAccount] Unique 'Current account' (sample): {df['Current account'].unique()[:10].tolist()}")

            # 経常収支（Total current account）のバランス（季節調整済み）を取得
            filtered_df = df[
                (df['Receipts, payments and balances'] == 'Balances, seasonally adjusted') &
                (df['Current account'] == 'Total current account')
            ].copy()

            print(f"[CaCurrentAccount] Filtered rows: {len(filtered_df)}")
            if len(filtered_df) > 0:
                print(f"[CaCurrentAccount] Sample data: {filtered_df[['REF_DATE', 'VALUE']].tail(5).to_dict('records')}")

            # 日付毎にデータを整理
            current_account_data = {}

            for _, row in filtered_df.iterrows():
                date_str = str(row['REF_DATE'])  # 形式: "2024-01" (YYYY-MM) for quarterly
                value = row['VALUE']

                if pd.isna(value):
                    continue

                try:
                    formatted_date = self._quarter_to_date(date_str)
                    if not formatted_date:
                        continue

                    # 既にデータがある場合は上書きしない（最初の値を使う）
                    if formatted_date not in current_account_data:
                        current_account_data[formatted_date] = float(value)

                except (ValueError, TypeError):
                    continue

            print(f"[CaCurrentAccount] Parsed {len(current_account_data)} quarters of data")

            # QoQ変化額を計算
            result = self._calculate_qoq_change(current_account_data)

            print(f"[CaCurrentAccount] Loaded {len(result)} quarterly records")
            if result:
                print(f"[CaCurrentAccount] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaCurrentAccount] Latest: {latest['date']} Value={latest.get('value')} QoQ Change={latest.get('qoq_change')}")

            return result

        except Exception as e:
            print(f"[CaCurrentAccount] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _quarter_to_date(self, date_str: str) -> Optional[str]:
        """四半期形式を日付に変換（例: "2024-01" -> "2024-01-01"）"""
        try:
            date_str = date_str.strip()
            # 形式: "2024-01" -> "2024-01-01"
            if len(date_str) == 7 and '-' in date_str:
                return f"{date_str}-01"
            return None
        except Exception:
            return None

    def _calculate_qoq_change(self, data: Dict[str, float]) -> List[Dict[str, Any]]:
        """QoQ（前期比変化額）を計算

        Args:
            data: 日付 -> 経常収支の辞書
        """
        # 日付でソート
        sorted_dates = sorted(data.keys())
        result = []

        for i, date_str in enumerate(sorted_dates):
            value = data[date_str]

            item = {
                "date": date_str,
                "value": round(value, 2),
            }

            # QoQ変化額を計算（前期との差額）
            if i > 0:
                prev_date = sorted_dates[i - 1]
                prev_value = data[prev_date]
                change = value - prev_value
                item["qoq_change"] = round(change, 2)

            result.append(item)

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            return should_refresh_by_pattern(FMP_CURRENT_ACCOUNT_PATTERN, last_updated_str, country="CA")
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
            print(f"[CaCurrentAccount] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaCurrentAccount] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Canada Current Account",
            "source": "Statistics Canada",
            "table": "36-10-0018-01",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(FMP_CURRENT_ACCOUNT_PATTERN, country="CA"),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_current_account_service = CaCurrentAccountService()
