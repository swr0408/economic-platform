"""
中国金融政策ダッシュボードローダー
LPR（ローンプライムレート）を一括取得

キャッシュ更新判定: FMP発表日時ベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CST = ZoneInfo("Asia/Shanghai")


class ChinaPolicyLoader(BaseDashboardLoader):
    """
    中国金融政策ダッシュボード用データローダー

    取得データ:
    - cn_lpr_1y: ローンプライムレート（1年）
    - cn_lpr_5y: ローンプライムレート（5年）

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "china"
    CATEGORY_CODE = "policy"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "cn_lpr_1y",
        "cn_lpr_5y",
        "ch_reverse_repo_rate",
        "china_reserve_requirement_ratio_for_large_banks",
        "ch_central_bank_balance_sheet",
        "ch_m1_m2",
        "cn_aggregate_financing_to_the_real_economy",
        "cn_new_rmb_loans",
        "cn_foreign_exchange_reserves",
        "cn_local_bonds",
        "cn_overseas_investor_flow",
        "cn_capital_flows",
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
            return {"all"}

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
            print(f"[ChinaPolicy] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全金融政策データを取得

        Returns:
            {
                "cn_lpr_1y": {...},
                "cn_lpr_5y": {...},
                "ch_reverse_repo_rate": {...},
            }
        """
        from services.china.cn_lpr_service import cn_lpr_service
        from services.china.ch_reverse_repo_rate_service import ch_reverse_repo_rate_service
        from services.china.ch_rrr_service import ch_rrr_service
        from services.china.ch_central_bank_balance_sheet_service import ch_central_bank_balance_sheet_service
        from services.china.ch_m1_m2_service import ch_m1_m2_service
        from services.china.cn_aggregate_financing_service import cn_aggregate_financing_service
        from services.china.cn_new_rmb_loans_service import cn_new_rmb_loans_service
        from services.china.cn_foreign_exchange_reserves_service import cn_foreign_exchange_reserves_service
        from services.china.cn_local_bonds_service import cn_local_bonds_service
        from services.china.cn_overseas_investor_flow_service import cn_overseas_investor_flow_service
        from services.china.cn_capital_flows_service import cn_capital_flows_service

        result = {
            "cn_lpr_1y": None,
            "cn_lpr_5y": None,
            "ch_reverse_repo_rate": None,
            "china_reserve_requirement_ratio_for_large_banks": None,
            "ch_central_bank_balance_sheet": None,
            "ch_m1_m2": None,
            "cn_aggregate_financing_to_the_real_economy": None,
            "cn_new_rmb_loans": None,
            "cn_foreign_exchange_reserves": None,
            "cn_local_bonds": None,
            "cn_overseas_investor_flow": None,
            "cn_capital_flows": None,
        }

        result["cn_lpr_1y"] = self._get_lpr_indicator(
            cn_lpr_service, "1y", "LPR 1Y"
        )
        result["cn_lpr_5y"] = self._get_lpr_indicator(
            cn_lpr_service, "5y", "LPR 5Y"
        )
        result["ch_reverse_repo_rate"] = self._get_generic_indicator(
            ch_reverse_repo_rate_service, "ch_reverse_repo_rate", "Reverse Repo Rate"
        )
        result["china_reserve_requirement_ratio_for_large_banks"] = self._get_generic_indicator(
            ch_rrr_service, "china_reserve_requirement_ratio_for_large_banks", "RRR Large Banks"
        )
        result["ch_central_bank_balance_sheet"] = self._get_generic_indicator(
            ch_central_bank_balance_sheet_service, "ch_central_bank_balance_sheet", "Central Bank Balance Sheet"
        )
        result["ch_m1_m2"] = self._get_generic_indicator(
            ch_m1_m2_service, "ch_m1_m2", "M1/M2 Money Supply"
        )
        result["cn_aggregate_financing_to_the_real_economy"] = self._get_generic_indicator(
            cn_aggregate_financing_service, "cn_aggregate_financing_to_the_real_economy", "Aggregate Financing"
        )
        result["cn_new_rmb_loans"] = self._get_generic_indicator(
            cn_new_rmb_loans_service, "cn_new_rmb_loans", "New RMB Loans"
        )
        result["cn_foreign_exchange_reserves"] = self._get_generic_indicator(
            cn_foreign_exchange_reserves_service, "cn_foreign_exchange_reserves", "Foreign Exchange Reserves"
        )
        result["cn_local_bonds"] = self._get_generic_indicator(
            cn_local_bonds_service, "cn_local_bonds", "Local Bonds"
        )
        result["cn_overseas_investor_flow"] = self._get_generic_indicator(
            cn_overseas_investor_flow_service, "cn_overseas_investor_flow", "Overseas Investor Flow"
        )
        result["cn_capital_flows"] = self._get_generic_indicator(
            cn_capital_flows_service, "cn_capital_flows", "Capital Flows"
        )

        return result

    def _get_lpr_indicator(self, service, kind: str, label: str) -> dict:
        """LPR指標データを取得"""
        try:
            force_refresh = self._should_force_refresh(f"cn_lpr_{kind}")
            method = getattr(service, f"get_lpr_{kind}_data")
            response = method(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[ChinaPolicy] Error getting {label}: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}

    def _get_generic_indicator(self, service, key: str, label: str) -> dict:
        """汎用指標データを取得"""
        try:
            force_refresh = self._should_force_refresh(key)
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[ChinaPolicy] Error getting {label}: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
