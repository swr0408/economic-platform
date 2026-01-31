"""
UK金融政策ダッシュボードローダー
BOE政策金利などを一括取得

キャッシュ更新判定: 週次更新 + MPC発表日付近は頻繁更新
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader
from services.uk.fmp_next_release_utils import get_next_release_by_pattern


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# FMP Event Patterns
FMP_PATTERN_MPR = "BoE Monetary Policy Report"
FMP_PATTERN_PSNB = "Public Sector Net Borrowing"


class UKPolicyLoader(BaseDashboardLoader):
    """
    UK金融政策ダッシュボード用データローダー

    取得データ（基本仕様・常設）:
    - boe_bank_rate: BOE政策金利（Bank Rate）
    - boe_mpc_voting: BOE MPC投票履歴
    - boe_ois_curve: BOE OISフォワードカーブ
    - boe_market_expectations: 政策金利 見通し（Bank Rate前提パス）
    - boe_cpi_projections: CPI（総合）見通し
    - boe_gdp_forecast: GDP成長率 見通し
    - boe_unemployment_forecast: 失業率 見通し
    - boe_services_inflation: サービスインフレ（基調/粘着性）
    - boe_wage_growth: 賃金（足元トラッカー）
    - boe_average_weekly_earnings: 平均週間賃金（AWE）見通し
    - boe_unit_wage_costs: 単位賃金コスト（UWC）見通し
    - boe_inflation_expectations: インフレ期待（家計/企業）
    - boe_dmp_survey: DMP（意思決定者パネル）サーベイ
    - uk_public_sector_net_borrowing: 公的部門純借入（銀行除く）

    ※ CPI構成項目（boe_cpi_components）は2025年11月以降の拡張データのため除外
    ※ CPI寄与度（boe_cpi_contributions）は分解粒度が号で変わりやすいため除外

    キャッシュ方式: 週次更新 + MPC発表日付近は頻繁更新
    """

    COUNTRY_CODE = "uk"
    CATEGORY_CODE = "policy"

    # 期待されるデータキー（基本仕様・常設のみ）
    EXPECTED_KEYS = [
        "boe_bank_rate",
        "boe_mpc_voting",
        "boe_ois_curve",
        "boe_market_expectations",
        "boe_cpi_projections",
        "boe_gdp_forecast",
        "boe_unemployment_forecast",
        "boe_services_inflation",
        "boe_wage_growth",
        "boe_average_weekly_earnings",
        "boe_unit_wage_costs",
        "boe_inflation_expectations",
        "boe_dmp_survey",
        "uk_public_sector_net_borrowing",
    ]

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_expected_keys(self) -> List[str]:
        """期待されるデータキーのリストを返す"""
        return self.EXPECTED_KEYS

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
        全金融政策データを並列で取得

        Returns:
            {
                "boe_bank_rate": {...},
                "boe_mpc_voting": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.uk.boe_bank_rate_service import boe_bank_rate_service
        from services.uk.boe_mpc_voting_service import boe_mpc_voting_service
        from services.uk.boe_ois_curve_service import boe_ois_curve_service
        from services.uk.boe_market_expectations_service import boe_market_expectations_service
        from services.uk.boe_cpi_projections_service import boe_cpi_projections_service
        from services.uk.boe_gdp_forecast_service import boe_gdp_forecast_service
        from services.uk.boe_unemployment_forecast_service import boe_unemployment_forecast_service
        from services.uk.boe_services_inflation_service import boe_services_inflation_service
        from services.uk.boe_wage_growth_service import boe_wage_growth_service
        from services.uk.boe_average_weekly_earnings_service import boe_average_weekly_earnings_service
        from services.uk.boe_unit_wage_costs_service import boe_unit_wage_costs_service
        from services.uk.boe_inflation_expectations_service import boe_inflation_expectations_service
        from services.uk.boe_dmp_survey_service import boe_dmp_survey_service
        from services.uk.ons_public_sector_net_borrowing_service import ons_public_sector_net_borrowing_service

        result = {
            "boe_bank_rate": None,
            "boe_mpc_voting": None,
            "boe_ois_curve": None,
            "boe_market_expectations": None,
            "boe_cpi_projections": None,
            "boe_gdp_forecast": None,
            "boe_unemployment_forecast": None,
            "boe_services_inflation": None,
            "boe_wage_growth": None,
            "boe_average_weekly_earnings": None,
            "boe_unit_wage_costs": None,
            "boe_inflation_expectations": None,
            "boe_dmp_survey": None,
            "uk_public_sector_net_borrowing": None,
        }

        # 並列でデータを取得（基本仕様・常設のみ）
        with ThreadPoolExecutor(max_workers=14) as executor:
            futures = {
                executor.submit(self._get_boe_bank_rate, boe_bank_rate_service): "boe_bank_rate",
                executor.submit(self._get_boe_mpc_voting, boe_mpc_voting_service): "boe_mpc_voting",
                executor.submit(self._get_boe_ois_curve, boe_ois_curve_service): "boe_ois_curve",
                executor.submit(self._get_boe_market_expectations, boe_market_expectations_service): "boe_market_expectations",
                executor.submit(self._get_boe_cpi_projections, boe_cpi_projections_service): "boe_cpi_projections",
                executor.submit(self._get_boe_gdp_forecast, boe_gdp_forecast_service): "boe_gdp_forecast",
                executor.submit(self._get_boe_unemployment_forecast, boe_unemployment_forecast_service): "boe_unemployment_forecast",
                executor.submit(self._get_boe_services_inflation, boe_services_inflation_service): "boe_services_inflation",
                executor.submit(self._get_boe_wage_growth, boe_wage_growth_service): "boe_wage_growth",
                executor.submit(self._get_boe_average_weekly_earnings, boe_average_weekly_earnings_service): "boe_average_weekly_earnings",
                executor.submit(self._get_boe_unit_wage_costs, boe_unit_wage_costs_service): "boe_unit_wage_costs",
                executor.submit(self._get_boe_inflation_expectations, boe_inflation_expectations_service): "boe_inflation_expectations",
                executor.submit(self._get_boe_dmp_survey, boe_dmp_survey_service): "boe_dmp_survey",
                executor.submit(self._get_uk_public_sector_net_borrowing, ons_public_sector_net_borrowing_service): "uk_public_sector_net_borrowing",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_boe_bank_rate(self, service) -> dict:
        """BOE Bank Rateデータを取得"""
        try:
            force_refresh = self._should_force_refresh("boe_bank_rate")
            response = service.get_boe_bank_rate_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting BOE Bank Rate: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_boe_mpc_voting(self, service) -> dict:
        """BOE MPC投票データを取得"""
        try:
            force_refresh = self._should_force_refresh("boe_mpc_voting")
            response = service.get_table_data(limit=50)
            return {
                "data": response.get("data", []),
                "members": response.get("members", []),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting BOE MPC Voting: {e}")
            return {"data": [], "members": [], "next_release": None}

    def _get_boe_ois_curve(self, service) -> dict:
        """BOE OISカーブデータを取得"""
        try:
            force_refresh = self._should_force_refresh("boe_ois_curve")
            response = service.get_chart_data()
            return {
                "current": response.get("current"),
                "previous": response.get("previous"),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"Error getting BOE OIS Curve: {e}")
            return {"current": None, "previous": None, "metadata": {}}

    def _get_boe_market_expectations(self, service) -> dict:
        """BOE Market Expectationsデータを取得"""
        try:
            force_refresh = self._should_force_refresh("boe_market_expectations")
            response = service.get_market_expectations(force_refresh=force_refresh)
            forecasts = response.get("forecasts", {})
            return {
                "latest": forecasts.get("latest_forecast"),
                "previous": forecasts.get("previous_forecast"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting BOE Market Expectations: {e}")
            return {"latest": None, "previous": None, "metadata": {}, "next_release": None}

    def _get_boe_cpi_projections(self, service) -> dict:
        """BOE CPI Projectionsデータを取得"""
        try:
            force_refresh = self._should_force_refresh("boe_cpi_projections")
            response = service.get_cpi_projections(force_refresh=force_refresh)
            # FMPから次回発表日時を取得
            next_release = get_next_release_by_pattern(FMP_PATTERN_MPR)
            # サービスがtable_data形式で直接返すようになった
            return {
                "table_data": response.get("table_data", []),
                "chart_data": response.get("chart_data"),
                "metadata": response.get("metadata", {}),
                "next_release": next_release,
            }
        except Exception as e:
            print(f"Error getting BOE CPI Projections: {e}")
            return {"table_data": [], "chart_data": None, "metadata": {}, "next_release": None}

    def _get_boe_gdp_forecast(self, service) -> dict:
        """BOE GDP Forecastデータを取得"""
        try:
            force_refresh = self._should_force_refresh("boe_gdp_forecast")
            response = service.fetch_data(force_refresh=force_refresh)
            # FMPから次回発表日時を取得
            next_release = get_next_release_by_pattern(FMP_PATTERN_MPR)
            return {
                "table_data": response.get("table_data", []),
                "chart_data": response.get("chart_data"),
                "metadata": response.get("metadata", {}),
                "next_release": next_release,
            }
        except Exception as e:
            print(f"Error getting BOE GDP Forecast: {e}")
            return {"table_data": [], "chart_data": None, "metadata": {}, "next_release": None}

    def _get_boe_unemployment_forecast(self, service) -> dict:
        """BOE Unemployment Forecastデータを取得"""
        try:
            force_refresh = self._should_force_refresh("boe_unemployment_forecast")
            response = service.fetch_data(force_refresh=force_refresh)
            # FMPから次回発表日時を取得
            next_release = get_next_release_by_pattern(FMP_PATTERN_MPR)
            return {
                "table_data": response.get("table_data", []),
                "chart_data": response.get("chart_data"),
                "metadata": response.get("metadata", {}),
                "next_release": next_release,
            }
        except Exception as e:
            print(f"Error getting BOE Unemployment Forecast: {e}")
            return {"table_data": [], "chart_data": None, "metadata": {}, "next_release": None}

    def _get_boe_services_inflation(self, service) -> dict:
        """BOE Services Inflationデータを取得"""
        try:
            force_refresh = self._should_force_refresh("boe_services_inflation")
            response = service.fetch_data(force_refresh=force_refresh)
            # FMPから次回発表日時を取得
            next_release = get_next_release_by_pattern(FMP_PATTERN_MPR)
            return {
                "services_inflation": response.get("services_inflation", {}),
                "metadata": response.get("metadata", {}),
                "next_release": next_release,
            }
        except Exception as e:
            print(f"Error getting BOE Services Inflation: {e}")
            return {"services_inflation": {}, "metadata": {}, "next_release": None}

    def _get_boe_wage_growth(self, service) -> dict:
        """BOE Wage Growthデータを取得"""
        try:
            force_refresh = self._should_force_refresh("boe_wage_growth")
            response = service.fetch_data(force_refresh=force_refresh)
            # FMPから次回発表日時を取得
            next_release = get_next_release_by_pattern(FMP_PATTERN_MPR)
            return {
                "wage_growth": response.get("wage_growth", {}),
                "metadata": response.get("metadata", {}),
                "next_release": next_release,
            }
        except Exception as e:
            print(f"Error getting BOE Wage Growth: {e}")
            return {"wage_growth": {}, "metadata": {}, "next_release": None}

    def _get_boe_average_weekly_earnings(self, service) -> dict:
        """BOE Average Weekly Earningsデータを取得"""
        try:
            force_refresh = self._should_force_refresh("boe_average_weekly_earnings")
            response = service.fetch_data(force_refresh=force_refresh)
            # FMPから次回発表日時を取得
            next_release = get_next_release_by_pattern(FMP_PATTERN_MPR)
            return {
                "average_weekly_earnings": response.get("average_weekly_earnings", {}),
                "metadata": response.get("metadata", {}),
                "next_release": next_release,
            }
        except Exception as e:
            print(f"Error getting BOE Average Weekly Earnings: {e}")
            return {"average_weekly_earnings": {}, "metadata": {}, "next_release": None}

    def _get_boe_unit_wage_costs(self, service) -> dict:
        """BOE Unit Wage Costsデータを取得"""
        try:
            force_refresh = self._should_force_refresh("boe_unit_wage_costs")
            response = service.fetch_data(force_refresh=force_refresh)
            # FMPから次回発表日時を取得
            next_release = get_next_release_by_pattern(FMP_PATTERN_MPR)
            return {
                "unit_wage_costs": response.get("unit_wage_costs", {}),
                "metadata": response.get("metadata", {}),
                "next_release": next_release,
            }
        except Exception as e:
            print(f"Error getting BOE Unit Wage Costs: {e}")
            return {"unit_wage_costs": {}, "metadata": {}, "next_release": None}

    def _get_boe_inflation_expectations(self, service) -> dict:
        """BOE Inflation Expectationsデータを取得"""
        try:
            force_refresh = self._should_force_refresh("boe_inflation_expectations")
            response = service.fetch_data(force_refresh=force_refresh)
            # FMPから次回発表日時を取得
            next_release = get_next_release_by_pattern(FMP_PATTERN_MPR)
            return {
                "inflation_expectations": response.get("inflation_expectations", {}),
                "metadata": response.get("metadata", {}),
                "next_release": next_release,
            }
        except Exception as e:
            print(f"Error getting BOE Inflation Expectations: {e}")
            return {"inflation_expectations": {}, "metadata": {}, "next_release": None}

    def _get_boe_dmp_survey(self, service) -> dict:
        """BOE DMP Surveyデータを取得"""
        try:
            force_refresh = self._should_force_refresh("boe_dmp_survey")
            response = service.fetch_data(force_refresh=force_refresh)
            return {
                "survey_data": response.get("survey_data", {}),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"Error getting BOE DMP Survey: {e}")
            return {"survey_data": {}, "metadata": {}}

    def _get_uk_public_sector_net_borrowing(self, service) -> dict:
        """UK公的部門純借入データを取得"""
        try:
            force_refresh = self._should_force_refresh("uk_public_sector_net_borrowing")
            response = service.get_data(force_refresh=force_refresh)
            # FMPから次回発表日時を取得
            next_release = get_next_release_by_pattern(FMP_PATTERN_PSNB)
            return {
                "psnb_ex": response.get("psnb_ex", []),
                "cgnb": response.get("cgnb", []),
                "psnd_ex": response.get("psnd_ex", []),
                "psnd_gdp": response.get("psnd_gdp", []),
                "latest_psnb_ex": response.get("latest_psnb_ex"),
                "latest_cgnb": response.get("latest_cgnb"),
                "latest_psnd_ex": response.get("latest_psnd_ex"),
                "latest_psnd_gdp": response.get("latest_psnd_gdp"),
                "metadata": response.get("metadata", {}),
                "next_release": next_release,
            }
        except Exception as e:
            print(f"Error getting UK Public Sector Net Borrowing: {e}")
            return {
                "psnb_ex": [],
                "cgnb": [],
                "psnd_ex": [],
                "psnd_gdp": [],
                "latest_psnb_ex": None,
                "latest_cgnb": None,
                "latest_psnd_ex": None,
                "latest_psnd_gdp": None,
                "metadata": {},
                "next_release": None,
            }
