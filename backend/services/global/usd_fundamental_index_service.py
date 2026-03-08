"""
USD Fundamental Index サービス
ISM非製造業指数 - 独製造業PMI のスプレッドを算出
DXY・EUR/USDの月次終値データも同時提供

データソース:
- ISM Non-Manufacturing PMI: DB (economic_calendar_events)
- Germany Manufacturing PMI: DB (economic_calendar_events)
- DXY / EUR/USD: yfinance 日次終値

キャッシュ方式: 24時間固定TTL
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "global" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "usd_fundamental_index_cache.json"


class UsdFundamentalIndexService:
    """USD Fundamental Index サービス"""

    CACHE_KEY = "global:usd_fundamental_index:data"
    CACHE_TTL = 24 * 60 * 60  # 24時間

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        USD Fundamental Indexデータを取得

        Returns:
            {
                "data": [{"date": "YYYY-MM", "ism_non_mfg": float, "germany_mfg": float, "spread": float}, ...],
                "dxy_data": [{"date": "YYYY-MM-DD", "close": float}, ...],
                "eurusd_data": [{"date": "YYYY-MM-DD", "close": float}, ...],
                "latest": {...},
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached = redis_client.get(self.CACHE_KEY)
            if cached and cached.get("last_updated"):
                try:
                    last_dt = datetime.fromisoformat(cached["last_updated"])
                    if (datetime.now(JST) - last_dt).total_seconds() < self.CACHE_TTL:
                        return {
                            "data": cached.get("data", []),
                            "dxy_data": cached.get("dxy_data", []),
                            "eurusd_data": cached.get("eurusd_data", []),
                            "latest": cached.get("latest"),
                            "cached": True,
                            "source": "redis",
                            "last_updated": cached["last_updated"],
                        }
                except Exception:
                    pass

        # ISM Non-Mfg と Germany Mfg PMI を取得
        ism_data = self._get_ism_non_mfg()
        germany_mfg_data = self._get_germany_mfg_pmi()

        # スプレッド算出
        spread_data = self._calc_spread(ism_data, germany_mfg_data)

        # DXY・EURUSD 日次終値
        dxy_data = self._get_market_daily("dxy")
        eurusd_data = self._get_market_daily("eurusd")

        latest = spread_data[-1] if spread_data else None

        payload = {
            "data": spread_data,
            "dxy_data": dxy_data,
            "eurusd_data": eurusd_data,
            "latest": latest,
            "last_updated": datetime.now(JST).isoformat(),
        }

        # キャッシュ保存
        redis_client.set(self.CACHE_KEY, payload, expire=self.CACHE_TTL)
        self._save_file_cache(payload)

        return {
            **payload,
            "cached": False,
            "source": "database + yfinance",
        }

    def _get_ism_non_mfg(self) -> List[Dict[str, Any]]:
        """ISM非製造業PMIデータを取得"""
        try:
            from services.usa.ism_non_manufacturing_service import ism_non_manufacturing_service
            result = ism_non_manufacturing_service.get_ism_non_manufacturing_data()
            raw = result.get("data", [])
            # date: "YYYY-MM-01" → "YYYY-MM"
            return [
                {"date": item["date"][:7], "value": item["value"]}
                for item in raw
                if item.get("value") is not None
            ]
        except Exception as e:
            print(f"[UsdFundIndex] Failed to get ISM Non-Mfg: {e}")
            return []

    def _get_germany_mfg_pmi(self) -> List[Dict[str, Any]]:
        """独製造業PMIデータを取得"""
        try:
            from services.eurozone.germany_pmi_service import germany_pmi_service
            result = germany_pmi_service.get_germany_pmi_data()
            mfg = result.get("manufacturing")
            if not mfg:
                return []
            raw = mfg.get("data", [])
            return [
                {"date": item["date"][:7], "value": item["value"]}
                for item in raw
                if item.get("value") is not None
            ]
        except Exception as e:
            print(f"[UsdFundIndex] Failed to get Germany Mfg PMI: {e}")
            return []

    def _calc_spread(
        self,
        ism_data: List[Dict],
        germany_data: List[Dict],
    ) -> List[Dict[str, Any]]:
        """ISM Non-Mfg - Germany Mfg のスプレッドを算出"""
        ism_map = {item["date"]: item["value"] for item in ism_data}
        germany_map = {item["date"]: item["value"] for item in germany_data}

        all_dates = sorted(set(ism_map.keys()) | set(germany_map.keys()))
        result = []
        for d in all_dates:
            ism_val = ism_map.get(d)
            de_val = germany_map.get(d)
            spread = None
            if ism_val is not None and de_val is not None:
                spread = round(ism_val - de_val, 1)
            result.append({
                "date": d,
                "ism_non_mfg": ism_val,
                "germany_mfg": de_val,
                "spread": spread,
            })
        return result

    def _get_market_daily(self, symbol_id: str) -> List[Dict[str, Any]]:
        """yfinanceから日次終値データを取得"""
        try:
            from services.market.yfinance_service import yfinance_service
            result = yfinance_service.get_daily_data(symbol_id)
            if not result or not result.get("data"):
                return []
            return [
                {"date": item["date"], "close": item["close"]}
                for item in result["data"]
                if item.get("close") is not None
            ]
        except Exception as e:
            print(f"[UsdFundIndex] Failed to get market data for {symbol_id}: {e}")
            return []

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[UsdFundIndex] Failed to save file cache: {e}")

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not CACHE_FILE.exists():
                return None
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        exists = redis_client.exists(self.CACHE_KEY)
        cached = redis_client.get(self.CACHE_KEY) if exists else None
        return {
            "indicator": "USD Fundamental Index (ISM Non-Mfg - Germany Mfg PMI)",
            "cache_key": self.CACHE_KEY,
            "exists": exists,
            "last_updated": cached.get("last_updated") if cached else None,
            "data_count": len(cached.get("data", [])) if cached else 0,
            "latest": cached.get("latest") if cached else None,
            "file_cache_exists": CACHE_FILE.exists(),
        }


# シングルトンインスタンス
usd_fundamental_index_service = UsdFundamentalIndexService()
