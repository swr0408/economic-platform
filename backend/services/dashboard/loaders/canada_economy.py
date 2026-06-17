"""
カナダ経済ダッシュボードローダー
GDP成長率、月次GDPなどを一括取得

キャッシュ更新判定: FMP発表日時ベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader
from services.canada.fmp_next_release_utils import get_next_release_by_pattern


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
TORONTO = ZoneInfo("America/Toronto")

# FMP Event Patterns
FMP_PATTERN_GDP = "Gross Domestic Product"


class CanadaEconomyLoader(BaseDashboardLoader):
    """
    カナダ経済ダッシュボード用データローダー

    取得データ:
    - ca_gdp_growth: GDP成長率（四半期）
    - ca_gdp_monthly: 月次GDP

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "canada"
    CATEGORY_CODE = "economy"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "ca_gdp_growth",
        "ca_gdp_monthly",
        "ca_industrial_production",
        "ca_trade_balance",
        "ca_current_account",
        "ca_current_account_gdp_ratio",
        "ca_us_export_dependence",
        "ca_bos",
        "ca_csce",
        "ca_slos",
        "ca_ivey_pmi",
        "ca_sp_pmi",
    ]

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_expected_keys(self) -> List[str]:
        """期待されるデータキーのリストを返す"""
        return self.EXPECTED_KEYS


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
            print(f"[CanadaEconomy] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全経済データを並列で取得

        Returns:
            {
                "ca_gdp_growth": {...},
                "ca_gdp_monthly": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.canada.ca_gdp_growth_service import ca_gdp_growth_service
        from services.canada.ca_gdp_monthly_service import ca_gdp_monthly_service
        from services.canada.ca_industrial_production_service import ca_industrial_production_service
        from services.canada.ca_trade_balance_service import ca_trade_balance_service
        from services.canada.ca_current_account_service import ca_current_account_service
        from services.canada.ca_current_account_gdp_ratio_service import ca_current_account_gdp_ratio_service
        from services.canada.ca_us_export_dependence_service import ca_us_export_dependence_service
        from services.canada.ca_bos_service import ca_bos_service
        from services.canada.ca_csce_service import ca_csce_service
        from services.canada.ca_slos_service import ca_slos_service
        from services.canada.ca_ivey_pmi_service import ca_ivey_pmi_service
        from services.canada.ca_sp_pmi_service import ca_sp_pmi_service

        result = {
            "ca_gdp_growth": None,
            "ca_gdp_monthly": None,
            "ca_industrial_production": None,
            "ca_trade_balance": None,
            "ca_current_account": None,
            "ca_current_account_gdp_ratio": None,
            "ca_us_export_dependence": None,
            "ca_bos": None,
            "ca_csce": None,
            "ca_slos": None,
            "ca_ivey_pmi": None,
            "ca_sp_pmi": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=12) as executor:
            futures = {
                executor.submit(self._get_ca_gdp_growth, ca_gdp_growth_service): "ca_gdp_growth",
                executor.submit(self._get_ca_gdp_monthly, ca_gdp_monthly_service): "ca_gdp_monthly",
                executor.submit(self._get_ca_industrial_production, ca_industrial_production_service): "ca_industrial_production",
                executor.submit(self._get_ca_trade_balance, ca_trade_balance_service): "ca_trade_balance",
                executor.submit(self._get_ca_current_account, ca_current_account_service): "ca_current_account",
                executor.submit(self._get_ca_current_account_gdp_ratio, ca_current_account_gdp_ratio_service): "ca_current_account_gdp_ratio",
                executor.submit(self._get_ca_us_export_dependence, ca_us_export_dependence_service): "ca_us_export_dependence",
                executor.submit(self._get_ca_bos, ca_bos_service): "ca_bos",
                executor.submit(self._get_ca_csce, ca_csce_service): "ca_csce",
                executor.submit(self._get_ca_slos, ca_slos_service): "ca_slos",
                executor.submit(self._get_ca_ivey_pmi, ca_ivey_pmi_service): "ca_ivey_pmi",
                executor.submit(self._get_ca_sp_pmi, ca_sp_pmi_service): "ca_sp_pmi",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"[CanadaEconomy] Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_ca_gdp_growth(self, service) -> dict:
        """カナダGDP成長率データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_gdp_growth")
            response = service.get_ca_gdp_growth_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaEconomy] Error getting GDP Growth: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_gdp_monthly(self, service) -> dict:
        """カナダ月次GDPデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_gdp_monthly")
            response = service.get_ca_gdp_monthly_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "advance_estimate": response.get("advance_estimate"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaEconomy] Error getting Monthly GDP: {e}")
            return {"data": [], "latest": None, "advance_estimate": None, "metadata": {}, "next_release": None}

    def _get_ca_industrial_production(self, service) -> dict:
        """カナダ鉱工業生産データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_industrial_production")
            response = service.get_ca_industrial_production_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaEconomy] Error getting Industrial Production: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_trade_balance(self, service) -> dict:
        """カナダ貿易収支データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_trade_balance")
            response = service.get_ca_trade_balance_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaEconomy] Error getting Trade Balance: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_current_account(self, service) -> dict:
        """カナダ経常収支データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_current_account")
            response = service.get_ca_current_account_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaEconomy] Error getting Current Account: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_current_account_gdp_ratio(self, service) -> dict:
        """カナダ経常収支対GDP比データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_current_account_gdp_ratio")
            response = service.get_ca_current_account_gdp_ratio_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaEconomy] Error getting Current Account to GDP Ratio: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_us_export_dependence(self, service) -> dict:
        """カナダ対米輸出依存度データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_us_export_dependence")
            response = service.get_ca_us_export_dependence_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaEconomy] Error getting US Export Dependence: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_bos(self, service) -> dict:
        """カナダBOSデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_bos")
            response = service.get_ca_bos_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaEconomy] Error getting BOS: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_csce(self, service) -> dict:
        """カナダCSCEデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_csce")
            response = service.get_ca_csce_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaEconomy] Error getting CSCE: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_slos(self, service) -> dict:
        """カナダSLOSデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_slos")
            response = service.get_ca_slos_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaEconomy] Error getting SLOS: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_ivey_pmi(self, service) -> dict:
        """カナダ Ivey PMI データを取得"""
        try:
            force_refresh = self._should_force_refresh("ca_ivey_pmi")
            response = service.get_ca_ivey_pmi_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[CanadaEconomy] Error getting Ivey PMI: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_ca_sp_pmi(self, service) -> Optional[dict]:
        """カナダ S&P Global PMI データを取得（製造業/サービス業/総合）"""
        try:
            force_refresh = self._should_force_refresh("ca_sp_pmi")
            response = service.get_ca_sp_pmi_data(force_refresh=force_refresh)

            mfg = response.get("manufacturing")
            svc = response.get("services")
            cmp = response.get("composite")

            if not (mfg or svc or cmp):
                return None

            return {
                "manufacturing": mfg,
                "services": svc,
                "composite": cmp,
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated"),
            }
        except Exception as e:
            print(f"[CanadaEconomy] Error getting S&P PMI: {e}")
            return None
