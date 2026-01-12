"""
ユーロ圏経済ダッシュボードローダー
ECB GDP、GDP構成要素、銀行貸出調査、鉱工業生産、ESI、政策不確実性指数、PMIなどの経済指標を一括取得

キャッシュ更新判定: 日次更新方式
- ECB GDP: 毎日18:00 CET更新
- ECB GDP Components: 毎日18:00 CET更新
- ECB BLS: 毎日18:00 CET更新
- ECB Production: 毎日18:00 CET更新
- Eurostat ESI: FMP発表日時ベース更新
- Euro Policy Uncertainty: 24時間TTL更新
- EU PMI: FMP発表日時ベース更新
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class EurozoneEconomyLoader(BaseDashboardLoader):
    """
    ユーロ圏経済ダッシュボード用データローダー

    取得データ:
    - ecb_gdp: ECB GDP成長率（前期比・前年比）
    - ecb_gdp_components: ECB GDP構成要素別寄与度
    - ecb_bls: ECB 銀行貸出調査（企業向け・家計向け）
    - ecb_production: ECB 鉱工業生産（WDA指数・前月比・前年比）
    - eurostat_esi: Eurostat ESI（ユーロ圏・ドイツ・フランス・イタリア）
    - euro_policy_uncertainty: 欧州経済政策不確実性指数
    - eu_pmi: HCOB PMI（製造業・サービス業・総合）

    キャッシュ方式: 日次更新
    - ECB GDP: 毎日18:00 CET更新
    - ECB GDP Components: 毎日18:00 CET更新
    - ECB BLS: 毎日18:00 CET更新
    - ECB Production: 毎日18:00 CET更新
    - Eurostat ESI: FMP発表日時ベース更新
    - Euro Policy Uncertainty: 24時間TTL更新
    - EU PMI: FMP発表日時ベース更新
    """

    COUNTRY_CODE = "eurozone"
    CATEGORY_CODE = "economy"

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        """
        各指標の発表日時リストを返す
        """
        return []

    def _detect_stale_indicators(self, last_updated: Optional[str]) -> set:
        """
        発表日時を過ぎた指標を検出
        """
        stale = set()

        if last_updated is None:
            return {"all"}

        try:
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 24時間以上経過していれば更新
            if (now - last_updated_dt) > timedelta(hours=24):
                stale.add("ecb_gdp")
                stale.add("ecb_gdp_components")
                stale.add("ecb_bls")
                stale.add("ecb_production")
                stale.add("eurostat_esi")
                stale.add("euro_policy_uncertainty")
                stale.add("eu_pmi")

        except Exception as e:
            print(f"Error detecting stale indicators: {e}")
            return {"all"}

        return stale

    def _should_force_refresh(self, indicator: str) -> bool:
        """指標が強制更新対象かどうかを判定"""
        if "all" in self._stale_indicators:
            return True
        return indicator in self._stale_indicators

    def _prepare_for_refresh(self, last_updated: Optional[str]) -> None:
        """
        データ再取得の前処理
        """
        self._stale_indicators = self._detect_stale_indicators(last_updated)
        if self._stale_indicators:
            print(f"Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全経済データを並列で取得

        Returns:
            {
                "ecb_gdp": {...},
                "ecb_gdp_components": {...},
                "ecb_bls": {...},
                "ecb_production": {...},
                "eurostat_esi": {...},
                "euro_policy_uncertainty": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.eurozone.ecb_gdp_service import ecb_gdp_service
        from services.eurozone.ecb_gdp_components_service import ecb_gdp_components_service
        from services.eurozone.ecb_bls_service import ecb_bls_service
        from services.eurozone.ecb_production_service import ecb_production_service
        from services.eurozone.eurostat_esi_service import eurostat_esi_service
        from services.eurozone.euro_policy_uncertainty_service import euro_policy_uncertainty_service
        from services.eurozone.eu_pmi_service import eu_pmi_service

        result = {
            "ecb_gdp": None,
            "ecb_gdp_components": None,
            "ecb_bls": None,
            "ecb_production": None,
            "eurostat_esi": None,
            "euro_policy_uncertainty": None,
            "eu_pmi": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(self._get_ecb_gdp, ecb_gdp_service): "ecb_gdp",
                executor.submit(self._get_ecb_gdp_components, ecb_gdp_components_service): "ecb_gdp_components",
                executor.submit(self._get_ecb_bls, ecb_bls_service): "ecb_bls",
                executor.submit(self._get_ecb_production, ecb_production_service): "ecb_production",
                executor.submit(self._get_eurostat_esi, eurostat_esi_service): "eurostat_esi",
                executor.submit(self._get_euro_policy_uncertainty, euro_policy_uncertainty_service): "euro_policy_uncertainty",
                executor.submit(self._get_eu_pmi, eu_pmi_service): "eu_pmi",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_ecb_gdp(self, service) -> dict:
        """ECB GDPデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ecb_gdp")
            response = service.get_ecb_gdp_data(force_refresh=force_refresh)
            return {
                "gdp_growth_qoq": response.get("gdp_growth_qoq", []),
                "gdp_growth_yoy": response.get("gdp_growth_yoy", []),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"Error getting ECB GDP: {e}")
            return {"gdp_growth_qoq": [], "gdp_growth_yoy": [], "metadata": {}}

    def _get_ecb_gdp_components(self, service) -> dict:
        """ECB GDP構成要素データを取得"""
        try:
            force_refresh = self._should_force_refresh("ecb_gdp_components")
            response = service.get_ecb_gdp_components_data(force_refresh=force_refresh)
            return {
                "components": response.get("components", {}),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"Error getting ECB GDP Components: {e}")
            return {"components": {}, "metadata": {}}

    def _get_ecb_bls(self, service) -> dict:
        """ECB BLSデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ecb_bls")
            response = service.get_ecb_bls_data(force_refresh=force_refresh)
            return {
                "enterprises": response.get("enterprises", []),
                "households": response.get("households", []),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"Error getting ECB BLS: {e}")
            return {"enterprises": [], "households": [], "metadata": {}}

    def _get_ecb_production(self, service) -> dict:
        """ECB鉱工業生産データを取得"""
        try:
            force_refresh = self._should_force_refresh("ecb_production")
            response = service.get_ecb_production_data(force_refresh=force_refresh)
            return {
                "production_wda": response.get("production_wda", []),
                "mom_change": response.get("mom_change", []),
                "yoy_change": response.get("yoy_change", []),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"Error getting ECB Production: {e}")
            return {"production_wda": [], "mom_change": [], "yoy_change": [], "metadata": {}}

    def _get_eurostat_esi(self, service) -> dict:
        """Eurostat ESIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("eurostat_esi")
            response = service.get_eurostat_esi_data(force_refresh=force_refresh)
            return {
                "euro_area": response.get("euro_area", []),
                "germany": response.get("germany", []),
                "france": response.get("france", []),
                "italy": response.get("italy", []),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Eurostat ESI: {e}")
            return {"euro_area": [], "germany": [], "france": [], "italy": [], "metadata": {}}

    def _get_euro_policy_uncertainty(self, service) -> dict:
        """欧州経済政策不確実性指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("euro_policy_uncertainty")
            response = service.get_euro_policy_uncertainty_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"Error getting Euro Policy Uncertainty: {e}")
            return {"data": [], "latest": None, "metadata": {}}

    def _get_eu_pmi(self, service) -> dict:
        """EU HCOB PMIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("eu_pmi")
            response = service.get_eu_pmi_data(force_refresh=force_refresh)
            return {
                "manufacturing": response.get("manufacturing"),
                "services": response.get("services"),
                "composite": response.get("composite"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting EU PMI: {e}")
            return {"manufacturing": None, "services": None, "composite": None, "next_release": None}
