"""
ユーロ圏経済ダッシュボードローダー
ECB GDP、GDP構成要素、銀行貸出調査、鉱工業生産、ESI、政策不確実性指数、PMI、ドイツGDP成長率、ドイツ鉱工業生産、ドイツ製造業新規受注、ZEW景況感、フランスPMI、経常収支などの経済指標を一括取得

キャッシュ更新判定: 日次更新方式
- ECB GDP: 毎日18:00 CET更新
- ECB GDP Components: 毎日18:00 CET更新
- ECB BLS: 毎日18:00 CET更新
- ECB Production: 毎日18:00 CET更新
- Eurostat ESI: FMP発表日時ベース更新
- Euro Policy Uncertainty: 24時間TTL更新
- EU PMI: FMP発表日時ベース更新
- Germany GDP Growth: FMP発表日時ベース更新
- Germany Industrial Production: FMP発表日時ベース更新
- Germany Factory Orders: FMP発表日時ベース更新
- ZEW Economic Sentiment: FMP発表日時ベース更新
- Germany PMI: FMP発表日時ベース更新
- France PMI: FMP発表日時ベース更新
- EU Terms of Trade: FMP発表日時ベース更新（EU国際貿易と同時発表）
- ECB Current Account: FMP発表日時ベース更新
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
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
    - germany_gdp_growth: ドイツGDP成長率（前期比・前年比）
    - germany_industrial_production: ドイツ鉱工業生産（前月比・前年比）
    - germany_factory_orders: ドイツ製造業新規受注（前月比・前年比）
    - zew_economic_sentiment: ZEW景況感指数（景況感・現況）
    - germany_pmi: ドイツS&P Global PMI（製造業・サービス業・総合）
    - france_pmi: フランスHCOB PMI（製造業・サービス業・総合）

    キャッシュ方式: 日次更新
    - ECB GDP: 毎日18:00 CET更新
    - ECB GDP Components: 毎日18:00 CET更新
    - ECB BLS: 毎日18:00 CET更新
    - ECB Production: 毎日18:00 CET更新
    - Eurostat ESI: FMP発表日時ベース更新
    - Euro Policy Uncertainty: 24時間TTL更新
    - EU PMI: FMP発表日時ベース更新
    - Germany GDP Growth: FMP発表日時ベース更新
    - Germany Industrial Production: FMP発表日時ベース更新
    - Germany Factory Orders: FMP発表日時ベース更新
    - ZEW Economic Sentiment: FMP発表日時ベース更新
    - Germany PMI: FMP発表日時ベース更新
    - France PMI: FMP発表日時ベース更新
    """

    COUNTRY_CODE = "eurozone"
    CATEGORY_CODE = "economy"

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()


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
            return {"all"}

        return set()

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
        from services.eurozone.germany_gdp_growth_service import germany_gdp_growth_service
        from services.eurozone.germany_industrial_production_service import germany_industrial_production_service
        from services.eurozone.germany_factory_orders_service import germany_factory_orders_service
        from services.eurozone.zew_economic_sentiment_service import zew_economic_sentiment_service
        from services.eurozone.ifo_business_climate_service import ifo_business_climate_service
        from services.eurozone.germany_pmi_service import germany_pmi_service
        from services.eurozone.france_pmi_service import france_pmi_service
        from services.eurozone.ecb_adjusted_loans_service import ecb_adjusted_loans_service
        from services.eurozone.ecb_ciss_service import ecb_ciss_service
        from services.eurozone.eu_international_trade_service import eu_international_trade_service
        from services.eurozone.eu_terms_of_trade_service import eu_terms_of_trade_service
        from services.eurozone.ecb_current_account_service import ecb_current_account_service
        from services.eurozone.france_business_confidence_service import france_business_confidence_service
        from services.eurozone.eu_government_debt_to_gdp_ratio_service import eu_government_debt_to_gdp_ratio_service

        result = {
            "ecb_gdp": None,
            "ecb_gdp_components": None,
            "ecb_bls": None,
            "ecb_production": None,
            "eurostat_esi": None,
            "euro_policy_uncertainty": None,
            "eu_pmi": None,
            "germany_gdp_growth": None,
            "germany_industrial_production": None,
            "germany_factory_orders": None,
            "zew_economic_sentiment": None,
            "ifo_business_climate": None,
            "germany_pmi": None,
            "france_pmi": None,
            "ecb_adjusted_loans": None,
            "ecb_ciss": None,
            "eu_international_trade": None,
            "eu_terms_of_trade": None,
            "ecb_current_account": None,
            "france_business_confidence": None,
            "eu_government_debt_to_gdp_ratio": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = {
                executor.submit(self._get_ecb_gdp, ecb_gdp_service): "ecb_gdp",
                executor.submit(self._get_ecb_gdp_components, ecb_gdp_components_service): "ecb_gdp_components",
                executor.submit(self._get_ecb_bls, ecb_bls_service): "ecb_bls",
                executor.submit(self._get_ecb_production, ecb_production_service): "ecb_production",
                executor.submit(self._get_eurostat_esi, eurostat_esi_service): "eurostat_esi",
                executor.submit(self._get_euro_policy_uncertainty, euro_policy_uncertainty_service): "euro_policy_uncertainty",
                executor.submit(self._get_eu_pmi, eu_pmi_service): "eu_pmi",
                executor.submit(self._get_germany_gdp_growth, germany_gdp_growth_service): "germany_gdp_growth",
                executor.submit(self._get_germany_industrial_production, germany_industrial_production_service): "germany_industrial_production",
                executor.submit(self._get_germany_factory_orders, germany_factory_orders_service): "germany_factory_orders",
                executor.submit(self._get_zew_economic_sentiment, zew_economic_sentiment_service): "zew_economic_sentiment",
                executor.submit(self._get_ifo_business_climate, ifo_business_climate_service): "ifo_business_climate",
                executor.submit(self._get_germany_pmi, germany_pmi_service): "germany_pmi",
                executor.submit(self._get_france_pmi, france_pmi_service): "france_pmi",
                executor.submit(self._get_ecb_adjusted_loans, ecb_adjusted_loans_service): "ecb_adjusted_loans",
                executor.submit(self._get_ecb_ciss, ecb_ciss_service): "ecb_ciss",
                executor.submit(self._get_eu_international_trade, eu_international_trade_service): "eu_international_trade",
                executor.submit(self._get_eu_terms_of_trade, eu_terms_of_trade_service): "eu_terms_of_trade",
                executor.submit(self._get_ecb_current_account, ecb_current_account_service): "ecb_current_account",
                executor.submit(self._get_france_business_confidence, france_business_confidence_service): "france_business_confidence",
                executor.submit(self._get_eu_government_debt_to_gdp_ratio, eu_government_debt_to_gdp_ratio_service): "eu_government_debt_to_gdp_ratio",
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
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ECB GDP: {e}")
            return {"gdp_growth_qoq": [], "gdp_growth_yoy": [], "metadata": {}, "next_release": None}

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
        """ECB BLSデータを取得（企業向け・消費者信用・住宅購入向け）"""
        try:
            force_refresh = self._should_force_refresh("ecb_bls")
            response = service.get_ecb_bls_data(force_refresh=force_refresh)
            return {
                "enterprises_current": response.get("enterprises_current", []),
                "enterprises_expected": response.get("enterprises_expected", []),
                "consumer_current": response.get("consumer_current", []),
                "consumer_expected": response.get("consumer_expected", []),
                "housing_current": response.get("housing_current", []),
                "housing_expected": response.get("housing_expected", []),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ECB BLS: {e}")
            return {
                "enterprises_current": [],
                "enterprises_expected": [],
                "consumer_current": [],
                "consumer_expected": [],
                "housing_current": [],
                "housing_expected": [],
                "metadata": {},
                "next_release": None
            }

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
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ECB Production: {e}")
            return {"production_wda": [], "mom_change": [], "yoy_change": [], "metadata": {}, "next_release": None}

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

    def _get_germany_gdp_growth(self, service) -> dict:
        """ドイツGDP成長率データを取得"""
        try:
            force_refresh = self._should_force_refresh("germany_gdp_growth")
            response = service.get_germany_gdp_growth_data(force_refresh=force_refresh)
            return {
                "gdp_growth_qoq": response.get("gdp_growth_qoq", []),
                "gdp_growth_yoy": response.get("gdp_growth_yoy", []),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Germany GDP Growth: {e}")
            return {"gdp_growth_qoq": [], "gdp_growth_yoy": [], "metadata": {}, "next_release": None}

    def _get_germany_industrial_production(self, service) -> dict:
        """ドイツ鉱工業生産データを取得"""
        try:
            force_refresh = self._should_force_refresh("germany_industrial_production")
            response = service.get_germany_industrial_production_data(force_refresh=force_refresh)
            return {
                "mom": response.get("mom", []),
                "yoy": response.get("yoy", []),
                "latest_mom": response.get("latest_mom"),
                "latest_yoy": response.get("latest_yoy"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Germany Industrial Production: {e}")
            return {"mom": [], "yoy": [], "latest_mom": None, "latest_yoy": None, "next_release": None}

    def _get_germany_factory_orders(self, service) -> dict:
        """ドイツ製造業新規受注データを取得"""
        try:
            force_refresh = self._should_force_refresh("germany_factory_orders")
            response = service.get_germany_factory_orders_data(force_refresh=force_refresh)
            return {
                "mom": response.get("mom", []),
                "yoy": response.get("yoy", []),
                "domestic_mom": response.get("domestic_mom", []),
                "domestic_yoy": response.get("domestic_yoy", []),
                "foreign_mom": response.get("foreign_mom", []),
                "foreign_yoy": response.get("foreign_yoy", []),
                "index_total": response.get("index_total", []),
                "index_domestic": response.get("index_domestic", []),
                "index_foreign": response.get("index_foreign", []),
                "latest_mom": response.get("latest_mom"),
                "latest_yoy": response.get("latest_yoy"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Germany Factory Orders: {e}")
            return {
                "mom": [], "yoy": [],
                "domestic_mom": [], "domestic_yoy": [],
                "foreign_mom": [], "foreign_yoy": [],
                "index_total": [], "index_domestic": [], "index_foreign": [],
                "latest_mom": None, "latest_yoy": None, "next_release": None
            }

    def _get_zew_economic_sentiment(self, service) -> dict:
        """ZEW景況感指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("zew_economic_sentiment")
            response = service.get_zew_economic_sentiment_data(force_refresh=force_refresh)
            return {
                "sentiment": response.get("sentiment", []),
                "situation": response.get("situation", []),
                "latest_sentiment": response.get("latest_sentiment"),
                "latest_situation": response.get("latest_situation"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ZEW Economic Sentiment: {e}")
            return {
                "sentiment": [], "situation": [],
                "latest_sentiment": None, "latest_situation": None,
                "next_release": None
            }

    def _get_ifo_business_climate(self, service) -> dict:
        """IFO企業景況感指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("ifo_business_climate")
            response = service.get_ifo_business_climate_data(force_refresh=force_refresh)
            return {
                "climate": response.get("climate", []),
                "current": response.get("current", []),
                "expectations": response.get("expectations", []),
                "latest_climate": response.get("latest_climate"),
                "latest_current": response.get("latest_current"),
                "latest_expectations": response.get("latest_expectations"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting IFO Business Climate: {e}")
            return {
                "climate": [], "current": [], "expectations": [],
                "latest_climate": None, "latest_current": None, "latest_expectations": None,
                "next_release": None
            }

    def _get_germany_pmi(self, service) -> dict:
        """ドイツS&P Global PMIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("germany_pmi")
            response = service.get_germany_pmi_data(force_refresh=force_refresh)
            return {
                "manufacturing": response.get("manufacturing"),
                "services": response.get("services"),
                "composite": response.get("composite"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Germany PMI: {e}")
            return {"manufacturing": None, "services": None, "composite": None, "next_release": None}

    def _get_france_pmi(self, service) -> dict:
        """フランスHCOB PMIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("france_pmi")
            response = service.get_france_pmi_data(force_refresh=force_refresh)
            return {
                "manufacturing": response.get("manufacturing"),
                "services": response.get("services"),
                "composite": response.get("composite"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting France PMI: {e}")
            return {"manufacturing": None, "services": None, "composite": None, "next_release": None}

    def _get_ecb_adjusted_loans(self, service) -> dict:
        """ECB調整済貸出データを取得（NFC・家計・住宅向け）"""
        try:
            force_refresh = self._should_force_refresh("ecb_adjusted_loans")
            response = service.get_adjusted_loans_data(force_refresh=force_refresh)
            return {
                "nfc": response.get("nfc", {}),
                "households": response.get("households", {}),
                "housing": response.get("housing", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ECB Adjusted Loans: {e}")
            return {
                "nfc": {"data": [], "latest": None},
                "households": {"data": [], "latest": None},
                "housing": {"data": [], "latest": None},
                "next_release": None
            }

    def _get_ecb_ciss(self, service) -> dict:
        """ECB CISSデータを取得（システミックストレス総合指標）"""
        try:
            force_refresh = self._should_force_refresh("ecb_ciss")
            response = service.get_ciss_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ECB CISS: {e}")
            return {"data": [], "latest": None, "next_release": None}

    def _get_eu_international_trade(self, service) -> dict:
        """EU国際貿易データを取得（貿易収支・輸出・輸入 + 前月比・前年比・増減幅）"""
        try:
            force_refresh = self._should_force_refresh("eu_international_trade")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "balance": response.get("balance", []),
                "exports": response.get("exports", []),
                "imports": response.get("imports", []),
                "balance_mom": response.get("balance_mom", []),
                "balance_mom_diff": response.get("balance_mom_diff", []),
                "balance_yoy": response.get("balance_yoy", []),
                "exports_mom": response.get("exports_mom", []),
                "exports_yoy": response.get("exports_yoy", []),
                "imports_mom": response.get("imports_mom", []),
                "imports_yoy": response.get("imports_yoy", []),
                "latest_balance": response.get("latest_balance"),
                "latest_exports": response.get("latest_exports"),
                "latest_imports": response.get("latest_imports"),
                "latest_balance_mom": response.get("latest_balance_mom"),
                "latest_balance_mom_diff": response.get("latest_balance_mom_diff"),
                "latest_balance_yoy": response.get("latest_balance_yoy"),
                "latest_exports_mom": response.get("latest_exports_mom"),
                "latest_exports_yoy": response.get("latest_exports_yoy"),
                "latest_imports_mom": response.get("latest_imports_mom"),
                "latest_imports_yoy": response.get("latest_imports_yoy"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting EU International Trade: {e}")
            return {
                "balance": [], "exports": [], "imports": [],
                "balance_mom": [], "balance_mom_diff": [], "balance_yoy": [],
                "exports_mom": [], "exports_yoy": [],
                "imports_mom": [], "imports_yoy": [],
                "latest_balance": None, "latest_exports": None, "latest_imports": None,
                "latest_balance_mom": None, "latest_balance_mom_diff": None, "latest_balance_yoy": None,
                "latest_exports_mom": None, "latest_exports_yoy": None,
                "latest_imports_mom": None, "latest_imports_yoy": None,
                "metadata": {}, "next_release": None
            }

    def _get_eu_terms_of_trade(self, service) -> dict:
        """EU交易条件データを取得（輸出単価指数/輸入単価指数）"""
        try:
            force_refresh = self._should_force_refresh("eu_terms_of_trade")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "terms_of_trade": response.get("terms_of_trade", []),
                "export_uv": response.get("export_uv", []),
                "import_uv": response.get("import_uv", []),
                "latest_tot": response.get("latest_tot"),
                "latest_export_uv": response.get("latest_export_uv"),
                "latest_import_uv": response.get("latest_import_uv"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting EU Terms of Trade: {e}")
            return {
                "terms_of_trade": [], "export_uv": [], "import_uv": [],
                "latest_tot": None, "latest_export_uv": None, "latest_import_uv": None,
                "metadata": {}, "next_release": None
            }

    def _get_ecb_current_account(self, service) -> dict:
        """ECB経常収支データを取得"""
        try:
            force_refresh = self._should_force_refresh("ecb_current_account")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ECB Current Account: {e}")
            return {
                "data": [],
                "latest": None,
                "metadata": {},
                "next_release": None
            }

    def _get_france_business_confidence(self, service) -> dict:
        """フランス企業信頼感データを取得"""
        try:
            force_refresh = self._should_force_refresh("france_business_confidence")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting France Business Confidence: {e}")
            return {
                "data": [],
                "latest": None,
                "metadata": {},
                "next_release": None
            }

    def _get_eu_government_debt_to_gdp_ratio(self, service) -> dict:
        """EU政府債務残高対GDP比データを取得"""
        try:
            force_refresh = self._should_force_refresh("eu_government_debt_to_gdp_ratio")
            response = service.get_data(force_refresh=force_refresh)
            return {
                "countries": response.get("countries", {}),
                "ea20": response.get("ea20", []),
                "qoq_change": response.get("qoq_change", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting EU Government Debt to GDP Ratio: {e}")
            return {
                "countries": {},
                "ea20": [],
                "qoq_change": [],
                "latest": None,
                "metadata": {},
                "next_release": None,
            }
