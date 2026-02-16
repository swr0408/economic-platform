"""
ASX RBA Rate Tracker サービス

ASX 30日物銀行間キャッシュレート先物から、次回RBA会合での利上げ/利下げ確率と
インプライドイールドカーブを取得する。

データソース:
- ASX RBA Rate Tracker
- https://www.asx.com.au/markets/trade-our-derivatives-market/futures-market/rba-rate-tracker

3つのASXエンドポイント（JSON形式、.csv拡張子）:
1. dynamic_text.csv - 現在の状況サマリ
2. market_exp.csv - 確率の日次推移
3. yield_curve.csv - インプライドイールドカーブ

更新頻度: 営業日毎（先物決済価格ベース）
"""
import json
from datetime import datetime
from typing import Dict, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
SYDNEY = ZoneInfo("Australia/Sydney")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "australia" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "asx_rate_tracker_cache.json"

# ASX Data Endpoints
ASX_DYNAMIC_TEXT_URL = "https://www.asx.com.au/content/dam/asx/data/dynamic_text.csv"
ASX_MARKET_EXP_URL = "https://www.asx.com.au/content/dam/asx/data/market_exp.csv"
ASX_YIELD_CURVE_URL = "https://www.asx.com.au/content/dam/asx/data/yield_curve.csv"


class AsxRateTrackerService:
    """ASX RBA Rate Tracker サービス"""

    DATA_CACHE_KEY = "australia:asx_rate_tracker:data"
    CACHE_TTL_SECONDS = 3600  # 1時間

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
    }

    def __init__(self):
        pass

    def get_rate_tracker_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ASX Rate Trackerデータを取得"""

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        **cached_data.get("data", {}),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # ASXからデータ取得
        result = self._fetch_all_data()
        if result:
            cache_payload = {
                "data": result,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=self.CACHE_TTL_SECONDS)
            self._save_file_cache(cache_payload)

            return {
                **result,
                "cached": False,
                "source": "asx",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                **file_cache.get("data", {}),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "summary": None,
            "probability_history": [],
            "yield_curve": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_all_data(self) -> Optional[Dict[str, Any]]:
        """3つのASXエンドポイントからデータを取得・統合"""
        try:
            summary = self._fetch_dynamic_text()
            probability = self._fetch_market_expectations()
            yield_curve = self._fetch_yield_curve()

            if not summary and not probability and not yield_curve:
                print("[AsxRateTracker] All ASX endpoints failed")
                return None

            result = {}

            # サマリ情報
            if summary:
                result["summary"] = {
                    "current_rate": summary.get("RBA_Trgt_Cash_Rate"),
                    "last_rate_change": summary.get("RBA_Trgt_Cash_Rate_Change"),
                    "last_meeting_date": summary.get("RBA_Mtng_Dt"),
                    "next_meeting_date": summary.get("Nxt_RBA_Mtng_Dt"),
                    "settlement_date": summary.get("Crnt_Stlmnt_Dt"),
                    "settlement_price": summary.get("Crnt_Dy_Stlmnt_Price"),
                    "market_expectation_pct": summary.get("Mkt_Exptn_Rate"),
                    "future_cash_rate": summary.get("Ftre_Cash_Rate"),
                    "future_rate_change": summary.get("Ftre_Cash_Rate_Change"),
                    "expiry_month": summary.get("Expiry_Month"),
                    "expiry_year": summary.get("Expiry_Year"),
                }
            else:
                result["summary"] = None

            # 確率推移
            if probability:
                days = probability.get("days", [])
                # 日付の古い順にソート
                days_sorted = sorted(days, key=lambda x: x.get("Stlmnt_Dt", ""))
                result["probability_history"] = [
                    {
                        "date": day.get("Stlmnt_Dt"),
                        "prob_no_change": day.get("Prob_No_Change"),
                        "prob_change": day.get("Prob_Change"),
                    }
                    for day in days_sorted
                ]
                result["probability_meta"] = {
                    "future_cash_rate": probability.get("Ftre_Cash_Rate"),
                    "future_rate_change": probability.get("Ftre_Cash_Rate_Change"),
                }
            else:
                result["probability_history"] = []
                result["probability_meta"] = None

            # イールドカーブ
            if yield_curve:
                months = yield_curve.get("months", [])
                result["yield_curve"] = {
                    "settlement_date": yield_curve.get("Crnt_Stlmnt_Dt"),
                    "target_rate": yield_curve.get("RBA_Trgt_Cash_Rate"),
                    "data": [
                        {
                            "month": m.get("Expiry_Month"),
                            "implied_yield": m.get("Implied_Yield"),
                        }
                        for m in months
                    ],
                }
            else:
                result["yield_curve"] = None

            return result

        except Exception as e:
            print(f"[AsxRateTracker] Error fetching data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_json(self, url: str, label: str) -> Optional[Dict[str, Any]]:
        """ASXエンドポイントからJSONデータを取得"""
        try:
            print(f"[AsxRateTracker] Fetching {label} from: {url}")
            resp = requests.get(url, headers=self.HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            print(f"[AsxRateTracker] {label}: OK")
            return data
        except Exception as e:
            print(f"[AsxRateTracker] Error fetching {label}: {e}")
            return None

    def _fetch_dynamic_text(self) -> Optional[Dict[str, Any]]:
        """dynamic_text.csv からサマリ情報を取得"""
        return self._fetch_json(ASX_DYNAMIC_TEXT_URL, "dynamic_text")

    def _fetch_market_expectations(self) -> Optional[Dict[str, Any]]:
        """market_exp.csv から確率推移データを取得"""
        return self._fetch_json(ASX_MARKET_EXP_URL, "market_exp")

    def _fetch_yield_curve(self) -> Optional[Dict[str, Any]]:
        """yield_curve.csv からイールドカーブデータを取得"""
        return self._fetch_json(ASX_YIELD_CURVE_URL, "yield_curve")

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(SYDNEY)

            # 週末はキャッシュ利用
            if now.weekday() >= 5:
                return False

            # 1時間以上経過していれば更新
            elapsed = (now - last_updated.astimezone(SYDNEY)).total_seconds()
            if elapsed > self.CACHE_TTL_SECONDS:
                return True

            return False
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
            print(f"[AsxRateTracker] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[AsxRateTracker] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "ASX RBA Rate Tracker",
            "source": "ASX",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
asx_rate_tracker_service = AsxRateTrackerService()
