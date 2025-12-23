"""
米国消費ダッシュボードローダー
小売売上高 + コントロールグループ + CARTS + Affinity Spend + Visa支出 + 自動車販売台数 + Redbook + クレジットカードローン残高 を一括取得

キャッシュ更新判定: 発表日時ベース方式
- 発表日: Census.gov / Chicago Fed / GitHubから自動取得（next_release）
- 発表時刻: 8:30 ET（小売売上高・CARTS）、不定期（Affinity Spend）
- Visa支出: 発表日自動取得（不明時は1ヶ月経過後1日1回チェック）
- 自動車販売台数: FRED releases/datesから発表日自動取得
- Redbook: 毎週火曜日 8:55 ET発表
- クレジットカードローン残高: 毎週金曜日 16:15 ET発表（H.8）
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
    - retail_control: コントロールグループ - Investing.com（毎月中旬 8:30 ET）
    - carts: シカゴ連銀小売指数 - Chicago Fed CARTS（毎月第1木曜/第2金曜 8:30 ET）
    - affinity_spend: Affinityカード支出 - Opportunity Insights（不定期、GitHubコミットで判定）
    - visa_spending: Visa支出モメンタム指数 - FRED VISASMIHSA（毎月更新）
    - total_vehicle_sales: 自動車販売台数 - FRED TOTALSA（毎月更新）
    - redbook: Redbook小売売上高指数 - Investing.com（毎週火曜日 8:55 ET）
    - consumer_credit: クレジットカードローン残高 - FRED CCLACBW027SBOG（毎週金曜日 16:15 ET）

    キャッシュ方式: 発表日時ベース判定
    - 小売売上高発表: 毎月中旬 8:30 ET
    - CARTS発表: 毎月第1木曜日（予備版）/ 第2金曜日（確定版） 8:30 ET
    - Affinity Spend: 不定期（1日1回更新チェック）
    - Visa支出: 発表日自動取得、不明時は1ヶ月経過後1日1回チェック
    - 自動車販売台数: FRED releases/datesから発表日自動取得
    - Redbook: 毎週火曜日 8:55 ET
    - クレジットカードローン残高: 毎週金曜日 16:15 ET
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
        try:
            from services.usa.visa_spending_service import visa_spending_service
            data = visa_spending_service.get_visa_spending_data()
            next_release = data.get("next_release")
            if next_release:
                date_str = next_release.get("date")
                if date_str:
                    base_date = datetime.strptime(date_str, "%Y-%m-%d")
                    # 発表時刻は不明なので8:30 ETと仮定
                    release_et = datetime(
                        base_date.year, base_date.month, base_date.day,
                        8, 30, tzinfo=ET
                    )
                    return release_et.astimezone(JST)
        except Exception:
            pass
        return None

    def _get_vehicle_sales_release_datetime(self) -> Optional[datetime]:
        """自動車販売台数の発表日時を取得"""
        try:
            from services.usa.total_vehicle_sales_service import total_vehicle_sales_service
            data = total_vehicle_sales_service.get_total_vehicle_sales_data()
            next_release = data.get("next_release")
            if next_release:
                date_str = next_release.get("date")
                if date_str:
                    base_date = datetime.strptime(date_str, "%Y-%m-%d")
                    release_et = datetime(
                        base_date.year, base_date.month, base_date.day,
                        8, 30, tzinfo=ET
                    )
                    return release_et.astimezone(JST)
        except Exception:
            pass
        return None

    def _get_redbook_release_datetime(self) -> Optional[datetime]:
        """Redbookの発表日時を取得"""
        try:
            from services.usa.redbook_service import redbook_service
            data = redbook_service.get_redbook_data()
            next_release = data.get("next_release")
            if next_release:
                date_str = next_release.get("date")
                if date_str:
                    base_date = datetime.strptime(date_str, "%Y-%m-%d")
                    # Redbookは8:55 ET発表
                    release_et = datetime(
                        base_date.year, base_date.month, base_date.day,
                        8, 55, tzinfo=ET
                    )
                    return release_et.astimezone(JST)
        except Exception:
            pass
        return None

    def _get_consumer_credit_release_datetime(self) -> Optional[datetime]:
        """クレジットカードローン残高の発表日時を取得"""
        try:
            from services.usa.consumer_credit_service import consumer_credit_service
            data = consumer_credit_service.get_consumer_credit_data()
            next_release = data.get("next_release")
            if next_release:
                date_str = next_release.get("date")
                if date_str:
                    base_date = datetime.strptime(date_str, "%Y-%m-%d")
                    # H.8は16:15 ET発表
                    release_et = datetime(
                        base_date.year, base_date.month, base_date.day,
                        16, 15, tzinfo=ET
                    )
                    return release_et.astimezone(JST)
        except Exception:
            pass
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
            return {"all"}

        try:
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 小売売上高・コントロールグループ（同時発表）
            retail_release = self._get_retail_sales_release_datetime()
            if retail_release and last_updated_dt < retail_release <= now:
                stale.add("retail_sales")
                stale.add("retail_control")
                print(f"[stale] Retail Sales release detected: {retail_release.isoformat()}")

            # CARTS
            carts_release = self._get_carts_release_datetime()
            if carts_release and last_updated_dt < carts_release <= now:
                stale.add("carts")
                print(f"[stale] CARTS release detected: {carts_release.isoformat()}")

            # Visa支出
            visa_release = self._get_visa_spending_release_datetime()
            if visa_release and last_updated_dt < visa_release <= now:
                stale.add("visa_spending")
                print(f"[stale] Visa Spending release detected: {visa_release.isoformat()}")

            # 自動車販売台数
            vehicle_release = self._get_vehicle_sales_release_datetime()
            if vehicle_release and last_updated_dt < vehicle_release <= now:
                stale.add("total_vehicle_sales")
                print(f"[stale] Vehicle Sales release detected: {vehicle_release.isoformat()}")

            # Redbook
            redbook_release = self._get_redbook_release_datetime()
            if redbook_release and last_updated_dt < redbook_release <= now:
                stale.add("redbook")
                print(f"[stale] Redbook release detected: {redbook_release.isoformat()}")

            # クレジットカードローン残高
            credit_release = self._get_consumer_credit_release_datetime()
            if credit_release and last_updated_dt < credit_release <= now:
                stale.add("consumer_credit")
                print(f"[stale] Consumer Credit release detected: {credit_release.isoformat()}")

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

        result = {
            "retail_sales": None,
            "retail_control": None,
            "carts": None,
            "affinity_spend": None,
            "visa_spending": None,
            "total_vehicle_sales": None,
            "redbook": None,
            "consumer_credit": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=9) as executor:
            futures = {
                executor.submit(self._get_retail_sales, retail_sales_service): "retail_sales",
                executor.submit(self._get_retail_control, retail_control_service): "retail_control",
                executor.submit(self._get_carts, carts_service): "carts",
                executor.submit(self._get_affinity_spend, affinity_spend_service): "affinity_spend",
                executor.submit(self._get_visa_spending, visa_spending_service): "visa_spending",
                executor.submit(self._get_total_vehicle_sales, total_vehicle_sales_service): "total_vehicle_sales",
                executor.submit(self._get_redbook, redbook_service): "redbook",
                executor.submit(self._get_consumer_credit, consumer_credit_service): "consumer_credit",
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
            response = service.get_control_group_data(force_refresh=force_refresh)
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

    def invalidate_cache(self) -> bool:
        """
        キャッシュを無効化（ダッシュボード + 個別サービス）
        """
        from services.usa.retail_sales_service import retail_sales_service
        from services.usa.retail_control_service import retail_control_service
        from services.usa.carts_service import carts_service
        from services.usa.affinity_spend_service import affinity_spend_service
        from services.usa.visa_spending_service import visa_spending_service
        from services.usa.total_vehicle_sales_service import total_vehicle_sales_service
        from services.usa.redbook_service import redbook_service
        from services.usa.consumer_credit_service import consumer_credit_service

        # 小売売上高サービスのRedisキャッシュを無効化
        try:
            retail_sales_service.invalidate_cache()
            print("Retail Sales Redis cache invalidated")
        except Exception as e:
            print(f"Error invalidating Retail Sales cache: {e}")

        # コントロールグループサービスのRedisキャッシュを無効化
        try:
            retail_control_service.invalidate_cache()
            print("Retail Control Redis cache invalidated")
        except Exception as e:
            print(f"Error invalidating Retail Control cache: {e}")

        # CARTSサービスのRedisキャッシュを無効化
        try:
            carts_service.invalidate_cache()
            print("CARTS Redis cache invalidated")
        except Exception as e:
            print(f"Error invalidating CARTS cache: {e}")

        # Affinity SpendサービスのRedisキャッシュを無効化
        try:
            affinity_spend_service.invalidate_cache()
            print("Affinity Spend Redis cache invalidated")
        except Exception as e:
            print(f"Error invalidating Affinity Spend cache: {e}")

        # Visa SpendingサービスのRedisキャッシュを無効化
        try:
            visa_spending_service.invalidate_cache()
            print("Visa Spending Redis cache invalidated")
        except Exception as e:
            print(f"Error invalidating Visa Spending cache: {e}")

        # Total Vehicle SalesサービスのRedisキャッシュを無効化
        try:
            total_vehicle_sales_service.invalidate_cache()
            print("Total Vehicle Sales Redis cache invalidated")
        except Exception as e:
            print(f"Error invalidating Total Vehicle Sales cache: {e}")

        # RedbookサービスのRedisキャッシュを無効化
        try:
            redbook_service.invalidate_cache()
            print("Redbook Redis cache invalidated")
        except Exception as e:
            print(f"Error invalidating Redbook cache: {e}")

        # Consumer CreditサービスのRedisキャッシュを無効化
        try:
            consumer_credit_service.invalidate_cache()
            print("Consumer Credit Redis cache invalidated")
        except Exception as e:
            print(f"Error invalidating Consumer Credit cache: {e}")

        # 親クラスのinvalidate_cacheを呼び出し
        return super().invalidate_cache()
