"""
グローバル経済ダッシュボードローダー
グローバル製造業PMI等を一括取得
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class GlobalEconomyLoader(BaseDashboardLoader):
    """
    グローバル経済ダッシュボード用データローダー

    取得データ:
    - jpmorgan_global_manufacturing_pmi: J.P.Morgan グローバル製造業PMI
    """

    COUNTRY_CODE = "global"
    CATEGORY_CODE = "economy"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "jpmorgan_global_manufacturing_pmi",
        "economic_surprise_index_screenshot_url",
        "komtrax_screenshot_url",
        "global_epu",
        "semiconductor_sales",
        "taiwan_pmi_outlook",
        "taiwan_manufacturing_pmi",
        "south_korean_exports",
        "kr_semiconductor_exports",
        "taiwan_export_orders",
        "taiwan_electrical_equipment_exports",
        "china_shanghai_container_freight_index",
        "oecd_cli",
    ]

    # null値チェックをスキップするキー（スクリーンショットは存在しなくてもOK）
    NULL_VALUE_SKIP_KEYS = {"economic_surprise_index_screenshot_url", "komtrax_screenshot_url"}

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_expected_keys(self) -> List[str]:
        """期待されるデータキーのリストを返す"""
        return self.EXPECTED_KEYS

    def get_manual_csv_paths(self) -> List[Path]:
        """手動更新CSV（J.P.Morgan グローバル製造業PMI）を監視対象に宣言。

        手動CSVを編集しても指標の発表日時は変わらないため、発表日時ベースの
        stale 判定では検知できず集約キャッシュが古いまま配信され続ける。
        ここで宣言すると base._is_cache_stale が mtime 変化を検知し、
        集約キャッシュ（main/light）を自動再構築する。
        """
        # `global` は予約語のため from import 不可。importlib 経由で取得する。
        import importlib
        csv_file = importlib.import_module(
            "services.global.global_manufacturing_pmi_service"
        ).CSV_FILE
        return [csv_file]

    def _has_null_values(self, cached_data: Dict[str, Any]) -> bool:
        """キャッシュにNone値が含まれているかチェック（スクリーンショットURLはスキップ）"""
        data = cached_data.get("data", {})
        if not isinstance(data, dict):
            return False

        for key, value in data.items():
            if key.startswith("next_"):
                continue
            if key in self.NULL_VALUE_SKIP_KEYS:
                continue
            if value is None:
                print(f"Cache has null value for '{key}' in {self.COUNTRY_CODE}:{self.CATEGORY_CODE}")
                return True

        return False


    def _detect_stale_indicators(self, last_updated: Optional[str]) -> set:
        """
        発表日時を過ぎた指標を検出（FMPカレンダー自動判定）
        """
        if last_updated is None:
            return set()

        try:
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)

            now = datetime.now(JST)
            release_datetimes = self.get_release_datetimes()

            for release_dt in release_datetimes:
                if release_dt and last_updated_dt < release_dt <= now:
                    return {"all"}

        except Exception as e:
            print(f"Error detecting stale indicators: {e}")
            # エラー時に {"all"} を返すと、エラーが続く限り毎リクエストで全指標の
            # 外部API一斉取得が走りイベントループ/executorを圧迫する (2026-06-13 障害)。
            # 判定不能時はキャッシュ継続に倒す (各サービスのスケジューラが個別に更新する)。
            return set()

        return set()

    def _should_force_refresh(self, indicator: str) -> bool:
        """指標が強制更新対象かどうかを判定"""
        if "all" in self._stale_indicators:
            return True
        return indicator in self._stale_indicators

    def _prepare_for_refresh(self, last_updated: Optional[str]) -> None:
        """データ再取得の前処理"""
        self._stale_indicators = self._detect_stale_indicators(last_updated)
        if self._stale_indicators:
            print(f"[GlobalEconomy] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """全経済データを取得"""
        import importlib

        result = {
            "jpmorgan_global_manufacturing_pmi": None,
            "economic_surprise_index_screenshot_url": None,
            "komtrax_screenshot_url": None,
            "global_epu": None,
            "semiconductor_sales": None,
            "taiwan_pmi_outlook": None,
            "taiwan_manufacturing_pmi": None,
            "south_korean_exports": None,
            "kr_semiconductor_exports": None,
            "taiwan_export_orders": None,
            "taiwan_electrical_equipment_exports": None,
            "china_shanghai_container_freight_index": None,
            "oecd_cli": None,
        }

        # PMI データ
        try:
            _pmi_mod = importlib.import_module("services.global.global_manufacturing_pmi_service")
            svc = _pmi_mod.global_manufacturing_pmi_service
            result["jpmorgan_global_manufacturing_pmi"] = self._get_indicator(
                svc, "jpmorgan_global_manufacturing_pmi", "Global Manufacturing PMI"
            )
        except Exception as e:
            print(f"[GlobalEconomy] Error loading Global Manufacturing PMI module: {e}")

        # Economic Surprise Index screenshot URL
        try:
            _esi_mod = importlib.import_module("services.global.economic_surprise_index_screenshot_service")
            svc = _esi_mod.economic_surprise_index_screenshot_service
            info = svc.get_screenshot_url()
            result["economic_surprise_index_screenshot_url"] = info.get("screenshot_url")
        except Exception as e:
            print(f"[GlobalEconomy] Error getting Economic Surprise Index screenshot URL: {e}")

        # Komtrax screenshot URL
        try:
            _km_mod = importlib.import_module("services.global.komtrax_screenshot_service")
            svc = _km_mod.komtrax_screenshot_service
            info = svc.get_screenshot_url()
            result["komtrax_screenshot_url"] = info.get("screenshot_url")
        except Exception as e:
            print(f"[GlobalEconomy] Error getting Komtrax screenshot URL: {e}")

        # Global EPU (月次)
        try:
            _epu_mod = importlib.import_module("services.global.global_epu_service")
            svc = _epu_mod.global_epu_service
            result["global_epu"] = self._get_indicator(
                svc, "global_epu", "Global EPU"
            )
        except Exception as e:
            print(f"[GlobalEconomy] Error loading Global EPU module: {e}")

        # WSTS Semiconductor Sales
        try:
            _semi_mod = importlib.import_module("services.global.semiconductor_sales_service")
            svc = _semi_mod.semiconductor_sales_service
            result["semiconductor_sales"] = self._get_semiconductor_sales(svc)
        except Exception as e:
            print(f"[GlobalEconomy] Error loading Semiconductor Sales module: {e}")

        # Taiwan PMI Outlook (Electronic & Optical)
        try:
            _tw_mod = importlib.import_module("services.global.taiwan_pmi_outlook_service")
            svc = _tw_mod.taiwan_pmi_outlook_service
            result["taiwan_pmi_outlook"] = self._get_indicator(
                svc, "taiwan_pmi_outlook", "Taiwan PMI Outlook"
            )
        except Exception as e:
            print(f"[GlobalEconomy] Error loading Taiwan PMI Outlook module: {e}")

        # Taiwan Manufacturing PMI (S&P Global)
        try:
            _tw_mfg_mod = importlib.import_module("services.global.taiwan_manufacturing_pmi_service")
            svc = _tw_mfg_mod.taiwan_manufacturing_pmi_service
            result["taiwan_manufacturing_pmi"] = self._get_indicator(
                svc, "taiwan_manufacturing_pmi", "Taiwan Manufacturing PMI"
            )
        except Exception as e:
            print(f"[GlobalEconomy] Error loading Taiwan Manufacturing PMI module: {e}")

        # South Korean Exports YoY
        try:
            _kr_mod = importlib.import_module("services.global.south_korean_exports_service")
            svc = _kr_mod.south_korean_exports_service
            result["south_korean_exports"] = self._get_indicator(
                svc, "south_korean_exports", "South Korean Exports"
            )
        except Exception as e:
            print(f"[GlobalEconomy] Error loading South Korean Exports module: {e}")

        # KR Semiconductor Exports
        try:
            _kr_semi_mod = importlib.import_module("services.global.kr_semiconductor_exports_service")
            svc = _kr_semi_mod.kr_semiconductor_exports_service
            result["kr_semiconductor_exports"] = self._get_indicator(
                svc, "kr_semiconductor_exports", "KR Semiconductor Exports"
            )
        except Exception as e:
            print(f"[GlobalEconomy] Error loading KR Semiconductor Exports module: {e}")

        # Taiwan Export Orders YoY
        try:
            _tw_eo_mod = importlib.import_module("services.global.taiwan_export_orders_service")
            svc = _tw_eo_mod.taiwan_export_orders_service
            result["taiwan_export_orders"] = self._get_indicator(
                svc, "taiwan_export_orders", "Taiwan Export Orders"
            )
        except Exception as e:
            print(f"[GlobalEconomy] Error loading Taiwan Export Orders module: {e}")

        # Taiwan Electrical Equipment Exports
        try:
            _tw_ee_mod = importlib.import_module("services.global.taiwan_electrical_equipment_exports_service")
            svc = _tw_ee_mod.taiwan_electrical_equipment_exports_service
            result["taiwan_electrical_equipment_exports"] = self._get_indicator(
                svc, "taiwan_electrical_equipment_exports", "Taiwan Electrical Equipment Exports"
            )
        except Exception as e:
            print(f"[GlobalEconomy] Error loading Taiwan Electrical Equipment Exports module: {e}")

        # China Shanghai Container Freight Index (SCFI / CCFI)
        try:
            _cfi_mod = importlib.import_module("services.global.china_shanghai_container_freight_index_service")
            svc = _cfi_mod.china_shanghai_container_freight_index_service
            result["china_shanghai_container_freight_index"] = self._get_indicator(
                svc, "china_shanghai_container_freight_index", "Container Freight Index"
            )
        except Exception as e:
            print(f"[GlobalEconomy] Error loading Container Freight Index module: {e}")

        # OECD CLI（景気先行指数）
        try:
            _oecd_cli_mod = importlib.import_module("services.global.oecd_cli_service")
            svc = _oecd_cli_mod.oecd_cli_service
            result["oecd_cli"] = self._get_indicator(
                svc, "oecd_cli", "OECD CLI"
            )
        except Exception as e:
            print(f"[GlobalEconomy] Error loading OECD CLI module: {e}")

        return result

    def _get_semiconductor_sales(self, service) -> dict:
        """半導体売上高データを取得（yoy_data, mma_data, mma_yoy_dataも含む）"""
        try:
            force_refresh = self._should_force_refresh("semiconductor_sales")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "yoy_data": response.get("yoy_data", []),
                "mma_data": response.get("mma_data", []),
                "mma_yoy_data": response.get("mma_yoy_data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[GlobalEconomy] Error getting Semiconductor Sales: {e}")
            return {"data": [], "yoy_data": [], "mma_data": [], "mma_yoy_data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_indicator(self, service, indicator_key: str, label: str) -> dict:
        """指標データを取得"""
        try:
            force_refresh = self._should_force_refresh(indicator_key)
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[GlobalEconomy] Error getting {label}: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
