"""
米国消費ダッシュボードローダー
小売売上高 + コントロールグループ + CARTS + Affinity Spend + Visa支出 + 自動車販売台数 + Redbook + クレジットカードローン残高 + クレジットカードローン延滞率 + CB消費者信頼感 + CB雇用機会業況判断 + ミシガン消費者信頼感 + 家計貯蓄率 + 個人所得 + 可処分所得 + 個人消費支出 を一括取得

キャッシュ更新判定: 発表日時ベース方式
- 発表日: Census.gov / Chicago Fed / GitHubから自動取得（next_release）
- 発表時刻: 8:30 ET（小売売上高・CARTS）、不定期（Affinity Spend）
- Visa支出: 発表日自動取得（不明時は1ヶ月経過後1日1回チェック）
- 自動車販売台数: FRED releases/datesから発表日自動取得
- Redbook: 毎週火曜日 8:55 ET発表
- クレジットカードローン残高: 毎週金曜日 16:15 ET発表（H.8）
- クレジットカードローン延滞率: 四半期末60日後発表（2月・5月・8月・11月の15日過ぎ）
- CB消費者信頼感: 毎月最終火曜日 10:00 ET発表
- CB雇用機会業況判断: 毎月最終火曜日 10:00 ET発表（CB消費者信頼感と同時発表）
- ミシガン消費者信頼感: 毎月第2金曜日（速報版）/ 最終金曜日（確報版） 10:00 ET発表
- 家計貯蓄率/個人所得/可処分所得/個人消費支出: 毎月月末 8:30 ET発表（BEA Personal Income）
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")


class USAConsumerLoader(BaseDashboardLoader):
    """
    米国消費ダッシュボード用データローダー

    取得データ:
    - retail_sales: 小売売上高 - FRED RSAFS, RSFSXMV（毎月中旬 8:30 ET）
    - retail_control: コントロールグループ - DB/FMP（毎月中旬 8:30 ET）
    - carts: シカゴ連銀小売指数 - Chicago Fed CARTS（毎月第1木曜/第2金曜 8:30 ET）
    - affinity_spend: Affinityカード支出 - Opportunity Insights（不定期、GitHubコミットで判定）
    - visa_spending: Visa支出モメンタム指数 - FRED VISASMIHSA（毎月更新）
    - total_vehicle_sales: 自動車販売台数 - FRED TOTALSA（毎月更新）
    - redbook: Redbook小売売上高指数 - DB/FMP（毎週火曜日 8:55 ET）
    - consumer_credit: クレジットカードローン残高 - FRED CCLACBW027SBOG（毎週金曜日 16:15 ET）
    - delinquency_rate: クレジットカードローン延滞率 - FRED DRCCLACBS（四半期・2月/5月/8月/11月発表）
    - cb_consumer_confidence: CB消費者信頼感指数 - DB/FMP（毎月最終火曜日 10:00 ET）
    - cb_jobs_labor: CB雇用機会業況判断 - Conference Board公式ページ（毎月最終火曜日 10:00 ET）
    - michigan_consumer_sentiment: ミシガン消費者信頼感指数 - ミシガン大学（毎月第2金曜/最終金曜 10:00 ET）
    - personal_saving_rate: 家計貯蓄率 - FRED PSAVERT（毎月月末 8:30 ET）
    - personal_income: 個人所得 - FRED PI/RPI（毎月月末 8:30 ET）
    - disposable_income: 可処分所得 - FRED DSPI/DSPIC96（毎月月末 8:30 ET）
    - pce: 個人消費支出 - FRED PCE/PCEC96（毎月月末 8:30 ET）

    キャッシュ方式: 発表日時ベース判定
    - 小売売上高発表: 毎月中旬 8:30 ET
    - CARTS発表: 毎月第1木曜日（予備版）/ 第2金曜日（確定版） 8:30 ET
    - Affinity Spend: 不定期（1日1回更新チェック）
    - Visa支出: 発表日自動取得、不明時は1ヶ月経過後1日1回チェック
    - 自動車販売台数: FRED releases/datesから発表日自動取得
    - Redbook: 毎週火曜日 8:55 ET
    - クレジットカードローン残高: 毎週金曜日 16:15 ET
    - クレジットカードローン延滞率: 2月/5月/8月/11月の15日過ぎに1日1回チェック
    - CB消費者信頼感: 毎月最終火曜日 10:00 ET
    - CB雇用機会業況判断: 毎月最終火曜日 10:00 ET（CB消費者信頼感と同時発表）
    - ミシガン消費者信頼感: 毎月第2金曜日（速報版）/ 最終金曜日（確報版） 10:00 ET
    - 家計貯蓄率/個人所得/可処分所得/個人消費支出: BEA発表日自動取得、8:30 ET
    - 発表日時を過ぎた指標は個別サービスもforce_refreshで再取得
    """

    COUNTRY_CODE = "usa"
    CATEGORY_CODE = "consumer"

    def __init__(self):
        super().__init__()
        # 発表日時を過ぎた指標のセット（load_all実行時に判定）
        self._stale_indicators: set = set()

    # 発表時刻設定（ET）
    RETAIL_SALES_RELEASE_HOUR_ET = 8
    RETAIL_SALES_RELEASE_MINUTE_ET = 30
    CARTS_RELEASE_HOUR_ET = 8
    CARTS_RELEASE_MINUTE_ET = 30

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        """
        各指標の発表日時リストを返す

        Returns:
            - 小売売上高発表日時（8:30 ET）
            - CARTS発表日時（8:30 ET）
        """
        release_times = []

        # 小売売上高発表日時
        retail_release = self._get_retail_sales_release_datetime()
        if retail_release:
            release_times.append(retail_release)

        # CARTS発表日時
        carts_release = self._get_carts_release_datetime()
        if carts_release:
            release_times.append(carts_release)

        return release_times

    def _get_retail_sales_release_datetime(self) -> Optional[datetime]:
        """
        小売売上高の発表日時を取得

        Returns:
            発表日時（JST）、取得できない場合はNone
        """
        try:
            from services.usa.retail_sales_service import retail_sales_service

            # サービスからnext_releaseを取得（キャッシュから軽量に取得）
            data = retail_sales_service.get_retail_sales_data()
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
                self.RETAIL_SALES_RELEASE_HOUR_ET,
                self.RETAIL_SALES_RELEASE_MINUTE_ET,
                tzinfo=ET
            )
            release_jst = release_et.astimezone(JST)

            return release_jst

        except Exception as e:
            print(f"Error getting Retail Sales release datetime: {e}")
            return None

    def _get_carts_release_datetime(self) -> Optional[datetime]:
        """
        CARTSの発表日時を取得

        Returns:
            発表日時（JST）、取得できない場合はNone
        """
        try:
            from services.usa.carts_service import carts_service

            # サービスからnext_releaseを取得（キャッシュから軽量に取得）
            next_release = carts_service._get_next_release()

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
                self.CARTS_RELEASE_HOUR_ET,
                self.CARTS_RELEASE_MINUTE_ET,
                tzinfo=ET
            )
            release_jst = release_et.astimezone(JST)

            return release_jst

        except Exception as e:
            print(f"Error getting CARTS release datetime: {e}")
            return None

    def _get_visa_spending_release_datetime(self) -> Optional[datetime]:
        """Visa支出の発表日時を取得"""
        from services.usa.visa_spending_service import visa_spending_service
        return self._get_release_datetime_from_service(
            visa_spending_service.get_visa_spending_data,
            release_hour_et=8, release_minute_et=30,
            indicator_name="Visa Spending"
        )

    def _get_vehicle_sales_release_datetime(self) -> Optional[datetime]:
        """自動車販売台数の発表日時を取得"""
        from services.usa.total_vehicle_sales_service import total_vehicle_sales_service
        return self._get_release_datetime_from_service(
            total_vehicle_sales_service.get_total_vehicle_sales_data,
            release_hour_et=8, release_minute_et=30,
            indicator_name="Total Vehicle Sales"
        )

    def _get_redbook_release_datetime(self) -> Optional[datetime]:
        """Redbookの発表日時を取得"""
        from services.usa.redbook_service import redbook_service
        return self._get_release_datetime_from_service(
            redbook_service.get_redbook_data,
            release_hour_et=8, release_minute_et=55,
            indicator_name="Redbook"
        )

    def _get_consumer_credit_release_datetime(self) -> Optional[datetime]:
        """クレジットカードローン残高の発表日時を取得"""
        from services.usa.consumer_credit_service import consumer_credit_service
        return self._get_release_datetime_from_service(
            consumer_credit_service.get_consumer_credit_data,
            release_hour_et=16, release_minute_et=15,
            indicator_name="Consumer Credit"
        )

    def _get_delinquency_rate_release_datetime(self) -> Optional[datetime]:
        """クレジットカードローン延滞率の発表日時を取得"""
        from services.usa.delinquency_rate_service import delinquency_rate_service
        return self._get_release_datetime_from_service(
            delinquency_rate_service.get_delinquency_rate_data,
            release_hour_et=10, release_minute_et=0,
            indicator_name="Delinquency Rate"
        )

    def _get_cb_consumer_confidence_release_datetime(self) -> Optional[datetime]:
        """CB消費者信頼感の発表日時を取得"""
        from services.usa.cb_consumer_confidence_service import cb_consumer_confidence_service
        return self._get_release_datetime_from_service(
            cb_consumer_confidence_service.get_cb_consumer_confidence_data,
            release_hour_et=10, release_minute_et=0,
            indicator_name="CB Consumer Confidence"
        )

    def _get_michigan_consumer_sentiment_release_datetime(self) -> Optional[datetime]:
        """ミシガン消費者信頼感の発表日時を取得"""
        from services.usa.michigan_consumer_sentiment_service import michigan_consumer_sentiment_service
        return self._get_release_datetime_from_service(
            michigan_consumer_sentiment_service.get_michigan_consumer_sentiment_data,
            release_hour_et=10, release_minute_et=0,
            indicator_name="Michigan Consumer Sentiment"
        )

    def _get_personal_saving_rate_release_datetime(self) -> Optional[datetime]:
        """家計貯蓄率の発表日時を取得"""
        from services.usa.personal_saving_rate_service import personal_saving_rate_service
        return self._get_release_datetime_from_service(
            personal_saving_rate_service.get_personal_saving_rate_data,
            release_hour_et=8, release_minute_et=30,
            indicator_name="Personal Saving Rate"
        )

    def _detect_stale_indicators(self, last_updated: Optional[str]) -> set:
        """
        発表日時を過ぎた指標を検出（並列実行）

        Args:
            last_updated: ダッシュボードキャッシュのlast_updated（ISO形式）

        Returns:
            発表日時を過ぎた指標名のセット
        """
        if last_updated is None:
            return {"all"}

        try:
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 並列で発表日時を取得
            stale = set()
            check_results = {}

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {
                    executor.submit(self._get_retail_sales_release_datetime): "retail",
                    executor.submit(self._get_carts_release_datetime): "carts",
                    executor.submit(self._get_visa_spending_release_datetime): "visa_spending",
                    executor.submit(self._get_vehicle_sales_release_datetime): "total_vehicle_sales",
                    executor.submit(self._get_redbook_release_datetime): "redbook",
                    executor.submit(self._get_consumer_credit_release_datetime): "consumer_credit",
                    executor.submit(self._get_delinquency_rate_release_datetime): "delinquency_rate",
                    executor.submit(self._get_cb_consumer_confidence_release_datetime): "cb_consumer_confidence",
                    executor.submit(self._get_michigan_consumer_sentiment_release_datetime): "michigan_consumer_sentiment",
                    executor.submit(self._get_personal_saving_rate_release_datetime): "bea_personal_income",
                }

                for future in as_completed(futures):
                    key = futures[future]
                    try:
                        check_results[key] = future.result()
                    except Exception:
                        check_results[key] = None

            # 結果を判定
            def is_stale(release_dt):
                return release_dt and last_updated_dt < release_dt <= now

            # 小売売上高・コントロールグループ（同時発表）
            if is_stale(check_results.get("retail")):
                stale.add("retail_sales")
                stale.add("retail_control")

            # CARTS
            if is_stale(check_results.get("carts")):
                stale.add("carts")

            # Visa支出
            if is_stale(check_results.get("visa_spending")):
                stale.add("visa_spending")

            # 自動車販売台数
            if is_stale(check_results.get("total_vehicle_sales")):
                stale.add("total_vehicle_sales")

            # Redbook
            if is_stale(check_results.get("redbook")):
                stale.add("redbook")

            # クレジットカードローン残高
            if is_stale(check_results.get("consumer_credit")):
                stale.add("consumer_credit")

            # クレジットカードローン延滞率
            if is_stale(check_results.get("delinquency_rate")):
                stale.add("delinquency_rate")

            # CB消費者信頼感
            if is_stale(check_results.get("cb_consumer_confidence")):
                stale.add("cb_consumer_confidence")
                stale.add("cb_jobs_labor")  # 同時発表

            # ミシガン消費者信頼感
            if is_stale(check_results.get("michigan_consumer_sentiment")):
                stale.add("michigan_consumer_sentiment")

            # 家計貯蓄率/個人所得/可処分所得/個人消費支出（毎月月末、同時発表）
            if is_stale(check_results.get("bea_personal_income")):
                stale.add("personal_saving_rate")
                stale.add("personal_income")
                stale.add("disposable_income")
                stale.add("pce")

            if stale:
                print(f"[stale] Detected stale indicators: {stale}")

            return stale

        except Exception as e:
            print(f"Error detecting stale indicators: {e}")
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
        全消費データを並列で取得

        Returns:
            {
                "retail_sales": {...},
                "retail_control": {...},
                "carts": {...},
                "affinity_spend": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.usa.retail_sales_service import retail_sales_service
        from services.usa.retail_control_service import retail_control_service
        from services.usa.carts_service import carts_service
        from services.usa.affinity_spend_service import affinity_spend_service
        from services.usa.visa_spending_service import visa_spending_service
        from services.usa.total_vehicle_sales_service import total_vehicle_sales_service
        from services.usa.redbook_service import redbook_service
        from services.usa.consumer_credit_service import consumer_credit_service
        from services.usa.delinquency_rate_service import delinquency_rate_service
        from services.usa.cb_consumer_confidence_service import cb_consumer_confidence_service
        from services.usa.cb_jobs_labor_differential_service import cb_jobs_labor_differential_service
        from services.usa.michigan_consumer_sentiment_service import michigan_consumer_sentiment_service
        from services.usa.personal_saving_rate_service import personal_saving_rate_service
        from services.usa.personal_income_service import personal_income_service
        from services.usa.disposable_income_service import disposable_income_service
        from services.usa.pce_service import pce_service
        from services.usa.unemployment_rate_service import unemployment_rate_service
        from services.usa.advance_real_retail_sales_service import advance_real_retail_sales_service

        result = {
            "retail_sales": None,
            "retail_control": None,
            "advance_real_retail_sales": None,
            "carts": None,
            "affinity_spend": None,
            "visa_spending": None,
            "total_vehicle_sales": None,
            "redbook": None,
            "consumer_credit": None,
            "delinquency_rate": None,
            "cb_consumer_confidence": None,
            "cb_jobs_labor": None,
            "unemployment_rate": None,
            "michigan_consumer_sentiment": None,
            "personal_saving_rate": None,
            "personal_income": None,
            "disposable_income": None,
            "pce": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=19) as executor:
            futures = {
                executor.submit(self._get_retail_sales, retail_sales_service): "retail_sales",
                executor.submit(self._get_retail_control, retail_control_service): "retail_control",
                executor.submit(self._get_advance_real_retail_sales, advance_real_retail_sales_service): "advance_real_retail_sales",
                executor.submit(self._get_carts, carts_service): "carts",
                executor.submit(self._get_affinity_spend, affinity_spend_service): "affinity_spend",
                executor.submit(self._get_visa_spending, visa_spending_service): "visa_spending",
                executor.submit(self._get_total_vehicle_sales, total_vehicle_sales_service): "total_vehicle_sales",
                executor.submit(self._get_redbook, redbook_service): "redbook",
                executor.submit(self._get_consumer_credit, consumer_credit_service): "consumer_credit",
                executor.submit(self._get_delinquency_rate, delinquency_rate_service): "delinquency_rate",
                executor.submit(self._get_cb_consumer_confidence, cb_consumer_confidence_service): "cb_consumer_confidence",
                executor.submit(self._get_cb_jobs_labor, cb_jobs_labor_differential_service): "cb_jobs_labor",
                executor.submit(self._get_unemployment_rate, unemployment_rate_service): "unemployment_rate",
                executor.submit(self._get_michigan_consumer_sentiment, michigan_consumer_sentiment_service): "michigan_consumer_sentiment",
                executor.submit(self._get_personal_saving_rate, personal_saving_rate_service): "personal_saving_rate",
                executor.submit(self._get_personal_income, personal_income_service): "personal_income",
                executor.submit(self._get_disposable_income, disposable_income_service): "disposable_income",
                executor.submit(self._get_pce, pce_service): "pce",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_retail_sales(self, service) -> Optional[dict]:
        """小売売上高データを取得"""
        try:
            force_refresh = self._should_force_refresh("retail_sales")
            response = service.get_retail_sales_data(force_refresh=force_refresh)
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
            print(f"Error getting Retail Sales data: {e}")
            return None

    def _get_retail_control(self, service) -> Optional[dict]:
        """コントロールグループデータを取得"""
        try:
            force_refresh = self._should_force_refresh("retail_control")
            response = service.get_retail_control_data(force_refresh=force_refresh)
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting Retail Control data: {e}")
            return None

    def _get_advance_real_retail_sales(self, service) -> Optional[dict]:
        """実質小売売上高データを取得"""
        try:
            force_refresh = self._should_force_refresh("retail_sales")  # 小売売上高と同時発表
            response = service.get_advance_real_retail_sales_data(force_refresh=force_refresh)
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
            print(f"Error getting Advance Real Retail Sales data: {e}")
            return None

    def _get_carts(self, service) -> Optional[dict]:
        """CARTSデータを取得"""
        try:
            force_refresh = self._should_force_refresh("carts")
            response = service.get_carts_data(force_refresh=force_refresh)

            weekly_data = response.get("weekly", {})
            price_data = response.get("price", {})

            return {
                "weekly": {
                    "data": weekly_data.get("data", []),
                    "latest": weekly_data.get("latest"),
                },
                "price": {
                    "data": price_data.get("data", []),
                    "latest": price_data.get("latest"),
                },
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting CARTS data: {e}")
            return None

    def _get_affinity_spend(self, service) -> Optional[dict]:
        """Affinityカード支出データを取得"""
        try:
            force_refresh = self._should_force_refresh("affinity_spend")
            response = service.get_affinity_spend_data(force_refresh=force_refresh)
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "latest": response.get("latest"),
                "last_commit": response.get("last_commit"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting Affinity Spend data: {e}")
            return None

    def _get_visa_spending(self, service) -> Optional[dict]:
        """Visa支出モメンタム指数データを取得"""
        try:
            force_refresh = self._should_force_refresh("visa_spending")
            response = service.get_visa_spending_data(force_refresh=force_refresh)
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
            print(f"Error getting Visa Spending data: {e}")
            return None

    def _get_total_vehicle_sales(self, service) -> Optional[dict]:
        """自動車販売台数データを取得"""
        try:
            force_refresh = self._should_force_refresh("total_vehicle_sales")
            response = service.get_total_vehicle_sales_data(force_refresh=force_refresh)
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
            print(f"Error getting Total Vehicle Sales data: {e}")
            return None

    def _get_redbook(self, service) -> Optional[dict]:
        """Redbookデータを取得"""
        try:
            force_refresh = self._should_force_refresh("redbook")
            response = service.get_redbook_data(force_refresh=force_refresh)
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
            print(f"Error getting Redbook data: {e}")
            return None

    def _get_consumer_credit(self, service) -> Optional[dict]:
        """クレジットカードローン残高データを取得"""
        try:
            force_refresh = self._should_force_refresh("consumer_credit")
            response = service.get_consumer_credit_data(force_refresh=force_refresh)
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
            print(f"Error getting Consumer Credit data: {e}")
            return None

    def _get_delinquency_rate(self, service) -> Optional[dict]:
        """クレジットカードローン延滞率データを取得"""
        try:
            force_refresh = self._should_force_refresh("delinquency_rate")
            response = service.get_delinquency_rate_data(force_refresh=force_refresh)
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
            print(f"Error getting Delinquency Rate data: {e}")
            return None

    def _get_cb_consumer_confidence(self, service) -> Optional[dict]:
        """CB消費者信頼感データを取得"""
        try:
            force_refresh = self._should_force_refresh("cb_consumer_confidence")
            response = service.get_cb_consumer_confidence_data(force_refresh=force_refresh)
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
            print(f"Error getting CB Consumer Confidence data: {e}")
            return None

    def _get_cb_jobs_labor(self, service) -> Optional[dict]:
        """CB雇用機会業況判断データを取得"""
        try:
            force_refresh = self._should_force_refresh("cb_jobs_labor")
            response = service.get_jobs_labor_data(force_refresh=force_refresh)
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
            print(f"Error getting CB Jobs Labor data: {e}")
            return None

    def _get_unemployment_rate(self, service) -> Optional[dict]:
        """失業率データを取得（CB雇用機会業況判断チャート用）"""
        try:
            response = service.get_unemployment_rate_data(force_refresh=False)
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
            print(f"Error getting Unemployment Rate data: {e}")
            return None

    def _get_michigan_consumer_sentiment(self, service) -> Optional[dict]:
        """ミシガン消費者信頼感データを取得"""
        try:
            force_refresh = self._should_force_refresh("michigan_consumer_sentiment")
            response = service.get_michigan_consumer_sentiment_data(force_refresh=force_refresh)
            data = response.get("data", [])
            if not data:
                return None
            return {
                "data": data,
                "components": response.get("components", []),
                "latest": response.get("latest"),
                "latest_components": response.get("latest_components"),
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting Michigan Consumer Sentiment data: {e}")
            return None

    def _get_personal_saving_rate(self, service) -> Optional[dict]:
        """家計貯蓄率データを取得"""
        try:
            force_refresh = self._should_force_refresh("personal_saving_rate")
            response = service.get_personal_saving_rate_data(force_refresh=force_refresh)
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
            print(f"Error getting Personal Saving Rate data: {e}")
            return None

    def _get_personal_income(self, service) -> Optional[dict]:
        """個人所得データを取得"""
        try:
            force_refresh = self._should_force_refresh("personal_income")
            response = service.get_personal_income_data(force_refresh=force_refresh)
            return {
                "nominal": response.get("nominal"),
                "real": response.get("real"),
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting Personal Income data: {e}")
            return None

    def _get_disposable_income(self, service) -> Optional[dict]:
        """可処分所得データを取得"""
        try:
            force_refresh = self._should_force_refresh("disposable_income")
            response = service.get_disposable_income_data(force_refresh=force_refresh)
            return {
                "nominal": response.get("nominal"),
                "real": response.get("real"),
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting Disposable Income data: {e}")
            return None

    def _get_pce(self, service) -> Optional[dict]:
        """個人消費支出データを取得"""
        try:
            force_refresh = self._should_force_refresh("pce")
            response = service.get_pce_data(force_refresh=force_refresh)
            return {
                "nominal": response.get("nominal"),
                "real": response.get("real"),
                "next_release": response.get("next_release"),
                "last_updated": response.get("last_updated")
            }
        except Exception as e:
            print(f"Error getting PCE data: {e}")
            return None

    def invalidate_cache(self) -> bool:
        """
        キャッシュを無効化（ダッシュボード + 個別サービス）
        """
        from services.usa.retail_sales_service import retail_sales_service
        from services.usa.retail_control_service import retail_control_service
        from services.usa.advance_real_retail_sales_service import advance_real_retail_sales_service
        from services.usa.carts_service import carts_service
        from services.usa.affinity_spend_service import affinity_spend_service
        from services.usa.visa_spending_service import visa_spending_service
        from services.usa.total_vehicle_sales_service import total_vehicle_sales_service
        from services.usa.redbook_service import redbook_service
        from services.usa.consumer_credit_service import consumer_credit_service
        from services.usa.delinquency_rate_service import delinquency_rate_service
        from services.usa.cb_consumer_confidence_service import cb_consumer_confidence_service
        from services.usa.cb_jobs_labor_differential_service import cb_jobs_labor_differential_service
        from services.usa.michigan_consumer_sentiment_service import michigan_consumer_sentiment_service
        from services.usa.personal_saving_rate_service import personal_saving_rate_service
        from services.usa.personal_income_service import personal_income_service
        from services.usa.disposable_income_service import disposable_income_service
        from services.usa.pce_service import pce_service

        # 全サービスのキャッシュを無効化
        services = [
            (retail_sales_service, "Retail Sales"),
            (retail_control_service, "Retail Control"),
            (advance_real_retail_sales_service, "Advance Real Retail Sales"),
            (carts_service, "CARTS"),
            (affinity_spend_service, "Affinity Spend"),
            (visa_spending_service, "Visa Spending"),
            (total_vehicle_sales_service, "Total Vehicle Sales"),
            (redbook_service, "Redbook"),
            (consumer_credit_service, "Consumer Credit"),
            (delinquency_rate_service, "Delinquency Rate"),
            (cb_consumer_confidence_service, "CB Consumer Confidence"),
            (cb_jobs_labor_differential_service, "CB Jobs Labor Differential"),
            (michigan_consumer_sentiment_service, "Michigan Consumer Sentiment"),
            (personal_saving_rate_service, "Personal Saving Rate"),
            (personal_income_service, "Personal Income"),
            (disposable_income_service, "Disposable Income"),
            (pce_service, "PCE"),
        ]
        self._invalidate_service_caches(services)

        # 親クラスのinvalidate_cacheを呼び出し
        return super().invalidate_cache()
