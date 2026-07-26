"""
カナダ決済残高（Settlement Balances）サービス

指標:
1. Lynx Settlement Balances - Actual（ACTUAL）- 日次
2. Members of Payments Canada deposits（V36636）- 週次

データソース:
- Bank of Canada Valet API
- https://www.bankofcanada.ca/valet/observations/ACTUAL/json（日次）
- https://www.bankofcanada.ca/valet/observations/V36636/json（週次）

解説:
- 日次: Lynx決済システムの実際の決済残高
- 週次: Payments Canada メンバーの settlement account balances（BOCバランスシート連動）
- 短期資金デスク/ディーラーがCORRAのタイト/ルーズを判断する指標

発表スケジュール:
- 日次: 営業日ベース（具体的な更新時刻は非公開）
- 週次: 水曜日時点のデータ、金曜 14:30 ET 公表
"""
import json
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
TORONTO = ZoneInfo("America/Toronto")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ca_settlement_balances_cache.json"
DAILY_CACHE_FILE = CACHE_DIR / "ca_settlement_balances_daily_cache.json"


class CaSettlementBalancesService:
    """カナダ決済残高サービス"""

    DATA_CACHE_KEY = "canada:ca_settlement_balances:data"
    DAILY_CACHE_KEY = "canada:ca_settlement_balances:daily"

    # BOC Valet API URLs
    VALET_URL_WEEKLY = "https://www.bankofcanada.ca/valet/observations/V36636/json"
    VALET_URL_DAILY = "https://www.bankofcanada.ca/valet/observations/ACTUAL/json"

    def __init__(self):
        pass

    def get_ca_settlement_balances_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダ決済残高データを取得（日次と週次の両方を返す）"""
        daily_result = self._get_daily_data(force_refresh)
        weekly_result = self._get_weekly_data(force_refresh)

        # 日次データを優先してメインのdata/latestを設定
        if daily_result.get("data"):
            main_data = daily_result["data"]
            main_latest = daily_result.get("latest")
            main_metadata = daily_result.get("metadata", {})
        elif weekly_result.get("data"):
            main_data = weekly_result["data"]
            main_latest = weekly_result.get("latest")
            main_metadata = weekly_result.get("metadata", {})
        else:
            main_data = []
            main_latest = None
            main_metadata = {}

        return {
            "data": main_data,
            "latest": main_latest,
            "metadata": main_metadata,
            "daily": {
                "data": daily_result.get("data", []),
                "latest": daily_result.get("latest"),
                "metadata": daily_result.get("metadata", {}),
            },
            "weekly": {
                "data": weekly_result.get("data", []),
                "latest": weekly_result.get("latest"),
                "metadata": weekly_result.get("metadata", {}),
            },
            "cached": daily_result.get("cached", False) and weekly_result.get("cached", False),
            "source": daily_result.get("source", "none"),
            "last_updated": datetime.now(JST).isoformat(),
        }

    def _get_daily_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """日次データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DAILY_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh_daily(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "cached": True,
                        "source": "redis (daily)",
                        "last_updated": last_updated_str,
                    }

        # 日次データを取得
        result = self._load_daily_data()
        if result:
            latest = result[-1] if result else None

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Bank of Canada",
                    "indicator": "Lynx Settlement Balances (Actual)",
                    "description": "Lynx決済残高（日次）",
                    "unit": "millions CAD",
                    "series_id": "ACTUAL",
                    "frequency": "daily",
                },
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DAILY_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload, DAILY_CACHE_FILE)

            return {
                "data": result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "cached": False,
                "source": "api (daily)",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache(DAILY_CACHE_FILE)
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "cached": True,
                "source": "file (daily fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "cached": False,
            "source": "none",
            "last_updated": None,
        }

    def _get_weekly_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """週次データを取得（フォールバック用）"""
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh_weekly(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "cached": True,
                        "source": "redis (weekly)",
                        "last_updated": last_updated_str,
                    }

        result = self._load_weekly_data()
        if result:
            latest = result[-1] if result else None

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Bank of Canada",
                    "indicator": "Members of Payments Canada deposits",
                    "description": "カナダ決済残高（週次）",
                    "unit": "millions CAD",
                    "series_id": "V36636",
                    "frequency": "weekly",
                },
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload, DATA_CACHE_FILE)

            return {
                "data": result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "cached": False,
                "source": "api (weekly)",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache(DAILY_CACHE_FILE)
        if not file_cache:
            file_cache = self._load_file_cache(DATA_CACHE_FILE)
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_daily_data(self) -> List[Dict[str, Any]]:
        """日次データ（ACTUAL）を取得"""
        try:
            today = date.today()
            start_date = "2020-01-01"
            end_date = today.strftime("%Y-%m-%d")

            url = f"{self.VALET_URL_DAILY}?start_date={start_date}&end_date={end_date}"
            print(f"[CaSettlementBalances] Fetching daily data from: {url}")

            resp = requests.get(url, timeout=30)
            resp.raise_for_status()

            data = resp.json()
            observations = data.get("observations", [])

            result = []

            for obs in observations:
                date_str = obs.get("d")
                value_obj = obs.get("ACTUAL", {})
                value_str = value_obj.get("v")

                if not date_str or not value_str:
                    continue

                try:
                    value = float(value_str)
                    result.append({
                        "date": date_str,
                        "value": value,
                    })
                except (ValueError, TypeError):
                    continue

            result.sort(key=lambda x: x["date"])

            print(f"[CaSettlementBalances] Loaded {len(result)} daily records")
            if result:
                print(f"[CaSettlementBalances] Daily date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaSettlementBalances] Latest daily: {latest['date']} = {latest['value']:,.0f} M CAD")

            return result

        except Exception as e:
            print(f"[CaSettlementBalances] Error loading daily data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _load_weekly_data(self) -> List[Dict[str, Any]]:
        """週次データ（V36636）を取得"""
        try:
            today = date.today()
            start_date = "2015-01-01"
            end_date = today.strftime("%Y-%m-%d")

            url = f"{self.VALET_URL_WEEKLY}?start_date={start_date}&end_date={end_date}"
            print(f"[CaSettlementBalances] Fetching weekly data from: {url}")

            resp = requests.get(url, timeout=30)
            resp.raise_for_status()

            data = resp.json()
            observations = data.get("observations", [])

            result = []

            for obs in observations:
                date_str = obs.get("d")
                value_obj = obs.get("V36636", {})
                value_str = value_obj.get("v")

                if not date_str or not value_str:
                    continue

                try:
                    value = float(value_str)
                    result.append({
                        "date": date_str,
                        "value": value,
                    })
                except (ValueError, TypeError):
                    continue

            result.sort(key=lambda x: x["date"])

            print(f"[CaSettlementBalances] Loaded {len(result)} weekly records")
            if result:
                print(f"[CaSettlementBalances] Weekly date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaSettlementBalances] Latest weekly: {latest['date']} = {latest['value']:,.0f} M CAD")

            return result

        except Exception as e:
            print(f"[CaSettlementBalances] Error loading weekly data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh_daily(self, last_updated_str: str) -> bool:
        """日次データのキャッシュ更新判定

        JST 6:00 以降で、前回更新が当日6:00より前なら更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now_jst = datetime.now(JST)

            # 今日のJST 6:00
            today_release_time = now_jst.replace(hour=6, minute=0, second=0, microsecond=0)

            # 現在がJST 6:00以降で、最終更新がその前なら更新
            if now_jst >= today_release_time and last_updated < today_release_time:
                return True

            return False
        except Exception:
            return True

    def _should_refresh_weekly(self, last_updated_str: str) -> bool:
        """週次データのキャッシュ更新判定

        金曜 14:30 ET に公表
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now_toronto = datetime.now(TORONTO)

            # max-age フォールバック（発表レース凍結の自己回復）:
            # 金曜発表ちょうどの再取得でソース未反映のまま last_updated=now を刻むと、
            # 下の金曜判定が「消化済み」と誤認し翌金曜まで当該週を取り逃す。週次のため
            # 48hで必ず再取得させ自己回復させる。
            if (now_toronto - last_updated).total_seconds() > 48 * 3600:
                return True

            # 金曜日（weekday=4）の14:30 ET
            if now_toronto.weekday() == 4:
                release_time = now_toronto.replace(hour=14, minute=30, second=0, microsecond=0)
                last_updated_toronto = last_updated.astimezone(TORONTO)
                if now_toronto >= release_time and last_updated_toronto < release_time:
                    return True

            return False
        except Exception:
            return True

    def _load_file_cache(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not file_path.exists():
                return None
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CaSettlementBalances] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any], file_path: Path) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaSettlementBalances] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        redis_client.delete(self.DAILY_CACHE_KEY)
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        daily_exists = redis_client.exists(self.DAILY_CACHE_KEY)
        weekly_exists = redis_client.exists(self.DATA_CACHE_KEY)
        daily_data = redis_client.get(self.DAILY_CACHE_KEY) if daily_exists else None
        weekly_data = redis_client.get(self.DATA_CACHE_KEY) if weekly_exists else None

        return {
            "indicator": "Canada Settlement Balances",
            "source": "Bank of Canada",
            "daily": {
                "series_id": "ACTUAL",
                "cache_key": self.DAILY_CACHE_KEY,
                "exists": daily_exists,
                "last_updated": daily_data.get("last_updated") if daily_data else None,
                "data_count": len(daily_data.get("data", [])) if daily_data else 0,
                "latest": daily_data.get("latest") if daily_data else None,
                "file_cache_exists": DAILY_CACHE_FILE.exists(),
            },
            "weekly": {
                "series_id": "V36636",
                "cache_key": self.DATA_CACHE_KEY,
                "exists": weekly_exists,
                "last_updated": weekly_data.get("last_updated") if weekly_data else None,
                "data_count": len(weekly_data.get("data", [])) if weekly_data else 0,
                "latest": weekly_data.get("latest") if weekly_data else None,
                "file_cache_exists": DATA_CACHE_FILE.exists(),
            },
        }

    def warm_cache(self) -> None:
        """起動時にキャッシュをウォームアップ（バックグラウンド）"""
        import threading

        def _warm():
            try:
                print("[CaSettlementBalances] Warming cache in background...")
                self.get_ca_settlement_balances_data(force_refresh=False)
                print("[CaSettlementBalances] Cache warmed successfully")
            except Exception as e:
                print(f"[CaSettlementBalances] Cache warm failed: {e}")

        thread = threading.Thread(target=_warm, daemon=True)
        thread.start()


# シングルトンインスタンス
ca_settlement_balances_service = CaSettlementBalancesService()
