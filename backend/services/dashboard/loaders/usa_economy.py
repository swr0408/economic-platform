"""
米国経済ダッシュボードローダー
GDP成長率、GDP寄与度、GDP項目別成長率、潜在成長率、銀行貸し出し態度、FCI-G、NFCI、GDPNow、ISM製造業、ISMサブインデックスを一括取得

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
    - next_gdp_release: 次回GDP発表情報

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
            "next_gdp_release": None,
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
                executor.submit(self._get_next_gdp_release, bea_schedule_service): "next_gdp_release",
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
