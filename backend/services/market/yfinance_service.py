"""
yfinance を使用した市場データ取得サービス

機能:
- 日足OHLC データの取得（直近15年）
- Redis + ファイルキャッシュ
- 日次更新（市場クローズ後）
- 計算値（ドル建て日経、各通貨建てゴールド等）のサポート
"""
import json
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional
from pathlib import Path
from zoneinfo import ZoneInfo

import yfinance as yf
import pandas as pd

from core.redis_client import redis_client
from services.market.symbols import (
    get_symbol_by_id,
    get_ticker_by_id,
    get_all_symbols,
    is_calculated_symbol,
    get_calculation_info,
    MARKET_SYMBOLS,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

# キャッシュ設定
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# データ期間（15年）
DATA_YEARS = 15


class YFinanceService:
    """yfinance を使用した市場データ取得サービス"""

    CACHE_KEY_PREFIX = "market:daily:"
    CACHE_TTL = 86400  # 24時間

    def __init__(self):
        pass

    def get_daily_data(
        self,
        symbol_id: str,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        銘柄の日足データを取得

        Args:
            symbol_id: 銘柄ID（例: "usdjpy", "sp500"）
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "open": float, "high": float, "low": float, "close": float}, ...],
                "latest": {"date": "YYYY-MM-DD", "close": float},
                "symbol": {...},
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        symbol_info = get_symbol_by_id(symbol_id)
        if not symbol_info:
            return {
                "data": [],
                "latest": None,
                "symbol": None,
                "cached": False,
                "source": "none",
                "last_updated": None,
                "error": f"Unknown symbol: {symbol_id}"
            }

        # 計算が必要な銘柄の場合
        if is_calculated_symbol(symbol_id):
            return self._get_calculated_data(symbol_id, force_refresh)

        cache_key = f"{self.CACHE_KEY_PREFIX}{symbol_id}"

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": self._get_latest(cached_data.get("data", [])),
                        "symbol": symbol_info,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache(symbol_id)
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    data = file_cache.get("data", [])

                    # Redisにも保存
                    redis_client.set(cache_key, {
                        "data": data,
                        "last_updated": last_updated_str
                    }, expire=0)

                    return {
                        "data": data,
                        "latest": self._get_latest(data),
                        "symbol": symbol_info,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # yfinance からデータ取得
        ticker = symbol_info["ticker"]
        api_data = self._fetch_from_yfinance(ticker)

        if api_data:
            cache_payload = {
                "data": api_data,
                "last_updated": datetime.now(JST).isoformat()
            }

            # キャッシュ保存
            redis_client.set(cache_key, cache_payload, expire=0)
            self._save_file_cache(symbol_id, cache_payload)

            return {
                "data": api_data,
                "latest": self._get_latest(api_data),
                "symbol": symbol_info,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache(symbol_id)
        if file_cache:
            data = file_cache.get("data", [])
            return {
                "data": data,
                "latest": self._get_latest(data),
                "symbol": symbol_info,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "symbol": symbol_info,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_yfinance(self, ticker: str) -> List[Dict[str, Any]]:
        """yfinance からデータを取得"""
        try:
            print(f"Fetching {ticker} from yfinance...")

            # 15年前からの日足データ
            end_date = datetime.now()
            start_date = end_date - timedelta(days=DATA_YEARS * 365)

            stock = yf.Ticker(ticker)
            df = stock.history(
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                interval="1d"
            )

            if df.empty:
                print(f"No data returned for {ticker}")
                return []

            result = []
            for idx, row in df.iterrows():
                # インデックスが Timestamp の場合
                date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, 'strftime') else str(idx)[:10]

                result.append({
                    "date": date_str,
                    "open": round(float(row["Open"]), 4) if pd.notna(row["Open"]) else None,
                    "high": round(float(row["High"]), 4) if pd.notna(row["High"]) else None,
                    "low": round(float(row["Low"]), 4) if pd.notna(row["Low"]) else None,
                    "close": round(float(row["Close"]), 4) if pd.notna(row["Close"]) else None,
                    "volume": int(row["Volume"]) if pd.notna(row.get("Volume", 0)) else 0,
                })

            print(f"Fetched {len(result)} records for {ticker}")
            return result

        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_calculated_data(
        self,
        symbol_id: str,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """計算が必要な銘柄のデータを取得"""
        calc_info = get_calculation_info(symbol_id)
        if not calc_info:
            return {
                "data": [],
                "latest": None,
                "symbol": None,
                "cached": False,
                "source": "none",
                "error": f"No calculation info for {symbol_id}"
            }

        symbol_info = get_symbol_by_id(symbol_id)

        # ベースデータと為替データを取得
        base_data = self.get_daily_data(calc_info["base"], force_refresh)
        fx_data = self.get_daily_data(calc_info["fx"], force_refresh)

        if not base_data.get("data") or not fx_data.get("data"):
            return {
                "data": [],
                "latest": None,
                "symbol": symbol_info,
                "cached": False,
                "source": "none",
                "error": "Failed to fetch base or FX data"
            }

        # 日付でマージして計算
        base_dict = {d["date"]: d for d in base_data["data"]}
        fx_dict = {d["date"]: d for d in fx_data["data"]}

        operation = calc_info["operation"]
        result = []

        for date_str, base in base_dict.items():
            if date_str not in fx_dict:
                continue

            fx = fx_dict[date_str]

            if base["close"] is None or fx["close"] is None:
                continue

            if operation == "multiply":
                calculated_close = base["close"] * fx["close"]
                calculated_open = base["open"] * fx["open"] if base["open"] and fx["open"] else None
                calculated_high = base["high"] * fx["high"] if base["high"] and fx["high"] else None
                calculated_low = base["low"] * fx["low"] if base["low"] and fx["low"] else None
            elif operation == "divide":
                if fx["close"] == 0:
                    continue
                calculated_close = base["close"] / fx["close"]
                calculated_open = base["open"] / fx["open"] if base["open"] and fx["open"] and fx["open"] != 0 else None
                calculated_high = base["high"] / fx["low"] if base["high"] and fx["low"] and fx["low"] != 0 else None  # high/low for range
                calculated_low = base["low"] / fx["high"] if base["low"] and fx["high"] and fx["high"] != 0 else None
            else:
                continue

            result.append({
                "date": date_str,
                "open": round(calculated_open, 4) if calculated_open else None,
                "high": round(calculated_high, 4) if calculated_high else None,
                "low": round(calculated_low, 4) if calculated_low else None,
                "close": round(calculated_close, 4),
                "volume": 0,
            })

        # 日付順にソート
        result.sort(key=lambda x: x["date"])

        return {
            "data": result,
            "latest": self._get_latest(result),
            "symbol": symbol_info,
            "cached": base_data.get("cached", False) and fx_data.get("cached", False),
            "source": "calculated",
            "last_updated": datetime.now(JST).isoformat()
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        判定ロジック:
        - 米国市場クローズ後（ET 16:00 = JST 5:00/6:00）に1日1回更新
        - 前日のデータが取得済みなら更新不要
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 今日の更新基準時刻（JST 6:00）
            today_refresh_time = now.replace(hour=6, minute=0, second=0, microsecond=0)

            # 今日の更新時刻より前に更新されていたら、再取得が必要
            if now >= today_refresh_time and last_updated < today_refresh_time:
                return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return False

    def _get_latest(self, data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """最新データを取得"""
        if not data:
            return None
        # 日付降順でソートして最新を取得
        sorted_data = sorted(data, key=lambda x: x["date"], reverse=True)
        latest = sorted_data[0]
        return {
            "date": latest["date"],
            "close": latest["close"],
            "open": latest.get("open"),
            "high": latest.get("high"),
            "low": latest.get("low"),
        }

    def _load_file_cache(self, symbol_id: str) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            cache_file = CACHE_DIR / f"{symbol_id}_cache.json"
            if not cache_file.exists():
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache for {symbol_id}: {e}")
            return None

    def _save_file_cache(self, symbol_id: str, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            cache_file = CACHE_DIR / f"{symbol_id}_cache.json"
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            print(f"Cache saved to {cache_file}")
        except Exception as e:
            print(f"Failed to save file cache for {symbol_id}: {e}")

    def get_multiple_daily_data(
        self,
        symbol_ids: List[str],
        force_refresh: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """複数銘柄のデータを一括取得"""
        result = {}
        for symbol_id in symbol_ids:
            result[symbol_id] = self.get_daily_data(symbol_id, force_refresh)
        return result

    def get_all_symbols_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """全銘柄のデータを取得"""
        symbol_ids = [s["id"] for s in MARKET_SYMBOLS]
        return self.get_multiple_daily_data(symbol_ids, force_refresh)

    def invalidate_cache(self, symbol_id: str) -> bool:
        """指定銘柄のキャッシュを無効化"""
        cache_key = f"{self.CACHE_KEY_PREFIX}{symbol_id}"
        return redis_client.delete(cache_key)

    def invalidate_all_cache(self) -> int:
        """全銘柄のキャッシュを無効化"""
        count = 0
        for symbol in MARKET_SYMBOLS:
            if self.invalidate_cache(symbol["id"]):
                count += 1
        return count

    def get_cache_status(self, symbol_id: str) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_key = f"{self.CACHE_KEY_PREFIX}{symbol_id}"
        cache_exists = redis_client.exists(cache_key)
        cached_data = redis_client.get(cache_key) if cache_exists else None
        cache_file = CACHE_DIR / f"{symbol_id}_cache.json"

        return {
            "symbol_id": symbol_id,
            "cache_key": cache_key,
            "redis_exists": cache_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "file_cache_exists": cache_file.exists()
        }


# シングルトンインスタンス
yfinance_service = YFinanceService()
