"""
カナダ貿易収支サービス

指標:
- 貿易収支（Trade Balance）
- 輸出（Exports）
- 輸入（Imports）
- 前月比・前年比

データソース:
- Statistics Canada Table 12-10-0011-01
- Canadian international merchandise trade

発表スケジュール:
- 月次（対象月の約2ヶ月後）
- 発表時刻: 08:30 ET

注意:
- 季節調整済みデータを使用
- Trade Balance = Exports - Imports（単位: Millions of CAD）
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
DATA_CACHE_FILE = CACHE_DIR / "ca_trade_balance_cache.json"

# Statistics Canada CSV URL
# Table 12-10-0011-01: Canadian international merchandise trade
STATCAN_TRADE_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/12100011-eng.zip"

# FMPイベントパターン
FMP_TRADE_PATTERN = "Imports"


class CaTradeBalanceService:
    """カナダ貿易収支サービス"""

    DATA_CACHE_KEY = "canada:ca_trade_balance:data"
    CACHE_TTL = 86400  # 24時間

    def __init__(self):
        pass

    def get_ca_trade_balance_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダ貿易収支データを取得"""
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
                    "table": "12-10-0011-01",
                    "indicator": "Canadian international merchandise trade",
                    "description": "カナダ貿易収支（季節調整済み）",
                    "unit": "Millions CAD",
                    "frequency": "monthly",
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
        """Statistics Canadaから貿易収支データを取得"""
        try:
            print(f"[CaTradeBalance] Fetching data from: {STATCAN_TRADE_URL}")

            df = fetch_statcan_csv(STATCAN_TRADE_URL)

            print(f"[CaTradeBalance] Columns: {df.columns.tolist()}")
            print(f"[CaTradeBalance] Total rows: {len(df)}")

            # Trade, exports and imports の区分
            # - Trade balance (All countries)
            # - Total exports (All countries)
            # - Total imports (All countries)
            # 季節調整済みデータを使用

            # 主要なカラム名を確認
            print(f"[CaTradeBalance] Unique 'Trade' values (sample): {df['Trade'].unique()[:10].tolist()}")
            print(f"[CaTradeBalance] Unique 'Seasonal adjustment' values: {df['Seasonal adjustment'].unique().tolist()}")
            print(f"[CaTradeBalance] Unique 'Principal trading partners' values (sample): {df['Principal trading partners'].unique()[:10].tolist()}")

            # 季節調整済み、全世界（All countries）のデータをフィルタ
            filtered_df = df[
                (df['Seasonal adjustment'] == 'Seasonally adjusted') &
                (df['Principal trading partners'] == 'All countries')
            ].copy()

            print(f"[CaTradeBalance] Filtered rows: {len(filtered_df)}")
            print(f"[CaTradeBalance] Unique 'Trade' values in filtered: {filtered_df['Trade'].unique().tolist()}")

            # 日付毎にデータを整理
            trade_data = {}

            for _, row in filtered_df.iterrows():
                date_str = row['REF_DATE']  # 形式: "2024-01" (YYYY-MM)
                trade_type = row['Trade']
                value = row['VALUE']

                if pd.isna(value):
                    continue

                try:
                    formatted_date = self._month_to_date(date_str)
                    if not formatted_date:
                        continue

                    if formatted_date not in trade_data:
                        trade_data[formatted_date] = {}

                    # Trade Balance, Export, Import を取得
                    # Trade列の値: 'Trade Balance', 'Export', 'Import'
                    if trade_type == 'Trade Balance':
                        trade_data[formatted_date]['balance'] = float(value)
                    elif trade_type == 'Export':
                        trade_data[formatted_date]['exports'] = float(value)
                    elif trade_type == 'Import':
                        trade_data[formatted_date]['imports'] = float(value)

                except (ValueError, TypeError):
                    continue

            print(f"[CaTradeBalance] Parsed {len(trade_data)} months of data")

            # MoMとYoYを計算
            result = self._calculate_growth_rates(trade_data)

            print(f"[CaTradeBalance] Loaded {len(result)} monthly records")
            if result:
                print(f"[CaTradeBalance] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaTradeBalance] Latest: {latest['date']} Balance={latest.get('balance')} MoM={latest.get('mom')}% YoY={latest.get('yoy')}%")

            return result

        except Exception as e:
            print(f"[CaTradeBalance] Error loading data: {e}")
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

    def _calculate_growth_rates(self, trade_data: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
        """MoM（前月比）とYoY（前年比）を計算

        Args:
            trade_data: 日付 -> {balance, exports, imports} の辞書
        """
        # 日付でソート
        sorted_dates = sorted(trade_data.keys())
        result = []

        for i, date_str in enumerate(sorted_dates):
            data = trade_data[date_str]
            balance = data.get('balance')
            exports = data.get('exports')
            imports = data.get('imports')

            if balance is None:
                continue

            item = {
                "date": date_str,
                "balance": round(balance, 2),
            }

            # 輸出・輸入があれば追加
            if exports is not None:
                item["exports"] = round(exports, 2)
            if imports is not None:
                item["imports"] = round(imports, 2)

            # MoM（前月比）を計算 - 貿易収支の増減額
            if i > 0:
                prev_date = sorted_dates[i - 1]
                prev_balance = trade_data[prev_date].get('balance')
                if prev_balance is not None:
                    # 貿易収支は絶対値なのでパーセント変化を計算
                    # 符号が変わる場合があるため、変化額も追加
                    change = balance - prev_balance
                    item["mom_change"] = round(change, 2)
                    # 前月がゼロでない場合のみパーセント変化を計算
                    if abs(prev_balance) > 0.01:
                        mom_pct = (change / abs(prev_balance)) * 100
                        item["mom"] = round(mom_pct, 2)

            # YoY（前年比）を計算
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            prev_year_date = f"{dt.year - 1}-{dt.month:02d}-01"
            if prev_year_date in trade_data:
                prev_year_balance = trade_data[prev_year_date].get('balance')
                if prev_year_balance is not None:
                    change = balance - prev_year_balance
                    item["yoy_change"] = round(change, 2)
                    if abs(prev_year_balance) > 0.01:
                        yoy_pct = (change / abs(prev_year_balance)) * 100
                        item["yoy"] = round(yoy_pct, 2)

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
            print(f"[CaTradeBalance] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaTradeBalance] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Canada Trade Balance",
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
ca_trade_balance_service = CaTradeBalanceService()
