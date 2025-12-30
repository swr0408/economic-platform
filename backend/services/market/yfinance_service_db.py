"""
yfinance を使用した市場データ取得サービス（DB版）

機能:
- 日足OHLC データの取得（直近15年）
- PostgreSQL + TimescaleDB への保存
- Redis キャッシュ（高速読み取り用）
- 日次更新（市場クローズ後）
- 計算値（ドル建て日経、各通貨建てゴールド等）のサポート
"""
import json
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo

import yfinance as yf
import pandas as pd

try:
    from core.redis_client import redis_client
    from services.market.market_repository import market_repository
except ImportError:
    from backend.core.redis_client import redis_client
    from backend.services.market.market_repository import market_repository


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

# データ期間（15年）
DATA_YEARS = 15


class YFinanceServiceDB:
    """yfinance を使用した市場データ取得サービス（DB版）"""

    CACHE_KEY_PREFIX = "market:daily:"
    CACHE_TTL = 3600  # 1時間（DBがあるので短め）

    def __init__(self):
        self.repo = market_repository

    def get_daily_data(
        self,
        symbol_id: str,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        銘柄の日足データを取得

        優先順位:
        1. Redisキャッシュ
        2. PostgreSQL
        3. yfinance API（新規取得 or 更新）
        """
        symbol_info = self.repo.get_symbol(symbol_id)
        if not symbol_info:
            return self._error_response(f"Unknown symbol: {symbol_id}")

        # 計算値の場合
        if symbol_info.get("is_calculated"):
            return self._get_calculated_data(symbol_id, symbol_info, force_refresh)

        # Redisキャッシュチェック
        if not force_refresh:
            cached = self._get_from_redis(symbol_id)
            if cached:
                return cached

        # DBから取得
        db_data = self.repo.get_daily_data(symbol_id)

        # DBにデータがあり、更新不要な場合
        if db_data and not force_refresh and not self._should_refresh(symbol_id):
            result = self._build_response(db_data, symbol_info, True, "database")
            self._save_to_redis(symbol_id, result)
            return result

        # yfinanceから取得（初回 or 更新）
        new_data = self._fetch_and_save(symbol_id, symbol_info)

        if new_data:
            result = self._build_response(new_data, symbol_info, False, "api")
            self._save_to_redis(symbol_id, result)
            return result

        # 取得失敗時はDBデータを返す
        if db_data:
            return self._build_response(db_data, symbol_info, True, "database (fallback)")

        return self._error_response("No data available")

    def _fetch_and_save(
        self,
        symbol_id: str,
        symbol_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """yfinanceからデータを取得してDBに保存"""
        ticker = symbol_info["ticker"]
        if not ticker:
            return []

        try:
            print(f"[YFinanceDB] Fetching {symbol_id} ({ticker}) from yfinance...")

            end_date = datetime.now()
            start_date = end_date - timedelta(days=DATA_YEARS * 365)

            stock = yf.Ticker(ticker)
            df = stock.history(
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                interval="1d"
            )

            if df.empty:
                print(f"[YFinanceDB] No data returned for {ticker}")
                return []

            # DataFrameをリストに変換
            data = []
            for idx, row in df.iterrows():
                date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, 'strftime') else str(idx)[:10]
                data.append({
                    "date": date_str,
                    "open": round(float(row["Open"]), 6) if pd.notna(row["Open"]) else None,
                    "high": round(float(row["High"]), 6) if pd.notna(row["High"]) else None,
                    "low": round(float(row["Low"]), 6) if pd.notna(row["Low"]) else None,
                    "close": round(float(row["Close"]), 6) if pd.notna(row["Close"]) else None,
                    "volume": int(row["Volume"]) if pd.notna(row.get("Volume", 0)) else 0,
                })

            # DBに保存
            count = self.repo.upsert_daily_data(symbol_id, data)
            print(f"[YFinanceDB] Saved {count} records for {symbol_id}")

            # 15年より古いデータを削除
            cutoff_date = (datetime.now() - timedelta(days=DATA_YEARS * 365)).date()
            deleted = self.repo.delete_old_daily_data(symbol_id, cutoff_date)
            if deleted > 0:
                print(f"[YFinanceDB] Deleted {deleted} old records for {symbol_id}")

            return data

        except Exception as e:
            print(f"[YFinanceDB] Error fetching {ticker}: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_calculated_data(
        self,
        symbol_id: str,
        symbol_info: Dict[str, Any],
        force_refresh: bool
    ) -> Dict[str, Any]:
        """計算値のデータを取得"""
        base_id = symbol_info.get("base_symbol_id")
        fx_id = symbol_info.get("fx_symbol_id")
        operation = symbol_info.get("operation")

        if not base_id or not fx_id or not operation:
            return self._error_response(f"Invalid calculation config for {symbol_id}")

        # ベースデータと為替データを取得
        base_data = self.get_daily_data(base_id, force_refresh)
        fx_data = self.get_daily_data(fx_id, force_refresh)

        if not base_data.get("data") or not fx_data.get("data"):
            return self._error_response("Failed to fetch base or FX data")

        # 日付でマージして計算
        base_dict = {d["date"]: d for d in base_data["data"]}
        fx_dict = {d["date"]: d for d in fx_data["data"]}

        result = []
        for date_str, base in base_dict.items():
            if date_str not in fx_dict:
                continue

            fx = fx_dict[date_str]
            if base["close"] is None or fx["close"] is None:
                continue

            if operation == "multiply":
                calc_close = base["close"] * fx["close"]
                calc_open = base["open"] * fx["open"] if base["open"] and fx["open"] else None
                calc_high = base["high"] * fx["high"] if base["high"] and fx["high"] else None
                calc_low = base["low"] * fx["low"] if base["low"] and fx["low"] else None
            elif operation == "divide":
                if fx["close"] == 0:
                    continue
                calc_close = base["close"] / fx["close"]
                calc_open = base["open"] / fx["open"] if base["open"] and fx["open"] and fx["open"] != 0 else None
                calc_high = base["high"] / fx["low"] if base["high"] and fx["low"] and fx["low"] != 0 else None
                calc_low = base["low"] / fx["high"] if base["low"] and fx["high"] and fx["high"] != 0 else None
            else:
                continue

            result.append({
                "date": date_str,
                "open": round(calc_open, 6) if calc_open else None,
                "high": round(calc_high, 6) if calc_high else None,
                "low": round(calc_low, 6) if calc_low else None,
                "close": round(calc_close, 6),
                "volume": 0,
            })

        result.sort(key=lambda x: x["date"])

        return self._build_response(
            result,
            symbol_info,
            base_data.get("cached", False) and fx_data.get("cached", False),
            "calculated"
        )

    def _should_refresh(self, symbol_id: str) -> bool:
        """
        更新が必要かどうかを判定

        判定ロジック:
        - 最新データの日付が昨日以前で、現在がJST 6:00以降なら更新
        """
        try:
            latest_date = self.repo.get_latest_daily_date(symbol_id)
            if not latest_date:
                return True

            now = datetime.now(JST)
            today = now.date()

            # 週末は更新不要
            if now.weekday() in [5, 6]:  # 土日
                # 金曜日のデータがあれば更新不要
                friday = today - timedelta(days=now.weekday() - 4)
                if now.weekday() == 5:
                    friday = today - timedelta(days=1)
                elif now.weekday() == 6:
                    friday = today - timedelta(days=2)

                if latest_date >= friday:
                    return False

            # 平日の場合
            if latest_date >= today - timedelta(days=1):
                return False

            # JST 6:00以降なら更新
            if now.hour >= 6:
                return True

            return False

        except Exception as e:
            print(f"[YFinanceDB] Error checking refresh status: {e}")
            return False

    def _get_from_redis(self, symbol_id: str) -> Optional[Dict[str, Any]]:
        """Redisからキャッシュを取得"""
        cache_key = f"{self.CACHE_KEY_PREFIX}{symbol_id}"
        cached = redis_client.get(cache_key)
        if cached:
            cached["source"] = "redis"
            return cached
        return None

    def _save_to_redis(self, symbol_id: str, data: Dict[str, Any]) -> None:
        """Redisにキャッシュを保存"""
        cache_key = f"{self.CACHE_KEY_PREFIX}{symbol_id}"
        redis_client.set(cache_key, data, expire=self.CACHE_TTL)

    def _build_response(
        self,
        data: List[Dict[str, Any]],
        symbol_info: Dict[str, Any],
        cached: bool,
        source: str
    ) -> Dict[str, Any]:
        """レスポンスを構築"""
        latest = None
        if data:
            sorted_data = sorted(data, key=lambda x: x["date"], reverse=True)
            latest = {
                "date": sorted_data[0]["date"],
                "close": sorted_data[0]["close"],
            }

        return {
            "data": data,
            "latest": latest,
            "symbol": symbol_info,
            "cached": cached,
            "source": source,
            "last_updated": datetime.now(JST).isoformat(),
        }

    def _error_response(self, message: str) -> Dict[str, Any]:
        """エラーレスポンスを構築"""
        return {
            "data": [],
            "latest": None,
            "symbol": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": message,
        }

    # =========================================================================
    # バッチ操作
    # =========================================================================

    def update_all_symbols(self, force_refresh: bool = False) -> Dict[str, Any]:
        """全銘柄を更新"""
        started_at = datetime.utcnow()
        symbols = self.repo.get_non_calculated_symbols()

        success_count = 0
        failed_count = 0
        errors = []

        for symbol in symbols:
            try:
                result = self.get_daily_data(symbol["id"], force_refresh)
                if result.get("error"):
                    failed_count += 1
                    errors.append(f"{symbol['id']}: {result['error']}")
                else:
                    success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f"{symbol['id']}: {str(e)}")

        completed_at = datetime.utcnow()

        # ログを記録
        status = "success" if failed_count == 0 else ("partial" if success_count > 0 else "failed")
        self.repo.log_update(
            data_type="daily",
            status=status,
            records_updated=success_count,
            error_message="\n".join(errors) if errors else None,
            started_at=started_at,
            completed_at=completed_at,
        )

        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "total": len(symbols),
            "errors": errors,
            "duration_seconds": (completed_at - started_at).total_seconds(),
        }

    def get_multiple_daily_data(
        self,
        symbol_ids: List[str],
        force_refresh: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """複数銘柄のデータを取得"""
        return {
            symbol_id: self.get_daily_data(symbol_id, force_refresh)
            for symbol_id in symbol_ids
        }

    def invalidate_cache(self, symbol_id: str) -> bool:
        """キャッシュを無効化"""
        cache_key = f"{self.CACHE_KEY_PREFIX}{symbol_id}"
        return redis_client.delete(cache_key)

    def invalidate_all_cache(self) -> int:
        """全銘柄のキャッシュを無効化"""
        symbols = self.repo.get_all_symbols()
        count = 0
        for symbol in symbols:
            if self.invalidate_cache(symbol["id"]):
                count += 1
        return count

    def get_cache_status(self, symbol_id: str) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        cache_key = f"{self.CACHE_KEY_PREFIX}{symbol_id}"
        redis_exists = redis_client.exists(cache_key)
        latest_date = self.repo.get_latest_daily_date(symbol_id)
        data_count = self.repo.get_daily_data_count(symbol_id)

        return {
            "symbol_id": symbol_id,
            "cache_key": cache_key,
            "redis_exists": redis_exists,
            "db_latest_date": latest_date.isoformat() if latest_date else None,
            "db_data_count": data_count,
        }


# シングルトンインスタンス
yfinance_service_db = YFinanceServiceDB()
