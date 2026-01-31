"""
ユーロ圏インフレダッシュボードローダー
HICP（消費者物価調和指数）、PPI（生産者物価指数）、SPF（インフレ期待）などのインフレ関連指標を一括取得

キャッシュ更新判定: FMP発表日時ベース方式
- ECB HICP: FMP発表日時ベース更新（"HICP MoM", "HICP YoY"パターン）
- ECB PPI: FMP発表日時ベース更新（"Producer Price Index MoM", "Producer Price Index YoY"パターン）
- ECB SPF: 独自判定方式（ECBサイトから次回発表日を取得）
- ECB SPF Core: 独自判定方式（ECBサイトから次回発表日を取得）
- Germany CPI: FMP発表日時ベース更新（"Inflation Rate YoY"パターン）
- Germany PPI: FMP発表日時ベース更新（"Producer Price Index MoM", "Producer Price Index YoY"パターン）
- ECB Inflation Expectations: FMP発表日時ベース更新（"Consumer Inflation Expectation"パターン）
- EU Import Prices: Eurostatリリースカレンダーベース更新（"Industrial import prices"パターン）
- Spain HICP/CPI: FMP発表日時ベース更新（"HICP YoY"パターン、country=ES）
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class EurozoneInflationLoader(BaseDashboardLoader):
    """
    ユーロ圏インフレダッシュボード用データローダー

    取得データ:
    - ecb_hicp: ECB HICP（消費者物価調和指数）
    - ecb_ppi: ECB PPI（生産者物価指数）
    - ecb_spf: ECB SPF（インフレ期待）
    - ecb_spf_core: ECB SPF Core（コアインフレ期待）
    - germany_cpi: ドイツCPI/HICP（消費者物価指数）
    - germany_ppi: ドイツPPI（生産者物価指数）
    - ecb_inflation_expectations: ECB CES インフレ期待（消費者期待調査）
    - eu_import_prices: EU輸入物価（Eurostat）
    - spain_hicp_cpi: スペインHICP/CPI（INE）

    キャッシュ方式: FMP発表日時ベース判定
    - ECB HICP: FMP発表日時ベース更新
    - ECB PPI: FMP発表日時ベース更新
    - ECB SPF: 独自判定方式
    - ECB SPF Core: 独自判定方式
    - Germany CPI: FMP発表日時ベース更新
    - Germany PPI: FMP発表日時ベース更新
    - ECB Inflation Expectations: FMP発表日時ベース更新
    - EU Import Prices: Eurostatリリースカレンダーベース更新
    - Spain HICP/CPI: FMP発表日時ベース更新
    """

    COUNTRY_CODE = "eurozone"
    CATEGORY_CODE = "inflation"

    # 期待されるデータキー（新しい指標追加時に更新）
    EXPECTED_KEYS = [
        "ecb_hicp",
        "ecb_ppi",
        "ecb_spf",
        "ecb_spf_core",
        "germany_cpi",
        "germany_ppi",
        "ecb_inflation_expectations",
        "eu_import_prices",
        "spain_hicp_cpi",
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

        try:
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)

            # 発表日時ベースの判定のみ
            # 各サービスが自身のキャッシュ判定を行う

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
        全インフレデータを並列で取得

        Returns:
            {
                "ecb_hicp": {...},
                "ecb_ppi": {...},
                "ecb_spf": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.eurozone.ecb_hicp_service import ecb_hicp_service
        from services.eurozone.ecb_ppi_service import ecb_ppi_service
        from services.eurozone.ecb_spf_service import ecb_spf_service
        from services.eurozone.ecb_spf_core_service import ecb_spf_core_service
        from services.eurozone.germany_cpi_service import germany_cpi_service
        from services.eurozone.germany_ppi_service import germany_ppi_service
        from services.eurozone.ecb_inflation_expectations_service import ecb_inflation_expectations_service
        from services.eurozone.eu_import_prices_service import eu_import_prices_service
        from services.eurozone.spain_hicp_cpi_service import spain_hicp_cpi_service

        result = {
            "ecb_hicp": None,
            "ecb_ppi": None,
            "ecb_spf": None,
            "ecb_spf_core": None,
            "germany_cpi": None,
            "germany_ppi": None,
            "ecb_inflation_expectations": None,
            "eu_import_prices": None,
            "spain_hicp_cpi": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=9) as executor:
            futures = {
                executor.submit(self._get_ecb_hicp, ecb_hicp_service): "ecb_hicp",
                executor.submit(self._get_ecb_ppi, ecb_ppi_service): "ecb_ppi",
                executor.submit(self._get_ecb_spf, ecb_spf_service): "ecb_spf",
                executor.submit(self._get_ecb_spf_core, ecb_spf_core_service): "ecb_spf_core",
                executor.submit(self._get_germany_cpi, germany_cpi_service): "germany_cpi",
                executor.submit(self._get_germany_ppi, germany_ppi_service): "germany_ppi",
                executor.submit(self._get_ecb_inflation_expectations, ecb_inflation_expectations_service): "ecb_inflation_expectations",
                executor.submit(self._get_eu_import_prices, eu_import_prices_service): "eu_import_prices",
                executor.submit(self._get_spain_hicp_cpi, spain_hicp_cpi_service): "spain_hicp_cpi",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_ecb_hicp(self, service) -> dict:
        """ECB HICPデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ecb_hicp")
            response = service.get_ecb_hicp_data(force_refresh=force_refresh)
            return {
                "annual_rates": response.get("annual_rates", {}),
                "monthly_changes": response.get("monthly_changes", {}),
                "breakdown_annual_rates": response.get("breakdown_annual_rates", {}),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ECB HICP: {e}")
            return {
                "annual_rates": {},
                "monthly_changes": {},
                "breakdown_annual_rates": {},
                "metadata": {},
            }

    def _get_ecb_ppi(self, service) -> dict:
        """ECB PPIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ecb_ppi")
            response = service.get_ecb_ppi_data(force_refresh=force_refresh)
            return {
                "annual_rates": response.get("annual_rates", {}),
                "monthly_changes": response.get("monthly_changes", {}),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ECB PPI: {e}")
            return {
                "annual_rates": {},
                "monthly_changes": {},
                "metadata": {},
            }

    def _get_ecb_spf(self, service) -> dict:
        """ECB SPFデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ecb_spf")
            response = service.get_ecb_spf_data(force_refresh=force_refresh)
            return {
                "inflation_expectations": response.get("inflation_expectations", {}),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ECB SPF: {e}")
            return {
                "inflation_expectations": {},
                "metadata": {},
            }

    def _get_ecb_spf_core(self, service) -> dict:
        """ECB SPF Coreデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ecb_spf_core")
            response = service.get_ecb_spf_core_data(force_refresh=force_refresh)
            return {
                "inflation_expectations": response.get("inflation_expectations", {}),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ECB SPF Core: {e}")
            return {
                "inflation_expectations": {},
                "metadata": {},
            }

    def _get_germany_cpi(self, service) -> dict:
        """ドイツCPI/HICPデータを取得（Destatis GENESIS API）"""
        try:
            force_refresh = self._should_force_refresh("germany_cpi")
            response = service.get_germany_cpi_data(force_refresh=force_refresh)

            # Destatis APIからのマージされたデータを個別系列に変換
            raw_data = response.get("data", [])

            cpi_yoy = []
            cpi_mom = []
            hicp_yoy = []
            hicp_mom = []

            for point in raw_data:
                date = point.get("date")
                if not date:
                    continue

                if point.get("cpi_yoy_change") is not None:
                    cpi_yoy.append({"date": date, "value": point["cpi_yoy_change"]})
                if point.get("cpi_mom_change") is not None:
                    cpi_mom.append({"date": date, "value": point["cpi_mom_change"]})
                if point.get("hicp_yoy_change") is not None:
                    hicp_yoy.append({"date": date, "value": point["hicp_yoy_change"]})
                if point.get("hicp_mom_change") is not None:
                    hicp_mom.append({"date": date, "value": point["hicp_mom_change"]})

            return {
                "cpi_yoy": cpi_yoy,
                "cpi_mom": cpi_mom,
                "hicp_yoy": hicp_yoy,
                "hicp_mom": hicp_mom,
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Germany CPI: {e}")
            return {
                "cpi_yoy": [],
                "cpi_mom": [],
                "hicp_yoy": [],
                "hicp_mom": [],
                "metadata": {},
            }

    def _get_germany_ppi(self, service) -> dict:
        """ドイツPPIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("germany_ppi")
            response = service.get_germany_ppi_data(force_refresh=force_refresh)

            raw_data = response.get("data", [])

            ppi_yoy = []
            ppi_mom = []

            for point in raw_data:
                date = point.get("date")
                if not date:
                    continue

                if point.get("ppi_yoy_change") is not None:
                    ppi_yoy.append({"date": date, "value": point["ppi_yoy_change"]})
                if point.get("ppi_mom_change") is not None:
                    ppi_mom.append({"date": date, "value": point["ppi_mom_change"]})

            return {
                "ppi_yoy": ppi_yoy,
                "ppi_mom": ppi_mom,
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Germany PPI: {e}")
            return {
                "ppi_yoy": [],
                "ppi_mom": [],
                "metadata": {},
            }

    def _get_ecb_inflation_expectations(self, service) -> dict:
        """ECB消費者インフレ期待データを取得"""
        try:
            force_refresh = self._should_force_refresh("ecb_inflation_expectations")
            response = service.get_inflation_expectations_data(force_refresh=force_refresh)

            data = response.get("data", {})

            return {
                "inflation_12m": data.get("inflation_12m", []),
                "inflation_3y": data.get("inflation_3y", []),
                "inflation_5y": data.get("inflation_5y", []),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ECB Inflation Expectations: {e}")
            return {
                "inflation_12m": [],
                "inflation_3y": [],
                "inflation_5y": [],
                "metadata": {},
            }

    def _get_eu_import_prices(self, service) -> dict:
        """EU輸入物価データを取得"""
        try:
            force_refresh = self._should_force_refresh("eu_import_prices")
            response = service.get_data(force_refresh=force_refresh)

            return {
                "yoy": response.get("yoy", []),
                "mom": response.get("mom", []),
                "latest_yoy": response.get("latest_yoy"),
                "latest_mom": response.get("latest_mom"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting EU Import Prices: {e}")
            return {
                "yoy": [],
                "mom": [],
                "latest_yoy": None,
                "latest_mom": None,
                "metadata": {},
            }

    def _get_spain_hicp_cpi(self, service) -> dict:
        """スペインHICP/CPIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("spain_hicp_cpi")
            response = service.get_data(force_refresh=force_refresh)

            return {
                "cpi_mom": response.get("cpi_mom", []),
                "cpi_yoy": response.get("cpi_yoy", []),
                "core_cpi_mom": response.get("core_cpi_mom", []),
                "core_cpi_yoy": response.get("core_cpi_yoy", []),
                "hicp_mom": response.get("hicp_mom", []),
                "hicp_yoy": response.get("hicp_yoy", []),
                "latest_cpi_yoy": response.get("latest_cpi_yoy"),
                "latest_hicp_yoy": response.get("latest_hicp_yoy"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting Spain HICP/CPI: {e}")
            return {
                "cpi_mom": [],
                "cpi_yoy": [],
                "core_cpi_mom": [],
                "core_cpi_yoy": [],
                "hicp_mom": [],
                "hicp_yoy": [],
                "latest_cpi_yoy": None,
                "latest_hicp_yoy": None,
                "metadata": {},
            }
