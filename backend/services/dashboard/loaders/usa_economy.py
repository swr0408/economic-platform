"""
米国経済ダッシュボードローダー
GDP成長率、GDP寄与度、GDP項目別成長率、潜在成長率、銀行貸し出し態度を一括取得

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
        from services.usa.bea_schedule_service import bea_schedule_service

        result = {
            "gdp_growth_rate": None,
            "gdp_contributions": None,
            "gdp_components_growth": None,
            "potential_gdp": None,
            "bank_lending": None,
            "next_gdp_release": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(self._get_gdp_growth_rate, gdp_service): "gdp_growth_rate",
                executor.submit(self._get_gdp_contributions, gdp_contributions_service): "gdp_contributions",
                executor.submit(self._get_gdp_components_growth, bea_gdp_components_service): "gdp_components_growth",
                executor.submit(self._get_potential_gdp, potential_gdp_service): "potential_gdp",
                executor.submit(self._get_bank_lending, bank_lending_service): "bank_lending",
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
