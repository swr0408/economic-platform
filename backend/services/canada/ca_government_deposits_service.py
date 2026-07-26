"""
カナダ政府預金（Government of Canada Canadian dollar deposits）サービス

指標:
1. Total: GOCCADDEPTOT - 政府預金合計
2. BoC: GOCCADDEPBOC - BOC保有分
3. Auction Participants: GOCCADDEPAP - オークション参加者保有分

データソース:
- Bank of Canada Valet API
- https://www.bankofcanada.ca/valet/observations/GOCCADDEPTOT/json

解説:
- 政府預金（TGA相当）。BoC保有分＋オークション参加者保有分の合計
- 政府預金の増減＝民間資金の吸収/放出として、短期資金環境（タイト/ルーズ）の説明変数
- B2の Government of Canada deposits（V36628）と同等

発表スケジュール:
- 週次: 金曜 14:30 ET 公表
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
DATA_CACHE_FILE = CACHE_DIR / "ca_government_deposits_cache.json"


class CaGovernmentDepositsService:
    """カナダ政府預金サービス"""

    DATA_CACHE_KEY = "canada:ca_government_deposits:data"

    # BOC Valet API URLs
    VALET_URL_TOTAL = "https://www.bankofcanada.ca/valet/observations/GOCCADDEPTOT/json"
    VALET_URL_BOC = "https://www.bankofcanada.ca/valet/observations/GOCCADDEPBOC/json"
    VALET_URL_AP = "https://www.bankofcanada.ca/valet/observations/GOCCADDEPAP/json"

    def __init__(self):
        pass

    def get_ca_government_deposits_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダ政府預金データを取得"""
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
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # データを取得
        result = self._load_data()
        if result:
            latest = result[-1] if result else None

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Bank of Canada",
                    "indicator": "Government of Canada Canadian dollar deposits",
                    "description": "カナダ政府預金（TGA相当）",
                    "unit": "millions CAD",
                    "series_id": "GOCCADDEPTOT",
                    "frequency": "weekly",
                },
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
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

    def _load_data(self) -> List[Dict[str, Any]]:
        """BOC Valet APIからデータを取得"""
        try:
            today = date.today()
            start_date = "2015-01-01"
            end_date = today.strftime("%Y-%m-%d")

            # 3系列を取得
            total_data = self._fetch_series("GOCCADDEPTOT", start_date, end_date)
            boc_data = self._fetch_series("GOCCADDEPBOC", start_date, end_date)
            ap_data = self._fetch_series("GOCCADDEPAP", start_date, end_date)

            # 日付をキーにしてマージ
            merged = {}
            for item in total_data:
                merged[item["date"]] = {
                    "date": item["date"],
                    "total": item["value"],
                    "boc": None,
                    "ap": None,
                }

            for item in boc_data:
                if item["date"] in merged:
                    merged[item["date"]]["boc"] = item["value"]
                else:
                    merged[item["date"]] = {
                        "date": item["date"],
                        "total": None,
                        "boc": item["value"],
                        "ap": None,
                    }

            for item in ap_data:
                if item["date"] in merged:
                    merged[item["date"]]["ap"] = item["value"]
                else:
                    merged[item["date"]] = {
                        "date": item["date"],
                        "total": None,
                        "boc": None,
                        "ap": item["value"],
                    }

            # リストに変換してソート
            result = list(merged.values())
            result.sort(key=lambda x: x["date"])

            # valueフィールドを追加（totalを使用）
            for item in result:
                item["value"] = item["total"]

            # totalがNoneのレコードを除外
            result = [item for item in result if item.get("total") is not None]

            print(f"[CaGovernmentDeposits] Loaded {len(result)} records")
            if result:
                print(f"[CaGovernmentDeposits] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaGovernmentDeposits] Latest: {latest['date']} = Total: {latest['total']:,.0f} M CAD")

            return result

        except Exception as e:
            print(f"[CaGovernmentDeposits] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_series(self, series_id: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """単一系列のデータを取得"""
        try:
            url = f"https://www.bankofcanada.ca/valet/observations/{series_id}/json?start_date={start_date}&end_date={end_date}"
            print(f"[CaGovernmentDeposits] Fetching {series_id} from: {url}")

            resp = requests.get(url, timeout=30)
            resp.raise_for_status()

            data = resp.json()
            observations = data.get("observations", [])

            result = []
            for obs in observations:
                date_str = obs.get("d")
                value_obj = obs.get(series_id, {})
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

            print(f"[CaGovernmentDeposits] {series_id}: {len(result)} records")
            return result

        except Exception as e:
            print(f"[CaGovernmentDeposits] Error fetching {series_id}: {e}")
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュ更新判定

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

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CaGovernmentDeposits] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaGovernmentDeposits] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if exists else None

        return {
            "indicator": "Canada Government Deposits",
            "source": "Bank of Canada",
            "series_id": "GOCCADDEPTOT",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }

    def warm_cache(self) -> None:
        """起動時にキャッシュをウォームアップ（バックグラウンド）"""
        import threading

        def _warm():
            try:
                print("[CaGovernmentDeposits] Warming cache in background...")
                self.get_ca_government_deposits_data(force_refresh=False)
                print("[CaGovernmentDeposits] Cache warmed successfully")
            except Exception as e:
                print(f"[CaGovernmentDeposits] Cache warm failed: {e}")

        thread = threading.Thread(target=_warm, daemon=True)
        thread.start()


# シングルトンインスタンス
ca_government_deposits_service = CaGovernmentDepositsService()
