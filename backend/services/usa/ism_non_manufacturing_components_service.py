"""
ISM非製造業サブインデックスサービス
DBnomics APIからISM非製造業の構成要素データを取得

データソース:
- DBnomics: https://db.nomics.world/ISM
- 新規受注: ISM/nm-neword/in
- 業況活動: ISM/nm-busact/in
- 雇用: ISM/nm-employment/in
- サプライヤー配送: ISM/nm-supdel/in
- 価格（仕入価格）: ISM/nm-prices/in
- 在庫: ISM/nm-inventories/in

発表スケジュール:
- 毎月第3営業日付近（ISM非製造業景況指数と同時）
- ISMスケジュールサービスから次回発表日を取得

キャッシュ方式: last_updated判定方式
- ISM非製造業景況指数の次回発表日で判定
"""
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# DBnomics API設定
DBNOMICS_BASE_URL = "https://api.db.nomics.world/v22"

# ISM非製造業サブインデックスのシリーズコード
ISM_NM_SERIES = {
    "new_orders": "ISM/nm-neword/in",
    "business_activity": "ISM/nm-busact/in",
    "employment": "ISM/nm-employment/in",
    "supplier_deliveries": "ISM/nm-supdel/in",
    "prices": "ISM/nm-prices/in",
    "inventories": "ISM/nm-inventories/in",
}


class ISMNonManufacturingComponentsService:
    """ISM非製造業サブインデックスサービス"""

    CACHE_KEY = "dbnomics:ism_non_manufacturing_components"
    ECONALPHA_ID = "ism_non_manufacturing"  # FMPマッピング用ID

    def __init__(self):
        """初期化"""
        pass

    def get_ism_non_manufacturing_components_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        ISM非製造業サブインデックスデータを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [
                    {
                        "date": "YYYY-MM-01",
                        "new_orders": float,
                        "business_activity": float,
                        "employment": float,
                        "supplier_deliveries": float,
                        "prices": float,
                        "inventories": float,
                        "order_inventory_balance": float,
                        "order_inventory_balance_3ma": float
                    },
                    ...
                ],
                "latest": {...},
                "next_release": {...} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # キャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY)
            if cached_data:
                # last_updated判定: ISM非製造業の発表日を過ぎていたらキャッシュ無効
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": None,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # DBnomics APIから取得
        fetched_result = self._fetch_from_dbnomics()

        if fetched_result and fetched_result.get("data"):
            fetched_data = fetched_result["data"]

            # 日付でソート（昇順）
            fetched_data.sort(key=lambda x: x["date"])

            # 最新値を取得
            latest = fetched_data[-1] if fetched_data else None

            cache_payload = {
                "data": fetched_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            # last_updated方式: TTL=0（無期限、発表日判定で無効化）
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)

            return {
                "data": fetched_data,
                "latest": latest,
                "next_release": None,
                "cached": False,
                "source": "dbnomics",
                "last_updated": datetime.now(JST).isoformat()
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        FMPスケジュールベースの3分方式で判定
        """
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def _fetch_from_dbnomics(self) -> Optional[Dict[str, Any]]:
        """DBnomics APIからISM非製造業サブインデックスデータを取得"""
        try:
            print("Fetching ISM Non-Manufacturing Components from DBnomics...")

            # 全シリーズを順次取得
            series_data = {}

            for name, series_code in ISM_NM_SERIES.items():
                try:
                    url = f"{DBNOMICS_BASE_URL}/series/{series_code}?observations=1&format=json"
                    response = requests.get(url, timeout=30)
                    response.raise_for_status()
                    data = response.json()

                    # データを抽出
                    extracted = self._extract_series_data(data)
                    if extracted:
                        series_data[name] = extracted
                        print(f"  {name}: {len(extracted)} records")
                except Exception as e:
                    print(f"  Error fetching {name}: {e}")
                    continue

            if not series_data:
                print("No data fetched from DBnomics")
                return None

            # データを統合
            combined_data = self._combine_series_data(series_data)

            if combined_data:
                print(f"Combined {len(combined_data)} ISM Non-Manufacturing Components records")
                return {"data": combined_data}

            return None

        except Exception as e:
            print(f"Error fetching ISM Non-Manufacturing Components from DBnomics: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_series_data(self, data: Dict) -> Optional[List[Dict[str, Any]]]:
        """DBnomicsレスポンスからシリーズデータを抽出"""
        try:
            if not data or not isinstance(data, dict):
                return None

            series = data.get("series", {})
            if not series:
                return None

            docs = series.get("docs", [])
            if not docs or not isinstance(docs, list):
                return None

            doc = docs[0]
            periods = doc.get("period", [])
            values = doc.get("value", [])

            if not periods or not values or len(periods) != len(values):
                return None

            result = []
            for i, period in enumerate(periods):
                value = values[i]
                if value is not None and not (isinstance(value, float) and value != value):  # NaN check
                    result.append({
                        "period": str(period),
                        "value": float(value)
                    })

            return result

        except Exception as e:
            print(f"Error extracting series data: {e}")
            return None

    def _combine_series_data(self, series_data: Dict[str, List[Dict]]) -> List[Dict[str, Any]]:
        """複数シリーズのデータを期間ごとに統合し、受注在庫バランスを計算"""
        try:
            # 期間をキーにしてデータを統合
            combined = {}

            for series_name, data_points in series_data.items():
                for point in data_points:
                    period = point["period"]
                    value = point["value"]

                    if period not in combined:
                        combined[period] = {
                            "date": f"{period}-01",  # YYYY-MM → YYYY-MM-01
                        }

                    combined[period][series_name] = value

            # 全項目が揃っているレコードのみを返す
            result = []
            required_fields = ["new_orders", "inventories"]  # 受注在庫バランス計算に必須

            for period, data in combined.items():
                # 少なくとも受注と在庫が揃っているか確認
                if all(field in data for field in required_fields):
                    new_orders = data.get("new_orders")
                    inventories = data.get("inventories")

                    # 受注在庫バランスを計算
                    order_inventory_balance = None
                    if new_orders is not None and inventories is not None:
                        order_inventory_balance = round(new_orders - inventories, 1)

                    full_data = {
                        "date": data["date"],
                        "new_orders": new_orders,
                        "business_activity": data.get("business_activity"),
                        "employment": data.get("employment"),
                        "supplier_deliveries": data.get("supplier_deliveries"),
                        "prices": data.get("prices"),
                        "inventories": inventories,
                        "order_inventory_balance": order_inventory_balance,
                    }
                    result.append(full_data)

            # 日付でソート
            result = sorted(result, key=lambda x: x["date"])

            # 3ヶ月移動平均を計算
            for i, item in enumerate(result):
                if i >= 2:
                    # 直近3ヶ月の受注在庫バランスの平均
                    balances = [
                        result[i - 2].get("order_inventory_balance"),
                        result[i - 1].get("order_inventory_balance"),
                        item.get("order_inventory_balance"),
                    ]
                    if all(b is not None for b in balances):
                        item["order_inventory_balance_3ma"] = round(sum(balances) / 3, 1)
                    else:
                        item["order_inventory_balance_3ma"] = None
                else:
                    item["order_inventory_balance_3ma"] = None

            return result

        except Exception as e:
            print(f"Error combining series data: {e}")
            return []

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_exists = redis_client.exists(self.CACHE_KEY)
        cached_data = redis_client.get(self.CACHE_KEY) if cache_exists else None

        return {
            "cache_key": self.CACHE_KEY,
            "exists": cache_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID)
        }


# シングルトンインスタンス
ism_non_manufacturing_components_service = ISMNonManufacturingComponentsService()
