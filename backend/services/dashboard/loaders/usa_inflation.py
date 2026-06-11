"""
米国物価ダッシュボードローダー
CPI（消費者物価指数）+ コアCPI + PCEデフレーター + PPI + PPI項目別 + GSCPI + Inflation Nowcasting + 輸入輸出物価指数 + シカゴ連銀小売物価指数 + NY連銀インフレ期待 + ミシガン大学インフレ期待 + Trimmed Mean PCE を一括取得

データソース:
- CPI/コアCPI/CPI項目別/住宅関連指標: FRED
- PCEデフレーター/コアPCEデフレーター: FRED
- PPI/コアPPI: FRED
- PPI項目別: BLS API
- Zillow家賃指数: Zillow CSV直接取得
- 家賃CPI: FRED
- GSCPI: NY連銀Excelファイル
- Inflation Nowcasting: Cleveland Fed（Seleniumスクレイピング）
- 輸入物価指数/輸出物価指数: FRED (IR, IQ)
- シカゴ連銀小売物価指数: Chicago Fed CARTS (ZIP/Excel)
- NY連銀インフレ期待: NY Fed SCE (Excel)
- ミシガン大学インフレ期待: University of Michigan CSV
- Trimmed Mean PCE: Dallas Fed Excel

キャッシュ更新判定: 発表日時ベース方式
- 発表日: FMPカレンダーから取得
- 発表時刻: 8:30 ET
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")


class USAInflationLoader(BaseDashboardLoader):
    """
    米国物価ダッシュボード用データローダー

    取得データ:
    - cpi: CPI（消費者物価指数）- FRED: CPIAUCSL（毎月10-15日頃 8:30 ET）
    - core_cpi: コアCPI（食品・エネルギー除く）- FRED: CPILFESL（毎月10-15日頃 8:30 ET）
    - cpi_categories: CPI項目別 - FRED: 食品, エネルギー, コア財, コアサービス, 住居費
    - housing_indicators: 住宅関連指標 - FRED: Zillow住宅価値指数, ケースシラー住宅価格指数, 家賃CPI
    - zillow_rent_index: Zillow家賃指数（前年比）- Zillow CSV直接取得（毎月15日頃）
    - rent_cpi: 家賃CPI（前年比）- FRED: CUUR0000SAH1
    - pce_deflator: PCEデフレーター（前年比）- FRED: PCEPI（毎月20-31日頃 8:30 ET）
    - core_pce_deflator: コアPCEデフレーター（前年比）- FRED: PCEPILFE（毎月20-31日頃 8:30 ET）
    - ppi: 生産者物価指数（PPI）- FRED: PPIFIS（毎月9-17日頃 8:30 ET）
    - core_ppi: コアPPI（食品・エネルギー除く）- FRED: PPIFES（毎月9-17日頃 8:30 ET）
    - ppi_categories: PPI項目別 - BLS API: 航空、ポートフォリオ管理、医療関連など7項目
    - gscpi: グローバルサプライチェーン圧力指数 - NY連銀Excel（毎月第4営業日頃 10:00 ET）
    - inflation_nowcasting: インフレーションナウキャスティング - Cleveland Fed（毎営業日 10:00 ET頃）
    - import_export_price: 輸入物価指数/輸出物価指数（前年比）- FRED: IR, IQ（毎月中旬 8:30 ET頃）
    - retail_food_services_price: シカゴ連銀小売物価指数（CARTS Fig6）- Chicago Fed（週次更新）
    - ny_inflation_expectations: NY連銀インフレ期待 - NY Fed SCE Excel（毎月第2月曜日 11:00 ET頃）
    - michigan_inflation_expectations: ミシガン大学インフレ期待 - University of Michigan CSV（毎月2回発表）
    - trimmed_mean_pce: Trimmed Mean PCE Inflation Rate - Dallas Fed Excel（毎月末頃）
    - supply_and_demand_driven_pce_inflation: Supply- and Demand-Driven PCE Inflation - SF Fed CSV（PCE発表後数日内）
    - used_car_prices: 中古車価格（FRED CPI Used Cars + Manheim Used Vehicle Value Index）
    - nfib_price_plans: NFIB中小企業価格引き上げ計画 - NFIB PDF（毎月第2火曜日 6:00 ET）

    キャッシュ方式: 発表日時ベース判定
    - CPI発表: 毎月10-15日頃 8:30 ET（CPIとコアCPIは同時発表）
    - 発表日時を過ぎた指標は個別サービスもforce_refreshで再取得
    """

    COUNTRY_CODE = "usa"
    CATEGORY_CODE = "inflation"

    def __init__(self):
        super().__init__()
        # 発表日時を過ぎた指標のセット（load_all実行時に判定）
        self._stale_indicators: set = set()

    # 発表時刻設定（ET）
    CPI_RELEASE_HOUR_ET = 8
    CPI_RELEASE_MINUTE_ET = 30

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        """
        各指標の発表日時リストを返す

        Returns:
            - CPI発表日時（8:30 ET）
        """
        release_times = []

        # CPI発表日時
        cpi_release = self._get_cpi_release_datetime()
        if cpi_release:
            release_times.append(cpi_release)

        return release_times

    def _get_cpi_release_datetime(self) -> Optional[datetime]:
        """
        CPIの発表日時を取得

        Returns:
            発表日時（JST）、取得できない場合はNone
        """
        try:
            from services.usa.cpi_service import cpi_service

            # サービスからnext_releaseを取得（キャッシュから軽量に取得）
            data = cpi_service.get_cpi_data()
            next_release = data.get("next_release")

            if not next_release:
                return None

            date_str = next_release.get("date")
            if not date_str:
                return None

            # YYYY-MM-DD形式をパース
            try:
                base_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                return None

            # 発表時刻（8:30 ET）をJSTに変換
            release_et = datetime(
                base_date.year, base_date.month, base_date.day,
                self.CPI_RELEASE_HOUR_ET,
                self.CPI_RELEASE_MINUTE_ET,
                tzinfo=ET
            )
            release_jst = release_et.astimezone(JST)

            return release_jst

        except Exception as e:
            print(f"Error getting CPI release datetime: {e}")
            return None

    def _detect_stale_indicators(self, last_updated: Optional[str]) -> set:
        """
        発表日時を過ぎた指標を検出

        Args:
            last_updated: ダッシュボードキャッシュのlast_updated（ISO形式）

        Returns:
            発表日時を過ぎた指標名のセット
        """
        if last_updated is None:
            return set()

        try:
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)

            now = datetime.now(JST)
            stale = set()

            # CPI発表日時をチェック
            # next_releaseは発表直後に次回日付へ切り替わるため、last_releaseも確認する
            cpi_release = self._get_cpi_release_datetime()
            cpi_last_release = self._get_last_release_datetime_from_fmp(
                "us_cpi", release_hour_et=8, release_minute_et=30, indicator_name="CPI"
            )
            if self._is_stale_by_release(last_updated_dt, now, cpi_release, cpi_last_release):
                stale.add("cpi")
                stale.add("core_cpi")  # 同時発表
                stale.add("cpi_categories")  # 同時発表
                stale.add("used_car_prices")  # FRED中古車(CUSR0000SETA02)はCPIと同時発表

            if stale:
                print(f"[stale] Detected stale indicators: {stale}")

            return stale

        except Exception as e:
            print(f"Error detecting stale indicators: {e}")
            # エラー時は全指標を更新対象とする
            return {"all"}

    def _should_force_refresh(self, indicator: str) -> bool:
        """指標が強制更新対象かどうかを判定"""
        if "all" in self._stale_indicators:
            return True
        return indicator in self._stale_indicators

    def _prepare_for_refresh(self, last_updated: Optional[str]) -> None:
        """
        データ再取得の前処理

        発表日時を過ぎた指標を検出し、force_refresh対象を設定する。
        """
        self._stale_indicators = self._detect_stale_indicators(last_updated)
        if self._stale_indicators:
            print(f"Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全物価データを並列で取得

        Returns:
            {
                "cpi": {...},
                "core_cpi": {...},
                "cpi_categories": {...},
                "housing_indicators": {...},
                "zillow_rent_index": {...},
                "rent_cpi": {...}
            }
        """
        # 遅延インポート（循環参照回避）
        from services.usa.cpi_service import cpi_service
        from services.usa.housing_indicators_service import housing_indicators_service
        from services.usa.zillow_rent_index_service import zillow_rent_index_service
        from services.usa.rent_cpi_service import rent_cpi_service
        from services.usa.pce_deflator_service import pce_deflator_service
        from services.usa.ppi_service import ppi_service
        from services.usa.ppi_categories_service import ppi_categories_service
        from services.usa.gscpi_service import gscpi_service
        from services.usa.inflation_nowcasting_service import inflation_nowcasting_service
        from services.usa.import_export_price_service import import_export_price_service
        from services.usa.retail_food_services_price_service import retail_food_services_price_service
        from services.usa.ny_inflation_expectations_service import ny_inflation_expectations_service
        from services.usa.michigan_inflation_expectations_service import michigan_inflation_expectations_service
        from services.usa.trimmed_mean_pce_service import trimmed_mean_pce_service
        from services.usa.median_cpi_service import median_cpi_service
        from services.usa.supply_and_demand_driven_pce_inflation_service import (
            supply_and_demand_driven_pce_inflation_service,
        )
        from services.usa.used_car_prices_service import used_car_prices_service
        from services.usa.nfib_service import nfib_service

        result = {
            "cpi": None,
            "core_cpi": None,
            "cpi_categories": None,
            "housing_indicators": None,
            "zillow_rent_index": None,
            "rent_cpi": None,
            "pce_deflator": None,
            "core_pce_deflator": None,
            "ppi": None,
            "core_ppi": None,
            "ppi_categories": None,
            "gscpi": None,
            "inflation_nowcasting": None,
            "import_export_price": None,
            "retail_food_services_price": None,
            "ny_inflation_expectations": None,
            "michigan_inflation_expectations": None,
            "trimmed_mean_pce": None,
            "median_cpi": None,
            "supply_and_demand_driven_pce_inflation": None,
            "used_car_prices": None,
            "nfib_price_plans": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(self._get_cpi, cpi_service): "cpi",
                executor.submit(self._get_core_cpi, cpi_service): "core_cpi",
                executor.submit(self._get_cpi_categories, cpi_service): "cpi_categories",
                executor.submit(self._get_housing_indicators, housing_indicators_service): "housing_indicators",
                executor.submit(self._get_zillow_rent_index, zillow_rent_index_service): "zillow_rent_index",
                executor.submit(self._get_rent_cpi, rent_cpi_service): "rent_cpi",
                executor.submit(self._get_pce_deflator, pce_deflator_service): "pce_deflator",
                executor.submit(self._get_core_pce_deflator, pce_deflator_service): "core_pce_deflator",
                executor.submit(self._get_ppi, ppi_service): "ppi",
                executor.submit(self._get_core_ppi, ppi_service): "core_ppi",
                executor.submit(self._get_ppi_categories, ppi_categories_service): "ppi_categories",
                executor.submit(self._get_gscpi, gscpi_service): "gscpi",
                executor.submit(self._get_inflation_nowcasting, inflation_nowcasting_service): "inflation_nowcasting",
                executor.submit(self._get_import_export_price, import_export_price_service): "import_export_price",
                executor.submit(self._get_retail_food_services_price, retail_food_services_price_service): "retail_food_services_price",
                executor.submit(self._get_ny_inflation_expectations, ny_inflation_expectations_service): "ny_inflation_expectations",
                executor.submit(self._get_michigan_inflation_expectations, michigan_inflation_expectations_service): "michigan_inflation_expectations",
                executor.submit(self._get_trimmed_mean_pce, trimmed_mean_pce_service): "trimmed_mean_pce",
                executor.submit(self._get_median_cpi, median_cpi_service): "median_cpi",
                executor.submit(
                    self._get_supply_and_demand_driven_pce_inflation,
                    supply_and_demand_driven_pce_inflation_service,
                ): "supply_and_demand_driven_pce_inflation",
                executor.submit(
                    self._get_used_car_prices, used_car_prices_service
                ): "used_car_prices",
                executor.submit(
                    self._get_nfib_price_plans, nfib_service
                ): "nfib_price_plans",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_cpi(self, service) -> Optional[dict]:
        """CPIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("cpi")
            response = service.get_cpi_data(force_refresh=force_refresh)
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
            print(f"Error getting CPI data: {e}")
            return None

    def _get_core_cpi(self, service) -> Optional[dict]:
        """コアCPIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("core_cpi")
            response = service.get_core_cpi_data(force_refresh=force_refresh)
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
            print(f"Error getting Core CPI data: {e}")
            return None

    def _get_cpi_categories(self, service) -> Optional[dict]:
        """CPI項目別データを取得"""
        try:
            force_refresh = self._should_force_refresh("cpi_categories")
            response = service.get_cpi_categories_data(force_refresh=force_refresh)
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
            print(f"Error getting CPI categories data: {e}")
            return None

    def _get_housing_indicators(self, service) -> Optional[dict]:
        """住宅関連指標データを取得"""
        try:
            response = service.get_housing_indicators_data()
            data = response.get("data", {})
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting housing indicators data: {e}")
            return None

    def _get_zillow_rent_index(self, service) -> Optional[dict]:
        """Zillow家賃指数データを取得"""
        try:
            response = service.get_zillow_rent_index_data()
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting Zillow rent index data: {e}")
            return None

    def _get_rent_cpi(self, service) -> Optional[dict]:
        """家賃CPIデータを取得"""
        try:
            response = service.get_rent_cpi_data()
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting rent CPI data: {e}")
            return None

    def _get_pce_deflator(self, service) -> Optional[dict]:
        """PCEデフレーターデータを取得"""
        try:
            force_refresh = self._should_force_refresh("pce_deflator")
            response = service.get_pce_deflator_data(force_refresh=force_refresh)
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
            print(f"Error getting PCE deflator data: {e}")
            return None

    def _get_core_pce_deflator(self, service) -> Optional[dict]:
        """コアPCEデフレーターデータを取得"""
        try:
            force_refresh = self._should_force_refresh("core_pce_deflator")
            response = service.get_core_pce_deflator_data(force_refresh=force_refresh)
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
            print(f"Error getting Core PCE deflator data: {e}")
            return None

    def _get_ppi(self, service) -> Optional[dict]:
        """PPIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("ppi")
            response = service.get_ppi_data(force_refresh=force_refresh)
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
            print(f"Error getting PPI data: {e}")
            return None

    def _get_core_ppi(self, service) -> Optional[dict]:
        """コアPPIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("core_ppi")
            response = service.get_core_ppi_data(force_refresh=force_refresh)
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
            print(f"Error getting Core PPI data: {e}")
            return None

    def _get_ppi_categories(self, service) -> Optional[dict]:
        """PPI項目別データを取得"""
        try:
            force_refresh = self._should_force_refresh("ppi_categories")
            response = service.get_ppi_categories_data(force_refresh=force_refresh)
            categories = response.get("categories", [])
            if not categories:
                return None
            return {
                "categories": categories,
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting PPI categories data: {e}")
            return None

    def _get_gscpi(self, service) -> Optional[dict]:
        """GSCPIデータを取得"""
        try:
            force_refresh = self._should_force_refresh("gscpi")
            response = service.get_gscpi_data(force_refresh=force_refresh)
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
            print(f"Error getting GSCPI data: {e}")
            return None

    def _get_inflation_nowcasting(self, service) -> Optional[dict]:
        """インフレーションナウキャスティングデータを取得"""
        try:
            force_refresh = self._should_force_refresh("inflation_nowcasting")
            response = service.get_inflation_nowcasting_data(force_refresh=force_refresh)
            monthly_mom = response.get("monthly_mom", [])
            monthly_yoy = response.get("monthly_yoy", [])
            if not monthly_mom and not monthly_yoy:
                return None
            return {
                "monthly_mom": monthly_mom,
                "monthly_yoy": monthly_yoy,
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting Inflation Nowcasting data: {e}")
            return None

    def _get_import_export_price(self, service) -> Optional[dict]:
        """輸入物価指数/輸出物価指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("import_export_price")
            response = service.get_import_export_price_data(force_refresh=force_refresh)
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
            print(f"Error getting Import/Export Price data: {e}")
            return None

    def _get_retail_food_services_price(self, service) -> Optional[dict]:
        """シカゴ連銀小売物価指数（CARTS Fig6）データを取得"""
        try:
            force_refresh = self._should_force_refresh("retail_food_services_price")
            response = service.get_retail_food_services_price_data(force_refresh=force_refresh)
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting Retail Food Services Price data: {e}")
            return None

    def _get_ny_inflation_expectations(self, service) -> Optional[dict]:
        """NY連銀インフレ期待データを取得"""
        try:
            force_refresh = self._should_force_refresh("ny_inflation_expectations")
            response = service.get_inflation_expectations_data(force_refresh=force_refresh)
            data = response.get("data", {})
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting NY Inflation Expectations data: {e}")
            return None

    def _get_michigan_inflation_expectations(self, service) -> Optional[dict]:
        """ミシガン大学インフレ期待データを取得"""
        try:
            force_refresh = self._should_force_refresh("michigan_inflation_expectations")
            response = service.get_inflation_expectations_data(force_refresh=force_refresh)
            data = response.get("data", {})
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting Michigan Inflation Expectations data: {e}")
            return None

    def _get_trimmed_mean_pce(self, service) -> Optional[dict]:
        """Trimmed Mean PCE Inflation Rate データを取得"""
        try:
            force_refresh = self._should_force_refresh("trimmed_mean_pce")
            response = service.get_data(force_refresh=force_refresh)
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
            print(f"Error getting Trimmed Mean PCE data: {e}")
            return None

    def _get_median_cpi(self, service) -> Optional[dict]:
        """Median CPI データを取得"""
        try:
            force_refresh = self._should_force_refresh("median_cpi")
            response = service.get_data(force_refresh=force_refresh)
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
            print(f"Error getting Median CPI data: {e}")
            return None

    def _get_supply_and_demand_driven_pce_inflation(self, service) -> Optional[dict]:
        """Supply- and Demand-Driven PCE Inflation データを取得"""
        try:
            force_refresh = self._should_force_refresh("supply_and_demand_driven_pce_inflation")
            response = service.get_data(force_refresh=force_refresh)
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
            print(f"Error getting Supply/Demand-Driven PCE Inflation data: {e}")
            return None

    def _get_used_car_prices(self, service) -> Optional[dict]:
        """中古車価格（FRED + Manheim）データを取得"""
        try:
            force_refresh = self._should_force_refresh("used_car_prices")
            response = service.get_data(force_refresh=force_refresh)
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
            print(f"Error getting Used Car Prices data: {e}")
            return None

    def _get_nfib_price_plans(self, service) -> Optional[dict]:
        """NFIB中小企業価格引き上げ計画データを取得"""
        try:
            force_refresh = self._should_force_refresh("nfib_price_plans")
            response = service.get_price_plans_data(force_refresh=force_refresh)
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
            print(f"Error getting NFIB Price Plans data: {e}")
            return None
