"""
日本 価格DIスプレッド（日銀短観）サービス

販売価格判断DI - 仕入価格判断DI で計算
企業のマージン（採算）とインフレ転嫁状況を表す

データソース:
- 日銀短観（BOJ Tankan Survey）
- 販売価格判断DI: A12シート
- 仕入価格判断DI: A13シート

発表スケジュール:
- 四半期（4月、7月、10月、12月）
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "price"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "japan_price_di_spread_cache.json"


class JapanPriceDISpreadService:
    """日本 価格DIスプレッドサービス"""

    DATA_CACHE_KEY = "japan:price_di_spread:data"
    CACHE_TTL = 60 * 60 * 24 * 7  # 7日

    # FMP indicator ID（マッピングテーブル参照用）
    INDICATOR_ID = "boj_tankan"

    def __init__(self):
        self._fmp_utils = None
        self._tankan_service = None

    @property
    def fmp_utils(self):
        """遅延インポートでFMPユーティリティを取得"""
        if self._fmp_utils is None:
            from services.japan.fmp_next_release_utils import (
                get_next_release_from_fmp,
                should_refresh_by_fmp_schedule
            )
            self._fmp_utils = {
                "get_next_release": get_next_release_from_fmp,
                "should_refresh": should_refresh_by_fmp_schedule
            }
        return self._fmp_utils

    @property
    def tankan_service(self):
        """遅延インポートで日銀短観包括サービスを取得"""
        if self._tankan_service is None:
            from services.japan.boj_tankan_comprehensive_service import boj_tankan_comprehensive_service
            self._tankan_service = boj_tankan_comprehensive_service
        return self._tankan_service

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """FMPから次回発表日時を取得"""
        try:
            return self.fmp_utils["get_next_release"](self.INDICATOR_ID)
        except Exception as e:
            print(f"Error getting next release: {e}")
            return None

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """価格DIスプレッドデータを取得"""
        # Redisキャッシュチェック
        # FMP発表日(概要)ベースの should_refresh に加え、調査全容(zenyo)が概要の
        # 翌日公表のため「保有データが公表済みであるべき四半期に未達」なら再取得
        # （概要日の再取得だけだと全容公表前で旧四半期のまま固着するのを防ぐ）。
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if (last_updated_str and not self._should_refresh(last_updated_str)
                        and not self._needs_release_refetch(cached_data)):
                    cached_data["cached"] = True
                    cached_data["source"] = "redis"
                    cached_data["next_release"] = self._get_next_release()
                    return cached_data

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if (last_updated_str and not self._should_refresh(last_updated_str)
                        and not self._needs_release_refetch(file_cache)):
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    file_cache["cached"] = True
                    file_cache["source"] = "file"
                    file_cache["next_release"] = self._get_next_release()
                    return file_cache

        # 日銀短観からデータ取得してスプレッド計算
        result = self._fetch_and_calculate_spread()
        if result and result.get("data"):
            latest = result["data"][-1] if result["data"] else None
            next_release = self._get_next_release()

            cache_payload = {
                "data": result["data"],
                "latest": latest,
                "metadata": {
                    "source": "Bank of Japan (BOJ) Tankan Survey",
                    "description": "Price DI Spread = Selling Price DI - Purchase Price DI",
                    "unit": "%pt",
                    "frequency": "Quarterly",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result["data"],
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "boj",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            file_cache["cached"] = True
            file_cache["source"] = "file (fallback)"
            file_cache["next_release"] = self._get_next_release()
            return file_cache

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": self._get_next_release(),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    # 長期バックフィルの開始年（zenyo xlsx が遡れる範囲。これ以前は手動CSV種で補完）
    ZENYO_BACKFILL_START_YEAR = 2019

    def _build_long_history(self, data_type: str) -> Dict[str, Dict[str, Any]]:
        """zenyo 過去ファイルを年次ストライドで取得し、DI 系列の長期履歴を
        {date: data_point} で返す。1ファイルに数四半期分が入るため年1本で十分被覆。"""
        from datetime import datetime as _dt
        merged: Dict[str, Dict[str, Any]] = {}
        now = _dt.now(JST)
        # 直近の確定四半期（3/6/9/12）
        cur_q = 12 if now.month >= 12 else 9 if now.month >= 10 else 6 if now.month >= 7 else 3 if now.month >= 4 else 12
        cur_year = now.year if now.month >= 4 else now.year - 1
        for year in range(self.ZENYO_BACKFILL_START_YEAR, cur_year + 1):
            # 当年は最新四半期、過年は Q1(3月) ファイル（各ファイルが数四半期を内包）
            quarter = cur_q if year == cur_year else 3
            points = self.tankan_service.fetch_di_quarter(data_type, year, quarter)
            for p in points:
                if p.get("date"):
                    merged[p["date"]] = p
            # 当年は最新四半期も別途確保（年初Q1取得だと最新が落ちるのを防ぐ）
            if year == cur_year and quarter != 3:
                for p in self.tankan_service.fetch_di_quarter(data_type, year, 3):
                    if p.get("date"):
                        merged.setdefault(p["date"], p)
        return merged

    def _seed_from_manual_csv(self, data_type: str, merged: Dict[str, Dict[str, Any]]) -> None:
        """手動CSV種（BOJ時系列検索のネイティブCSV）で古い期間を補完する。
        `data/manual_update/japan/tankan/*.csv` を解析（zenyo優先・未充足のみ）。"""
        try:
            from services.japan.boj_tankan_manual_seed import seed_into
            seed_into(data_type, merged)
        except Exception as e:
            print(f"[price_di_spread] manual CSV seed failed for {data_type}: {e}")

    def _fetch_and_calculate_spread(self) -> Optional[Dict[str, Any]]:
        """販売価格DIと仕入価格DIの長期履歴を取得してスプレッドを計算"""
        try:
            print("Building long-term Price DI Spread from BOJ Tankan (zenyo backfill)...")

            selling_by_date = self._build_long_history("selling_price")
            self._seed_from_manual_csv("selling_price", selling_by_date)
            if not selling_by_date:
                print("No selling price data available")
                return None

            purchase_by_date = self._build_long_history("purchase_price")
            self._seed_from_manual_csv("purchase_price", purchase_by_date)
            if not purchase_by_date:
                print("No purchase price data available")
                return None

            # 共通の日付でスプレッドを計算
            common_dates = sorted(set(selling_by_date.keys()) & set(purchase_by_date.keys()))
            result_data = []

            for date_str in common_dates:
                selling = selling_by_date[date_str]
                purchase = purchase_by_date[date_str]

                # 大企業製造業のスプレッド
                large_mfg_selling = selling.get("large_manufacturing_current")
                large_mfg_purchase = purchase.get("large_manufacturing_current")
                large_mfg_spread = None
                if large_mfg_selling is not None and large_mfg_purchase is not None:
                    large_mfg_spread = round(large_mfg_selling - large_mfg_purchase, 1)

                # 大企業全産業のスプレッド
                all_ind_selling = selling.get("all_industries_current")
                all_ind_purchase = purchase.get("all_industries_current")
                all_ind_spread = None
                if all_ind_selling is not None and all_ind_purchase is not None:
                    all_ind_spread = round(all_ind_selling - all_ind_purchase, 1)

                # メインのスプレッド値（大企業製造業を使用）
                value = large_mfg_spread if large_mfg_spread is not None else all_ind_spread

                if value is not None:
                    result_data.append({
                        "date": date_str,
                        "value": value,
                        "spread": value,
                        "large_manufacturing_spread": large_mfg_spread,
                        "all_industries_spread": all_ind_spread,
                        "large_manufacturing_selling": large_mfg_selling,
                        "large_manufacturing_purchase": large_mfg_purchase,
                        "all_industries_selling": all_ind_selling,
                        "all_industries_purchase": all_ind_purchase,
                    })

            print(f"Calculated Price DI Spread: {len(result_data)} data points")
            if result_data:
                print(f"Latest: {result_data[-1]}")

            return {"data": result_data}

        except Exception as e:
            print(f"Error calculating Price DI Spread: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _needs_release_refetch(self, cached: Dict[str, Any]) -> bool:
        """調査全容(zenyo)公表スケジュール基準で、保有データが最新四半期に未達なら
        再取得を促す（レート制限付き）。判定失敗時は False（従来通りキャッシュ返却）。"""
        try:
            from services.japan.boj_tankan_schedule import needs_release_refetch
            return needs_release_refetch(cached)
        except Exception:
            return False

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日ベース）"""
        try:
            return self.fmp_utils["should_refresh"](
                self.INDICATOR_ID,
                last_updated_str
            )
        except Exception as e:
            print(f"Error in _should_refresh: {e}")
            # フォールバック: 7日以上経過していれば更新
            try:
                last_updated = datetime.fromisoformat(last_updated_str)
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=JST)
                now = datetime.now(JST)
                return (now - last_updated).days >= 7
            except Exception:
                return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Japan Price DI Spread",
            "source": "Bank of Japan (BOJ) Tankan Survey",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
japan_price_di_spread_service = JapanPriceDISpreadService()
