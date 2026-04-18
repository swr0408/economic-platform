"""
ユーロ圏金融政策ダッシュボードローダー
ECB政策金利、Eurex OIS、M3マネーサプライ、Bank Interest Rates、次回発表日などを一括取得

キャッシュ更新判定: 発表日時ベース方式
- ECB金利決定: 21:15-21:25 JST（冬時間）/ 22:15-22:25 JST（夏時間）
- Eurex OIS: 20:00-20:10 JST（夏時間）/ 21:00-21:10 JST（冬時間）
- M3マネーサプライ: FMP発表日時ベース更新
- Bank Interest Rates: ECBカレンダーベース更新
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class EurozonePolicyLoader(BaseDashboardLoader):
    """
    ユーロ圏金融政策ダッシュボード用データローダー

    取得データ:
    - ecb_rates: ECB預金ファシリティ金利
    - eurex_ois: Eurex OISカーブ
    - ecb_macro_projections: ECBマクロ経済予測
    - ecb_m3: M3マネーサプライ
    - ecb_bank_interest_rates: 銀行金利（企業向け・住宅ローン）
    - ecb_balance_sheet: ECBバランスシート（総資産）

    キャッシュ方式: 発表日時ベース判定
    - ECB金利決定: 21:15-22:25 JST（時期により変動）
    - Eurex OIS: 20:00-21:10 JST（時期により変動）
    - ECBマクロ経済予測: 四半期ごと（3月、6月、9月、12月）
    - M3マネーサプライ: FMP発表日時ベース更新
    - Bank Interest Rates: ECBカレンダーベース更新
    """

    COUNTRY_CODE = "eurozone"
    CATEGORY_CODE = "policy"

    def __init__(self):
        super().__init__()
        # 発表日時を過ぎた指標のセット（load_all実行時に判定）
        self._stale_indicators: set = set()

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        """
        各指標の発表日時リストを返す

        Returns:
            - ECB金利決定発表日時
            - M3マネーサプライ発表日時
        """
        release_times = []

        # ECB発表日時（政策金利の更新タイミング）
        ecb_release = self._get_ecb_release_datetime()
        if ecb_release:
            release_times.append(ecb_release)

        # M3マネーサプライ発表日時
        m3_release = self._get_m3_release_datetime()
        if m3_release:
            release_times.append(m3_release)

        return release_times

    def _get_ecb_release_datetime(self) -> Optional[datetime]:
        """
        次回ECB金利決定発表日時を取得

        Returns:
            ECB発表日時（JST）、取得できない場合はNone
        """
        try:
            from services.eurozone.fmp_next_release_utils import get_next_release_from_fmp

            next_release = get_next_release_from_fmp("eu_ecb_rate")
            if not next_release:
                return None

            datetime_jst_str = next_release.get("datetime_jst")
            if not datetime_jst_str:
                return None

            return datetime.fromisoformat(datetime_jst_str)

        except Exception as e:
            print(f"Error getting ECB release datetime: {e}")
            return None

    def _get_m3_release_datetime(self) -> Optional[datetime]:
        """
        次回M3マネーサプライ発表日時を取得

        Returns:
            M3発表日時（JST）、取得できない場合はNone
        """
        try:
            from services.eurozone.fmp_next_release_utils import get_next_release_from_fmp

            next_release = get_next_release_from_fmp("monetary_aggregate_m3")
            if not next_release:
                return None

            datetime_jst_str = next_release.get("datetime_jst")
            if not datetime_jst_str:
                return None

            return datetime.fromisoformat(datetime_jst_str)

        except Exception as e:
            print(f"Error getting M3 release datetime: {e}")
            return None

    def _detect_stale_indicators(self, last_updated: Optional[str]) -> set:
        """
        発表日時を過ぎた指標を検出

        Args:
            last_updated: ダッシュボードキャッシュのlast_updated（ISO形式）

        Returns:
            発表日時を過ぎた指標名のセット
        """
        stale = set()

        if last_updated is None:
            return set()

        try:
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)

            now = datetime.now(JST)

            # ECB発表（政策金利）
            # next_releaseは発表直後に次回日付へ切り替わるため、last_releaseも確認する
            ecb_release = self._get_ecb_release_datetime()
            ecb_last = self._get_last_release_datetime_from_fmp(
                "eu_ecb_rate", indicator_name="ECB", country="eurozone"
            )
            if self._is_stale_by_release(last_updated_dt, now, ecb_release, ecb_last):
                stale.add("ecb_rates")
                print(f"[stale] ECB release detected")

            # M3マネーサプライ発表
            m3_release = self._get_m3_release_datetime()
            m3_last = self._get_last_release_datetime_from_fmp(
                "monetary_aggregate_m3", indicator_name="M3", country="eurozone"
            )
            if self._is_stale_by_release(last_updated_dt, now, m3_release, m3_last):
                stale.add("ecb_m3")
                print(f"[stale] M3 release detected")

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

        発表日時を過ぎた指標を検出し、force_refresh対象を設定する。
        """
        self._stale_indicators = self._detect_stale_indicators(last_updated)
        if self._stale_indicators:
            print(f"Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全金融政策データを並列で取得

        Returns:
            {
                "ecb_rates": {...},
                "eurex_ois": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.eurozone.ecb_rates_service import ecb_rates_service
        from services.eurozone.eurex_ois_service import eurex_ois_service
        from services.eurozone.ecb_macro_projections_service import ecb_macro_projections_service
        from services.eurozone.ecb_m3_service import ecb_m3_service
        from services.eurozone.ecb_bank_interest_rates_service import ecb_bank_interest_rates_service
        from services.eurozone.ecb_balance_sheet_service import ecb_balance_sheet_service

        result = {
            "ecb_rates": None,
            "eurex_ois": None,
            "ecb_macro_projections": None,
            "ecb_m3": None,
            "ecb_bank_interest_rates": None,
            "ecb_balance_sheet": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=7) as executor:
            futures = {
                executor.submit(self._get_ecb_rates, ecb_rates_service): "ecb_rates",
                executor.submit(self._get_eurex_ois, eurex_ois_service): "eurex_ois",
                executor.submit(self._get_ecb_macro_projections, ecb_macro_projections_service): "ecb_macro_projections",
                executor.submit(self._get_ecb_m3, ecb_m3_service): "ecb_m3",
                executor.submit(self._get_ecb_bank_interest_rates, ecb_bank_interest_rates_service): "ecb_bank_interest_rates",
                executor.submit(self._get_ecb_balance_sheet, ecb_balance_sheet_service): "ecb_balance_sheet",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_ecb_rates(self, service) -> dict:
        """ECB金利データを取得"""
        try:
            force_refresh = self._should_force_refresh("ecb_rates")
            response = service.get_ecb_rates_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ECB rates: {e}")
            return {"data": [], "latest": None, "next_release": None}

    def _get_eurex_ois(self, service) -> dict:
        """Eurex OISデータを取得

        スケジューラーが毎日キャッシュを更新するため、通常はキャッシュから取得。
        キャッシュが空の場合のみスクレイピングを実行する。
        """
        try:
            # まずキャッシュから取得を試みる
            response = service.get_chart_data(force_refresh=False)
            if response and response.get('labels'):
                return response
            # キャッシュがない場合のみスクレイピング実行（タイムアウト120秒）
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(service.get_chart_data, True)
                try:
                    response = future.result(timeout=120)
                    return response
                except concurrent.futures.TimeoutError:
                    print("Eurex OIS fetch timed out (120s), returning empty data")
                    return self._get_empty_eurex_ois_data()
        except Exception as e:
            print(f"Error getting Eurex OIS: {e}")
            return self._get_empty_eurex_ois_data()

    def _get_empty_eurex_ois_data(self) -> dict:
        """空のEurex OISデータを返す"""
        return {
            "labels": [],
            "values": [],
            "contracts": [],
            "settle_values": [],
            "previous_values": [],
            "current_date": None,
            "previous_date": None,
            "last_updated": None,
            "source": "Eurex"
        }

    def _get_ecb_macro_projections(self, service) -> dict:
        """ECBマクロ経済予測データを取得"""
        try:
            force_refresh = self._should_force_refresh("ecb_macro_projections")
            response = service.get_ecb_macro_projections_data(force_refresh=force_refresh)
            # 新しいAPI構造に合わせて返す
            return {
                "indicators": response.get("indicators", {}),
                "metadata": response.get("metadata", {}),
            }
        except Exception as e:
            print(f"Error getting ECB macro projections: {e}")
            return {"indicators": {}, "metadata": {}}

    def _get_ecb_m3(self, service) -> dict:
        """ECB M3マネーサプライデータを取得（原数値と前年比）"""
        try:
            force_refresh = self._should_force_refresh("ecb_m3")
            response = service.get_ecb_m3_data(force_refresh=force_refresh)
            return {
                "yoy": response.get("yoy", {}),
                "level": response.get("level", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ECB M3: {e}")
            return {"yoy": {"data": [], "latest": None}, "level": {"data": [], "latest": None}, "next_release": None}

    def _get_ecb_bank_interest_rates(self, service) -> dict:
        """ECB Bank Interest Ratesデータを取得（企業向け・住宅ローン）"""
        try:
            force_refresh = self._should_force_refresh("ecb_bank_interest_rates")
            response = service.get_bank_interest_rates_data(force_refresh=force_refresh)
            return {
                "corporations": response.get("corporations", {}),
                "housing": response.get("housing", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"Error getting ECB Bank Interest Rates: {e}")
            return {"corporations": {"data": [], "latest": None}, "housing": {"data": [], "latest": None}, "next_release": None}

    def _get_ecb_balance_sheet(self, service) -> dict:
        """ECBバランスシート（総資産）データを取得"""
        try:
            force_refresh = self._should_force_refresh("ecb_balance_sheet")
            response = service.get_ecb_balance_sheet_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
            }
        except Exception as e:
            print(f"Error getting ECB Balance Sheet: {e}")
            return {"data": [], "latest": None}
