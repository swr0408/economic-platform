"""
米国経済ダッシュボードローダー
GDP成長率、GDP寄与度、GDP項目別成長率、潜在成長率、銀行貸し出し態度、FCI-G、NFCI、GDPNow、
ISM製造業、ISMサブインデックス、ISM非製造業、ISM非製造業サブインデックス、
NY連銀製造業景気指数、フィラデルフィア連銀製造業景気指数、NFIB中小企業楽観指数、
NFIB中小企業設備投資計画、鉱工業生産、設備稼働率を一括取得

キャッシュ更新判定: last_updated方式（スケジュール時刻ベース）
"""
from typing import Dict, Any, Optional
from datetime import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


class USAEconomyLoader(BaseDashboardLoader):
    """
    米国経済ダッシュボード用データローダー

    取得データ:
    - gdp_growth_rate: GDP成長率（前期比年率）- FRED A191RL1Q225SBEA
    - gdp_contributions: GDP寄与度（5項目）- FRED各シリーズ
    - gdp_components_growth: GDP項目別成長率 - BEA NIPA T10101
    - potential_gdp: 潜在成長率（名目/実質）- FRED GDPPOT, NGDPPOT
    - bank_lending: 銀行貸し出し態度（SLOOS）- FRED DRTSCILM
    - fci: FCI-G（金融情勢指数）- Federal Reserve CSV
    - nfci: シカゴ連銀金融環境指数 - FRED NFCI（毎週水曜日更新）
    - gdpnow: GDPNow（リアルタイムGDP予測）- Atlanta Fed（月6-7回更新）
    - ism_manufacturing: ISM製造業景況指数 - Investing.com（毎月第1営業日）
    - ism_components: ISM製造業サブインデックス - DBnomics（毎月第1営業日）
    - ism_non_manufacturing: ISM非製造業景況指数 - DBnomics（毎月第3営業日）
    - ism_non_manufacturing_components: ISM非製造業サブインデックス - DBnomics（毎月第3営業日）
    - empire_state: NY連銀製造業景気指数 - FRED（毎月15日付近）
    - philadelphia_fed: フィラデルフィア連銀製造業景気指数 - FRED（毎月第3木曜日）
    - nfib: NFIB中小企業楽観指数 - NFIB PDF（毎月第2火曜日）
    - nfib_capex: NFIB中小企業設備投資計画 - NFIB PDF（毎月第2火曜日）
    - industrial_production: 鉱工業生産 - FRED INDPRO（毎月14〜18日頃）
    - capacity_utilization: 設備稼働率 - FRED TCU（毎月14〜18日頃、鉱工業生産と同時）
    - next_gdp_release: 次回GDP発表情報
    - next_ism_non_manufacturing_release: 次回ISM非製造業発表情報

    キャッシュ方式: last_updated判定（スケジュール時刻: 22:00 JST = 8:00 ET + 9時間 + バッファ）
    """

    COUNTRY_CODE = "usa"
    CATEGORY_CODE = "economy"

    def get_schedule_time(self) -> Optional[time]:
        """
        スケジュール時刻を返す
        BEA発表時刻(8:30 ET)の日本時間相当 + バッファ = 22:00 JST
        """
        return time(22, 0)  # 22:00 JST

    def load_all(self) -> Dict[str, Any]:
        """
        全経済データを並列で取得

        Returns:
            {
                "gdp_growth_rate": [...],
                "gdp_contributions": {"data": [...], "series_info": {...}},
                "gdp_components_growth": [...],
                "next_gdp_release": {...}
            }
        """
        # 遅延インポート（循環参照回避）
        from services.usa.gdp_service import gdp_service
        from services.usa.gdp_contributions_service import gdp_contributions_service
        from services.usa.bea_gdp_components_service import bea_gdp_components_service
        from services.usa.potential_gdp_service import potential_gdp_service
        from services.usa.bank_lending_service import bank_lending_service
        from services.usa.fci_service import fci_service
        from services.usa.nfci_service import nfci_service
        from services.usa.gdpnow_service import gdpnow_service
        from services.usa.ism_manufacturing_service import ism_manufacturing_service
        from services.usa.ism_components_service import ism_components_service
        from services.usa.ism_non_manufacturing_service import ism_non_manufacturing_service
        from services.usa.ism_non_manufacturing_components_service import ism_non_manufacturing_components_service
        from services.usa.empire_state_service import empire_state_service
        from services.usa.philadelphia_fed_service import philadelphia_fed_service
        from services.usa.nfib_service import nfib_service
        from services.usa.industrial_production_service import industrial_production_service
        from services.usa.capacity_utilization_service import capacity_utilization_service
        from services.usa.bea_schedule_service import bea_schedule_service

        result = {
            "gdp_growth_rate": None,
            "gdp_contributions": None,
            "gdp_components_growth": None,
            "potential_gdp": None,
            "bank_lending": None,
            "fci": None,
            "nfci": None,
            "gdpnow": None,
            "ism_manufacturing": None,
            "ism_components": None,
            "ism_non_manufacturing": None,
            "ism_non_manufacturing_components": None,
            "empire_state": None,
            "philadelphia_fed": None,
            "nfib": None,
            "nfib_capex": None,
            "industrial_production": None,
            "capacity_utilization": None,
            "next_gdp_release": None,
            "next_ism_non_manufacturing_release": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(self._get_gdp_growth_rate, gdp_service): "gdp_growth_rate",
                executor.submit(self._get_gdp_contributions, gdp_contributions_service): "gdp_contributions",
                executor.submit(self._get_gdp_components_growth, bea_gdp_components_service): "gdp_components_growth",
                executor.submit(self._get_potential_gdp, potential_gdp_service): "potential_gdp",
                executor.submit(self._get_bank_lending, bank_lending_service): "bank_lending",
                executor.submit(self._get_fci, fci_service): "fci",
                executor.submit(self._get_nfci, nfci_service): "nfci",
                executor.submit(self._get_gdpnow, gdpnow_service): "gdpnow",
                executor.submit(self._get_ism_manufacturing, ism_manufacturing_service): "ism_manufacturing",
                executor.submit(self._get_ism_components, ism_components_service): "ism_components",
                executor.submit(self._get_ism_non_manufacturing, ism_non_manufacturing_service): "ism_non_manufacturing",
                executor.submit(self._get_ism_non_manufacturing_components, ism_non_manufacturing_components_service): "ism_non_manufacturing_components",
                executor.submit(self._get_empire_state, empire_state_service): "empire_state",
                executor.submit(self._get_philadelphia_fed, philadelphia_fed_service): "philadelphia_fed",
                executor.submit(self._get_nfib, nfib_service): "nfib",
                executor.submit(self._get_nfib_capex, nfib_service): "nfib_capex",
                executor.submit(self._get_industrial_production, industrial_production_service): "industrial_production",
                executor.submit(self._get_capacity_utilization, capacity_utilization_service): "capacity_utilization",
                executor.submit(self._get_next_gdp_release, bea_schedule_service): "next_gdp_release",
                executor.submit(self._get_next_ism_non_manufacturing_release, ism_non_manufacturing_service): "next_ism_non_manufacturing_release",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_gdp_growth_rate(self, service) -> list:
        """GDP成長率データを取得"""
        try:
            response = service.get_gdp_growth_rate()
            return response.get("data", [])
        except Exception as e:
            print(f"Error getting GDP growth rate: {e}")
            return []

    def _get_gdp_contributions(self, service) -> Optional[dict]:
        """GDP寄与度データを取得"""
        try:
            response = service.get_gdp_contributions()
            return {
                "data": response.get("data", []),
                "series_info": response.get("series_info", {})
            }
        except Exception as e:
            print(f"Error getting GDP contributions: {e}")
            return None

    def _get_gdp_components_growth(self, service) -> Optional[list]:
        """GDP項目別成長率データを取得"""
        try:
            response = service.get_gdp_components_growth()
            data = response.get("data", [])
            # データが空の場合はNoneを返す（フロントでloadingではなく「利用不可」表示になる）
            return data if data else None
        except Exception as e:
            print(f"Error getting GDP components growth: {e}")
            return None

    def _get_potential_gdp(self, service) -> Optional[dict]:
        """潜在成長率データを取得"""
        try:
            response = service.get_potential_gdp()
            real_data = response.get("real", [])
            nominal_data = response.get("nominal", [])
            # データが両方空の場合はNoneを返す
            if not real_data and not nominal_data:
                return None
            return {
                "real": real_data,
                "nominal": nominal_data
            }
        except Exception as e:
            print(f"Error getting potential GDP: {e}")
            return None

    def _get_bank_lending(self, service) -> Optional[dict]:
        """銀行貸し出し態度データを取得"""
        try:
            response = service.get_bank_lending_standards()
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "next_release": response.get("next_release")
            }
        except Exception as e:
            print(f"Error getting bank lending standards: {e}")
            return None

    def _get_next_gdp_release(self, service) -> Optional[dict]:
        """次回GDP発表情報を取得"""
        try:
            return service.get_next_gdp_release()
        except Exception as e:
            print(f"Error getting next GDP release: {e}")
            return None

    def _get_fci(self, service) -> Optional[dict]:
        """FCI-G（金融情勢指数）データを取得"""
        try:
            response = service.get_fci_data()
            baseline = response.get("baseline", {})
            oneyear = response.get("oneyear", {})

            # データが両方空の場合はNoneを返す
            if not baseline.get("data") and not oneyear.get("data"):
                return None

            return {
                "baseline": {
                    "data": baseline.get("data", []),
                    "latest": baseline.get("latest")
                },
                "oneyear": {
                    "data": oneyear.get("data", []),
                    "latest": oneyear.get("latest")
                }
            }
        except Exception as e:
            print(f"Error getting FCI data: {e}")
            return None

    def _get_nfci(self, service) -> Optional[dict]:
        """シカゴ連銀金融環境指数（NFCI）データを取得"""
        try:
            response = service.get_nfci_data()
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest")
            }
        except Exception as e:
            print(f"Error getting NFCI data: {e}")
            return None

    def _get_gdpnow(self, service) -> Optional[dict]:
        """GDPNow（リアルタイムGDP予測）データを取得"""
        try:
            response = service.get_gdpnow_data()
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest")
            }
        except Exception as e:
            print(f"Error getting GDPNow data: {e}")
            return None

    def _get_ism_manufacturing(self, service) -> Optional[dict]:
        """ISM製造業景況指数データを取得"""
        try:
            response = service.get_ism_manufacturing_data()
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "next_release": response.get("next_release")
            }
        except Exception as e:
            print(f"Error getting ISM Manufacturing data: {e}")
            return None

    def _get_ism_components(self, service) -> Optional[dict]:
        """ISM製造業サブインデックスデータを取得"""
        try:
            response = service.get_ism_components_data()
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "next_release": response.get("next_release")
            }
        except Exception as e:
            print(f"Error getting ISM Components data: {e}")
            return None

    def _get_ism_non_manufacturing(self, service) -> Optional[dict]:
        """ISM非製造業景況指数データを取得"""
        try:
            response = service.get_ism_non_manufacturing_data()
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting ISM Non-Manufacturing data: {e}")
            return None

    def _get_ism_non_manufacturing_components(self, service) -> Optional[dict]:
        """ISM非製造業サブインデックスデータを取得"""
        try:
            response = service.get_ism_non_manufacturing_components_data()
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting ISM Non-Manufacturing Components data: {e}")
            return None

    def _get_next_ism_non_manufacturing_release(self, service) -> Optional[dict]:
        """次回ISM非製造業発表情報を取得（Investing.comから都度取得）"""
        try:
            # ISM非製造業サービスから次回発表情報を取得
            return service._get_next_release()
        except Exception as e:
            print(f"Error getting next ISM Non-Manufacturing release: {e}")
            return None

    def _get_empire_state(self, service) -> Optional[dict]:
        """NY連銀製造業景気指数データを取得"""
        try:
            response = service.get_empire_state_data()
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting Empire State data: {e}")
            return None

    def _get_philadelphia_fed(self, service) -> Optional[dict]:
        """フィラデルフィア連銀製造業景気指数データを取得"""
        try:
            response = service.get_philadelphia_fed_data()
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
                "series_config": response.get("series_config"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting Philadelphia Fed data: {e}")
            return None

    def _get_nfib(self, service) -> Optional[dict]:
        """NFIB中小企業楽観指数データを取得"""
        try:
            response = service.get_nfib_data()
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting NFIB data: {e}")
            return None

    def _get_nfib_capex(self, service) -> Optional[dict]:
        """NFIB中小企業設備投資計画データを取得"""
        try:
            response = service.get_capex_plans_data()
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting NFIB CapEx data: {e}")
            return None

    def _get_industrial_production(self, service) -> Optional[dict]:
        """鉱工業生産データを取得"""
        try:
            response = service.get_industrial_production_data()
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting Industrial Production data: {e}")
            return None

    def _get_capacity_utilization(self, service) -> Optional[dict]:
        """設備稼働率データを取得"""
        try:
            response = service.get_capacity_utilization_data()
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting Capacity Utilization data: {e}")
            return None
