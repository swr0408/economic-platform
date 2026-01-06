"""
米国物価ダッシュボードローダー
CPI（消費者物価指数）+ コアCPI + PCEデフレーター + PPI + PPI項目別 + GSCPI を一括取得

データソース:
- CPI/コアCPI/CPI項目別/住宅関連指標: FRED
- PCEデフレーター/コアPCEデフレーター: FRED
- PPI/コアPPI: FRED
- PPI項目別: BLS API
- Zillow家賃指数: Zillow CSV直接取得
- 家賃CPI: FRED
- GSCPI: NY連銀Excelファイル

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
    - housing_indicators: 住宅関連指標 - FRED: Zillow家賃指数, ケースシラー住宅価格指数, 家賃CPI
    - zillow_rent_index: Zillow家賃指数（前年比）- Zillow CSV直接取得（毎月15日頃）
    - rent_cpi: 家賃CPI（前年比）- FRED: CUUR0000SAH1
    - pce_deflator: PCEデフレーター（前年比）- FRED: PCEPI（毎月20-31日頃 8:30 ET）
    - core_pce_deflator: コアPCEデフレーター（前年比）- FRED: PCEPILFE（毎月20-31日頃 8:30 ET）
    - ppi: 生産者物価指数（PPI）- FRED: PPIFIS（毎月9-17日頃 8:30 ET）
    - core_ppi: コアPPI（食品・エネルギー除く）- FRED: PPIFES（毎月9-17日頃 8:30 ET）
    - ppi_categories: PPI項目別 - BLS API: 航空、ポートフォリオ管理、医療関連など7項目
    - gscpi: グローバルサプライチェーン圧力指数 - NY連銀Excel（毎月第4営業日頃 10:00 ET）

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
            # キャッシュがない場合は全指標を更新対象とする
            return {"all"}

        try:
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)

            now = datetime.now(JST)
            stale = set()

            # CPI発表日時をチェック
            cpi_release = self._get_cpi_release_datetime()
            if cpi_release and last_updated_dt < cpi_release <= now:
                stale.add("cpi")
                stale.add("core_cpi")  # 同時発表
                stale.add("cpi_categories")  # 同時発表

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
