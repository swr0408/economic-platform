"""
FMP発表日ベースの経済指標スケジューラー

FMP Economic Calendar APIから発表日を取得し、発表時刻の1分後にデータを取得する。
週1回、2ヶ月先までの発表日を取得してスケジュールを更新。

ハイブリッド方式:
1. メイン: FMP発表日の1分後にピンポイント取得
2. バックアップ: 週1回の発表日リフレッシュ（変更検知・漏れ防止）
"""

import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Set
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

try:
    from services.calendar.fmp_service import fmp_service
    from services.calendar.calendar_repository import calendar_repository
    from core.database import SessionLocal
except ImportError:
    from backend.services.calendar.fmp_service import fmp_service
    from backend.services.calendar.calendar_repository import calendar_repository
    from backend.core.database import SessionLocal


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")

# 発表後の更新設定
UPDATE_DELAY_MINUTES = 1  # 発表から1分後に取得開始
UPDATE_ITERATIONS = 3     # 3回取得（3分方式）
UPDATE_INTERVAL_SECONDS = 60

# FMP発表日取得設定
FUTURE_DAYS = 60  # 2ヶ月先まで取得

# 対象指標の設定
# fmp_event: FMP APIのeventパラメータに渡す値（完全一致検索用）
# fmp_event_pattern: イベント名のパターンマッチ用（部分一致）
# country: FMP APIの国コード
# FMP国コードからダッシュボードAPI用の国名へのマッピング
FMP_COUNTRY_TO_DASHBOARD = {
    "US": "usa",
    "EU": "eurozone",
    "DE": "eurozone",  # ドイツはユーロ圏ダッシュボードに含まれる
    "JP": "japan",
    "GB": "uk",
}

FMP_INDICATOR_CONFIGS = [
    # ========== USA ==========
    {
        "name_ja": "ISM製造業景況指数",
        "fmp_event": "ISM Manufacturing PMI",
        "fmp_event_pattern": "ISM Manufacturing PMI",
        "country": "US",
        "category": "economy",
        "service_module": "services.usa.ism_manufacturing_service",
        "service_instance": "ism_manufacturing_service",
        "fetch_method": "get_ism_manufacturing_data",
    },
    {
        "name_ja": "ISM非製造業景況指数",
        "fmp_event": "ISM Services PMI",
        "fmp_event_pattern": "ISM Services PMI",
        "country": "US",
        "category": "economy",
        "service_module": "services.usa.ism_non_manufacturing_service",
        "service_instance": "ism_non_manufacturing_service",
        "fetch_method": "get_ism_non_manufacturing_data",
    },
    {
        "name_ja": "CB消費者信頼感指数",
        "fmp_event": "CB Consumer Confidence",
        "fmp_event_pattern": "CB Consumer Confidence",
        "country": "US",
        "category": "consumer",
        "service_module": "services.usa.cb_consumer_confidence_service",
        "service_instance": "cb_consumer_confidence_service",
        "fetch_method": "get_cb_consumer_confidence_data",
    },
    {
        "name_ja": "Challenger人員削減数",
        "fmp_event": "Challenger Job Cuts",
        "fmp_event_pattern": "Challenger Job Cuts",
        "country": "US",
        "category": "employment",
        "service_module": "services.usa.challenger_job_cuts_service",
        "service_instance": "challenger_job_cuts_service",
        "fetch_method": "get_challenger_data",
    },
    {
        "name_ja": "レッドブック",
        "fmp_event": "Redbook YoY",
        "fmp_event_pattern": "Redbook",
        "country": "US",
        "category": "consumer",
        "service_module": "services.usa.redbook_service",
        "service_instance": "redbook_service",
        "fetch_method": "get_redbook_data",
    },
    {
        "name_ja": "コントロールグループ",
        "fmp_event": "Retail Sales Ex Gas/Autos MoM",
        "fmp_event_pattern": "Retail Sales",
        "country": "US",
        "category": "consumer",
        "service_module": "services.usa.retail_control_service",
        "service_instance": "retail_control_service",
        "fetch_method": "get_retail_control_data",
    },
    {
        "name_ja": "輸入物価指数/輸出物価指数",
        "fmp_event": "Import Price Index MoM",
        "fmp_event_pattern": "Import Price",
        "country": "US",
        "category": "inflation",
        "service_module": "services.usa.import_export_price_service",
        "service_instance": "import_export_price_service",
        "fetch_method": "get_import_export_price_data",
    },
    {
        "name_ja": "S&P Global PMI（米国）",
        "fmp_event": "S&P Global Manufacturing PMI",
        "fmp_event_pattern": "S&P Global",
        "country": "US",
        "category": "economy",
        "service_module": "services.usa.sp_pmi_service",
        "service_instance": "sp_pmi_service",
        "fetch_method": "get_sp_pmi_data",
    },
    {
        # FMP: "Atlanta Fed GDPNow" (us_gdonow mapping)
        "name_ja": "GDPNow（アトランタ連銀）",
        "fmp_event": "Atlanta Fed GDPNow",
        "fmp_event_pattern": "Atlanta Fed GDPNow",
        "country": "US",
        "category": "economy",
        "service_module": "services.usa.gdpnow_service",
        "service_instance": "gdpnow_service",
        "fetch_method": "get_gdpnow_data",
    },
    {
        # FMP: "Inflation Rate MoM/YoY", "CPI" (us_cpi mapping)
        # 同時更新: Median CPI（クリーブランド連銀）
        "name_ja": "CPI（消費者物価指数）",
        "fmp_event": "Inflation Rate MoM",
        "fmp_event_pattern": "Inflation Rate",
        "country": "US",
        "category": "inflation",
        "service_module": "services.usa.cpi_service",
        "service_instance": "cpi_service",
        "fetch_method": "get_cpi_data",
        "related_services": [
            {
                "service_module": "services.usa.median_cpi_service",
                "service_instance": "median_cpi_service",
                "fetch_method": "get_median_cpi_data",
            },
        ],
    },
    {
        # FMP: "PCE Price Index MoM/YoY" (pce mapping)
        # 同時更新: Trimmed Mean PCE（ダラス連銀）
        "name_ja": "PCE（個人消費支出）",
        "fmp_event": "PCE Price Index MoM",
        "fmp_event_pattern": "PCE Price Index",
        "country": "US",
        "category": "inflation",
        "service_module": "services.usa.pce_service",
        "service_instance": "pce_service",
        "fetch_method": "get_pce_data",
        "related_services": [
            {
                "service_module": "services.usa.trimmed_mean_pce_service",
                "service_instance": "trimmed_mean_pce_service",
                "fetch_method": "get_trimmed_mean_pce_data",
            },
        ],
    },
    {
        # FMP: "Unemployment Rate" (unemployment_rate mapping)
        # 同時更新: Sahm Rule
        "name_ja": "失業率（米国）",
        "fmp_event": "Unemployment Rate",
        "fmp_event_pattern": "Unemployment Rate",
        "country": "US",
        "category": "employment",
        "service_module": "services.usa.unemployment_service",
        "service_instance": "unemployment_service",
        "fetch_method": "get_unemployment_data",
        "related_services": [
            {
                "service_module": "services.usa.sahm_rule_service",
                "service_instance": "sahm_rule_service",
                "fetch_method": "get_sahm_rule_data",
            },
        ],
    },
    {
        # FMP: "Retail Sales MoM/YoY" (retail_sales mapping)
        # 同時更新: 実質小売売上高
        "name_ja": "小売売上高（米国）",
        "fmp_event": "Retail Sales MoM",
        "fmp_event_pattern": "Retail Sales",
        "country": "US",
        "category": "consumer",
        "service_module": "services.usa.retail_sales_service",
        "service_instance": "retail_sales_service",
        "fetch_method": "get_retail_sales_data",
        "related_services": [
            {
                "service_module": "services.usa.advance_real_retail_sales_service",
                "service_instance": "advance_real_retail_sales_service",
                "fetch_method": "get_advance_real_retail_sales_data",
            },
        ],
    },
    {
        "name_ja": "週間原油在庫（EIA）",
        "fmp_event": "EIA Crude Oil Stocks Change",
        "fmp_event_pattern": "EIA Crude Oil Stocks",
        "country": "US",
        "category": "energy",
        "service_module": "services.market.weekly_crude_oil_inventories_service",
        "service_instance": "weekly_crude_oil_inventories_service",
        "fetch_method": "get_data",
    },
    {
        "name_ja": "ガソリン在庫/製油稼働率（EIA）",
        "fmp_event": "EIA Gasoline Production Change",
        "fmp_event_pattern": "EIA Gasoline Production",
        "country": "US",
        "category": "energy",
        "service_module": "services.market.us_gasoline_inventories_refinery_utilization_service",
        "service_instance": "us_gasoline_inventories_refinery_utilization_service",
        "fetch_method": "get_data",
    },
    # ========== Eurozone ==========
    {
        "name_ja": "ユーロ圏PMI（HCOB）",
        "fmp_event": "HCOB Manufacturing PMI",
        "fmp_event_pattern": "HCOB",
        "country": "EU",
        "category": "economy",
        "service_module": "services.eurozone.eu_pmi_service",
        "service_instance": "eu_pmi_service",
        "fetch_method": "get_eurozone_pmi_data",
    },
    {
        "name_ja": "ドイツPMI（HCOB）",
        "fmp_event": "HCOB Manufacturing PMI",
        "fmp_event_pattern": "HCOB",
        "country": "DE",
        "category": "economy",
        "service_module": "services.eurozone.germany_pmi_service",
        "service_instance": "germany_pmi_service",
        "fetch_method": "get_germany_pmi_data",
    },
    {
        "name_ja": "フランスPMI（HCOB）",
        "fmp_event": "HCOB Manufacturing PMI",
        "fmp_event_pattern": "HCOB",
        "country": "FR",
        "category": "economy",
        "service_module": "services.eurozone.france_pmi_service",
        "service_instance": "france_pmi_service",
        "fetch_method": "get_france_pmi_data",
    },
    {
        "name_ja": "M3マネーサプライ",
        "fmp_event": "M3 Money Supply YoY",
        "fmp_event_pattern": "M3 Money Supply",
        "country": "EU",
        "category": "policy",
        "service_module": "services.eurozone.ecb_m3_service",
        "service_instance": "ecb_m3_service",
        "fetch_method": "get_ecb_m3_data",
    },
    {
        "name_ja": "ドイツ鉱工業生産",
        "fmp_event": "Industrial Production MoM",
        "fmp_event_pattern": "Industrial Production",
        "country": "DE",
        "category": "economy",
        "service_module": "services.eurozone.germany_industrial_production_service",
        "service_instance": "germany_industrial_production_service",
        "fetch_method": "get_germany_industrial_production_data",
    },
    {
        "name_ja": "ドイツ製造業受注",
        "fmp_event": "Factory Orders MoM",
        "fmp_event_pattern": "Factory Orders",
        "country": "DE",
        "category": "economy",
        "service_module": "services.eurozone.germany_factory_orders_service",
        "service_instance": "germany_factory_orders_service",
        "fetch_method": "get_germany_factory_orders_data",
    },
    {
        "name_ja": "ZEW景況感指数",
        "fmp_event": "ZEW Economic Sentiment Index",
        "fmp_event_pattern": "ZEW",
        "country": "DE",
        "category": "economy",
        "service_module": "services.eurozone.zew_economic_sentiment_service",
        "service_instance": "zew_economic_sentiment_service",
        "fetch_method": "get_zew_economic_sentiment_data",
    },
    {
        "name_ja": "Ifo景況感指数",
        "fmp_event": "Ifo Business Climate",
        "fmp_event_pattern": "Ifo",
        "country": "DE",
        "category": "economy",
        "service_module": "services.eurozone.ifo_business_climate_service",
        "service_instance": "ifo_business_climate_service",
        "fetch_method": "get_ifo_business_climate_data",
    },
    # ========== Japan ==========
    {
        "name_ja": "日本PMI（じぶん銀行）",
        "fmp_event": "Jibun Bank Manufacturing PMI",
        "fmp_event_pattern": "Jibun Bank",
        "country": "JP",
        "category": "economy",
        "service_module": "services.japan.jp_pmi_service",
        "service_instance": "jp_pmi_service",
        "fetch_method": "get_jp_pmi_data",
    },
    {
        "name_ja": "日本失業率",
        "fmp_event": "Unemployment Rate",
        "fmp_event_pattern": "Unemployment Rate",
        "country": "JP",
        "category": "employment",
        "service_module": "services.japan.japan_unemployment_service",
        "service_instance": "japan_unemployment_service",
        "fetch_method": "get_unemployment_data",
    },
    {
        "name_ja": "日本小売売上高",
        "fmp_event": "Retail Sales YoY",
        "fmp_event_pattern": "Retail Sales",
        "country": "JP",
        "category": "consumer",
        "service_module": "services.japan.retail_sales_service",
        "service_instance": "retail_sales_service",
        "fetch_method": "get_retail_sales_data",
    },
    {
        # FMP: "Producer Price Index MoM/YoY" (japan_cgpi mapping)
        "name_ja": "企業物価指数（CGPI）",
        "fmp_event": "Producer Price Index MoM",
        "fmp_event_pattern": "Producer Price Index",
        "country": "JP",
        "category": "price",
        "service_module": "services.japan.japan_cgpi_service",
        "service_instance": "japan_cgpi_service",
        "fetch_method": "get_cgpi_data",
        # 同時更新: 飲食料品・農林水産物、輸入/輸出物価
        "related_services": [
            {
                "service_module": "services.japan.japan_cgpi_food_agriculture_service",
                "service_instance": "japan_cgpi_food_agriculture_service",
                "fetch_method": "get_cgpi_food_agriculture_data",
            },
            {
                "service_module": "services.japan.japan_import_export_price_service",
                "service_instance": "japan_import_export_price_service",
                "fetch_method": "get_import_export_price_data",
            },
        ],
    },
    {
        # FMP: "Machinery Orders MoM/YoY" (japan_machinery_orders mapping)
        "name_ja": "機械受注",
        "fmp_event": "Machinery Orders MoM",
        "fmp_event_pattern": "Machinery Orders",
        "country": "JP",
        "category": "economy",
        "service_module": "services.japan.machinery_orders_service",
        "service_instance": "machinery_orders_service",
        "fetch_method": "get_machinery_orders_data",
    },
    {
        # FMP: "Tertiary Industry Index MoM" (japan_tertiary_industry_index mapping)
        "name_ja": "第3次産業活動指数",
        "fmp_event": "Tertiary Industry Index MoM",
        "fmp_event_pattern": "Tertiary Industry Index",
        "country": "JP",
        "category": "economy",
        "service_module": "services.japan.tertiary_industry_index_service",
        "service_instance": "tertiary_industry_index_service",
        "fetch_method": "get_tertiary_industry_index_data",
    },
    {
        # FMP: "Average Cash Earnings YoY" (japan_scheduled_wage mapping)
        "name_ja": "毎月勤労統計（現金給与総額）",
        "fmp_event": "Average Cash Earnings YoY",
        "fmp_event_pattern": "Average Cash Earnings",
        "country": "JP",
        "category": "employment",
        "service_module": "services.japan.cash_earnings_service",
        "service_instance": "cash_earnings_service",
        "fetch_method": "get_cash_earnings_data",
        # 同時更新: 実質賃金、所定内給与
        "related_services": [
            {
                "service_module": "services.japan.real_wage_service",
                "service_instance": "real_wage_service",
                "fetch_method": "get_real_wage_data",
            },
            {
                "service_module": "services.japan.scheduled_wage_service",
                "service_instance": "scheduled_wage_service",
                "fetch_method": "get_scheduled_wage_data",
            },
        ],
    },
    {
        # FMP: "Consumer Confidence" (jp_consumer_Sentiment mapping)
        "name_ja": "消費動向調査（消費者態度指数）",
        "fmp_event": "Consumer Confidence",
        "fmp_event_pattern": "Consumer Confidence",
        "country": "JP",
        "category": "consumer",
        "service_module": "services.japan.consumer_sentiment_service",
        "service_instance": "consumer_sentiment_service",
        "fetch_method": "get_consumer_sentiment_data",
    },
    {
        # FMP: "Eco Watchers Survey Current" (economy_watcher mapping)
        "name_ja": "景気ウォッチャー調査",
        "fmp_event": "Eco Watchers Survey Current",
        "fmp_event_pattern": "Eco Watchers",
        "country": "JP",
        "category": "consumer",
        "service_module": "services.japan.economy_watcher_service",
        "service_instance": "economy_watcher_service",
        "fetch_method": "get_economy_watcher_data",
    },
    # ========== UK ==========
    {
        "name_ja": "イギリスPMI（S&P Global）",
        "fmp_event": "S&P Global/CIPS Manufacturing PMI",
        "fmp_event_pattern": "S&P Global",
        "country": "GB",
        "category": "economy",
        "service_module": "services.uk.uk_pmi_service",
        "service_instance": "uk_pmi_service",
        "fetch_method": "get_uk_pmi_data",
    },
    {
        "name_ja": "BRC小売売上高",
        "fmp_event": "BRC Retail Sales Monitor YoY",
        "fmp_event_pattern": "BRC Retail Sales",
        "country": "GB",
        "category": "consumer",
        "service_module": "services.uk.brc_retail_sales_service",
        "service_instance": "brc_retail_sales_service",
        "fetch_method": "get_brc_retail_sales_data",
    },
    {
        # FMP: "Nationwide Housing Prices MoM/YoY" (nationwide_hpi mapping)
        "name_ja": "Nationwide住宅価格指数",
        "fmp_event": "Nationwide Housing Prices MoM",
        "fmp_event_pattern": "Nationwide Housing Prices",
        "country": "GB",
        "category": "housing",
        "service_module": "services.uk.nationwide_hpi_service",
        "service_instance": "nationwide_hpi_service",
        "fetch_method": "get_nationwide_hpi_data",
    },
    {
        # FMP: "BBA Mortgage Rate" (boe_mortgage_rates mapping)
        "name_ja": "BoE住宅ローン金利",
        "fmp_event": "BBA Mortgage Rate",
        "fmp_event_pattern": "BBA Mortgage Rate",
        "country": "GB",
        "category": "housing",
        "service_module": "services.uk.boe_mortgage_rates_service",
        "service_instance": "boe_mortgage_rates_service",
        "fetch_method": "get_boe_mortgage_rates_data",
    },
    {
        # FMP: "Mortgage Approvals" (boe_mortgage_lending mapping)
        "name_ja": "BoE住宅ローン承認件数",
        "fmp_event": "Mortgage Approvals",
        "fmp_event_pattern": "Mortgage Approvals",
        "country": "GB",
        "category": "housing",
        "service_module": "services.uk.boe_mortgage_lending_service",
        "service_instance": "boe_mortgage_lending_service",
        "fetch_method": "get_boe_mortgage_lending_data",
    },
]


def invalidate_dashboard_cache(country_code: str, category: str) -> bool:
    """
    ダッシュボードのRedisキャッシュを無効化

    Args:
        country_code: FMP国コード（US, EU, DE, JP, GB）
        category: カテゴリ（economy, consumer, employment, inflation, housing, policy）

    Returns:
        成功した場合True
    """
    try:
        from core.redis_client import redis_client
    except ImportError:
        from backend.core.redis_client import redis_client

    # FMP国コードからダッシュボード用の国名に変換
    dashboard_country = FMP_COUNTRY_TO_DASHBOARD.get(country_code)
    if not dashboard_country:
        print(f"[FMPScheduler] Unknown country code: {country_code}")
        return False

    cache_key = f"dashboard:{dashboard_country}:{category}:data"

    try:
        deleted = redis_client.delete(cache_key)
        if deleted:
            print(f"[FMPScheduler] Dashboard cache invalidated: {cache_key}")
        return deleted
    except Exception as e:
        print(f"[FMPScheduler] Failed to invalidate dashboard cache: {e}")
        return False


class FMPReleaseScheduler:
    """
    FMP発表日ベースの経済指標スケジューラー

    FMPから将来の発表日を取得し、各発表の1分後にデータ取得ジョブをスケジュール。
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._service_cache: Dict[str, Any] = {}
        self._scheduled_jobs: Set[str] = set()
        self._upcoming_releases: List[Dict[str, Any]] = []

    def _get_service_instance(self, config: Dict[str, Any]) -> Optional[Any]:
        """サービスインスタンスを動的にインポート"""
        import importlib

        cache_key = f"{config['service_module']}.{config['service_instance']}"

        if cache_key in self._service_cache:
            return self._service_cache[cache_key]

        module_paths = [
            f"backend.{config['service_module']}",
            config['service_module'],
        ]

        for module_path in module_paths:
            try:
                module = importlib.import_module(module_path)
                service = getattr(module, config['service_instance'])
                self._service_cache[cache_key] = service
                return service
            except (ImportError, AttributeError):
                continue

        return None

    def fetch_upcoming_releases_for_indicator(
        self,
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        特定の指標の将来の発表日をFMPから取得（eventパラメータで絞り込み）

        Args:
            config: 指標設定

        Returns:
            発表予定リスト
        """
        name_ja = config["name_ja"]
        fmp_event = config["fmp_event"]
        country = config.get("country", "US")

        today = date.today()
        end_date = today + timedelta(days=FUTURE_DAYS)

        try:
            # eventパラメータで指標を絞って取得
            events = fmp_service.fetch_calendar(
                today, end_date,
                country=country,
                event=fmp_event
            )
        except Exception as e:
            print(f"[FMPScheduler] Error fetching {name_ja}: {e}")
            return []

        releases = []
        seen_dates = set()
        now_jst = datetime.now(JST)

        for event in events:
            # 将来のイベントのみ（actualがない）
            if event.get("actual") is not None:
                continue

            datetime_raw = event.get("date", "")
            dt_utc, has_time = fmp_service.parse_datetime(datetime_raw)

            if not dt_utc:
                continue

            # 重複チェック（同日の複数イベント防止）
            date_key = dt_utc.date().isoformat()
            if date_key in seen_dates:
                continue
            seen_dates.add(date_key)

            # JSTに変換
            dt_jst = dt_utc.astimezone(JST)

            # 発表日が過去でないか確認
            if dt_jst <= now_jst:
                continue

            releases.append({
                "event_name": event.get("event", ""),
                "name_ja": name_ja,
                "datetime_utc": dt_utc,
                "datetime_jst": dt_jst,
                "has_time": has_time,
                "config": config,
                "estimate": event.get("estimate"),
            })

        return releases

    def fetch_all_upcoming_releases(self) -> List[Dict[str, Any]]:
        """
        全指標の将来の発表日を取得（各指標ごとにAPIを呼び出し）

        Returns:
            発表予定リスト [{event_name, datetime_utc, datetime_jst, config}, ...]
        """
        print(f"[FMPScheduler] Fetching upcoming releases for next {FUTURE_DAYS} days...")
        print(f"[FMPScheduler] Target indicators: {len(FMP_INDICATOR_CONFIGS)}")

        all_releases = []

        for config in FMP_INDICATOR_CONFIGS:
            releases = self.fetch_upcoming_releases_for_indicator(config)
            all_releases.extend(releases)
            if releases:
                print(f"  - {config['name_ja']}: {len(releases)} releases found")

        # 日時順にソート
        all_releases.sort(key=lambda x: x["datetime_utc"])

        print(f"[FMPScheduler] Total upcoming releases: {len(all_releases)}")
        for release in all_releases[:10]:  # 直近10件を表示
            print(f"    {release['name_ja']}: {release['datetime_jst'].strftime('%Y-%m-%d %H:%M JST')}")

        self._upcoming_releases = all_releases
        return all_releases

    def _sync_fmp_indicator_data(self, fmp_event: str, name_ja: str, country: str = "US") -> int:
        """
        FMPから特定指標の直近イベントを取得してDBに同期（eventパラメータで絞り込み）

        Args:
            fmp_event: FMP APIのeventパラメータ値
            name_ja: 指標名（ログ用）
            country: FMP APIの国コード

        Returns:
            Upsertしたレコード数
        """
        try:
            today = date.today()
            # 直近7日分を取得（発表後のactual値を拾う）
            start_date = today - timedelta(days=7)

            # eventパラメータで指標を絞って取得
            events = fmp_service.fetch_calendar(
                start_date, today,
                country=country,
                event=fmp_event
            )

            if not events:
                print(f"[FMPScheduler] No events found for: {name_ja} ({country})")
                return 0

            # 処理してDBにUpsert
            processed = [fmp_service.process_event(e) for e in events]
            count = calendar_repository.upsert_events(processed)

            print(f"[FMPScheduler] Synced {count} events for: {name_ja} ({country})")
            return count

        except Exception as e:
            print(f"[FMPScheduler] Error syncing {name_ja}: {e}")
            return 0

    async def fetch_indicator_data(
        self,
        config: Dict[str, Any],
        iteration: int = 1
    ):
        """
        指標データを取得（FMPからDB同期 → サービス経由で取得）

        Args:
            config: 指標設定
            iteration: 更新回数（1-3）
        """
        name_ja = config["name_ja"]
        fmp_event = config["fmp_event"]
        country = config.get("country", "US")

        try:
            print(f"[FMPScheduler] Fetching {name_ja} (iteration {iteration}/{UPDATE_ITERATIONS})...")

            # Step 1: FMPから最新データを取得してDBに保存（eventパラメータで絞り込み）
            synced_count = self._sync_fmp_indicator_data(fmp_event, name_ja, country)
            print(f"[FMPScheduler] DB synced: {synced_count} events")

            # Step 2: サービス経由でデータを取得（DBから読み込み）
            service = self._get_service_instance(config)
            if service is None:
                print(f"[FMPScheduler] Service not found: {config['service_module']}")
                return

            fetch_method = getattr(service, config['fetch_method'], None)
            if fetch_method is None:
                print(f"[FMPScheduler] Method not found: {config['fetch_method']}")
                return

            # Redisキャッシュを無効化して再取得
            if hasattr(service, 'invalidate_cache'):
                service.invalidate_cache()

            result = fetch_method(force_refresh=True)

            if result and not result.get("error"):
                latest = result.get("latest", {})
                latest_date = latest.get("date") if latest else "N/A"
                latest_value = latest.get("value") if latest else "N/A"
                print(f"[FMPScheduler] ✓ {name_ja}: date={latest_date}, value={latest_value}, source={result.get('source')}")

                # Step 3: 関連サービスも同時更新（related_servicesがある場合）
                related_services = config.get("related_services", [])
                for related in related_services:
                    try:
                        related_service = self._get_service_instance(related)
                        if related_service:
                            related_method = getattr(related_service, related['fetch_method'], None)
                            if related_method:
                                related_result = related_method(force_refresh=True)
                                if related_result and not related_result.get("error"):
                                    r_latest = related_result.get("latest", {})
                                    r_date = r_latest.get("date") if r_latest else "N/A"
                                    r_value = r_latest.get("value") if r_latest else "N/A"
                                    print(f"[FMPScheduler] ✓ (related) {related['service_instance']}: date={r_date}, value={r_value}")
                    except Exception as e:
                        print(f"[FMPScheduler] Error updating related service {related.get('service_instance')}: {e}")

                # Step 4: ダッシュボードキャッシュを無効化（サービスキャッシュとは別）
                category = config.get("category")
                if category:
                    invalidate_dashboard_cache(country, category)
            else:
                error = result.get("error") if result else "Unknown error"
                print(f"[FMPScheduler] ✗ {name_ja}: {error}")

        except Exception as e:
            print(f"[FMPScheduler] Error fetching {name_ja}: {e}")
            import traceback
            traceback.print_exc()

    async def update_indicator_for_3_minutes(self, config: Dict[str, Any]):
        """
        発表時刻から3分間、毎分データを取得（3分方式）

        Args:
            config: 指標設定
        """
        name_ja = config["name_ja"]
        print(f"[FMPScheduler] Starting 3-minute update cycle for: {name_ja}")

        for iteration in range(1, UPDATE_ITERATIONS + 1):
            await self.fetch_indicator_data(config, iteration)

            if iteration < UPDATE_ITERATIONS:
                await asyncio.sleep(UPDATE_INTERVAL_SECONDS)

        print(f"[FMPScheduler] Completed update cycle for: {name_ja}")

    def schedule_release_jobs(self):
        """
        全発表日のジョブをスケジュール（各指標ごとにFMP APIを呼び出し）
        """
        print("[FMPScheduler] Scheduling release jobs...")

        # 既存ジョブをクリア
        for job_id in list(self._scheduled_jobs):
            try:
                self.scheduler.remove_job(job_id)
            except Exception:
                pass
        self._scheduled_jobs.clear()

        # 全指標の発表日を取得（指標ごとにeventパラメータで絞って取得）
        releases = self.fetch_all_upcoming_releases()

        scheduled_count = 0
        now_jst = datetime.now(JST)

        for release in releases:
            dt_jst = release["datetime_jst"]
            config = release["config"]
            name_ja = release["name_ja"]

            # 発表1分後にスケジュール
            trigger_time = dt_jst + timedelta(minutes=UPDATE_DELAY_MINUTES)

            if trigger_time <= now_jst:
                continue

            job_id = f"fmp_release_{name_ja}_{dt_jst.strftime('%Y%m%d_%H%M')}"

            self.scheduler.add_job(
                self.update_indicator_for_3_minutes,
                trigger=DateTrigger(run_date=trigger_time),
                args=[config],
                id=job_id,
                replace_existing=True
            )

            self._scheduled_jobs.add(job_id)
            scheduled_count += 1
            print(f"[FMPScheduler] Scheduled: {name_ja} at {trigger_time.strftime('%Y-%m-%d %H:%M JST')}")

        print(f"[FMPScheduler] Total jobs scheduled: {scheduled_count}")

    def schedule_weekly_refresh(self):
        """
        週次の発表日リフレッシュジョブを追加

        毎週日曜日 6:00 JSTに発表日を再取得してスケジュールを更新。
        """
        self.scheduler.add_job(
            self._refresh_schedules,
            trigger=CronTrigger(day_of_week='sun', hour=6, minute=0, timezone=JST),
            id="fmp_weekly_refresh",
            replace_existing=True
        )
        print("[FMPScheduler] Scheduled weekly refresh at Sun 06:00 JST")

        # 毎日深夜にも差分チェック（発表日変更検知用）
        self.scheduler.add_job(
            self._refresh_schedules,
            trigger=CronTrigger(hour=5, minute=0, timezone=JST),
            id="fmp_daily_refresh",
            replace_existing=True
        )
        print("[FMPScheduler] Scheduled daily refresh at 05:00 JST")

    async def _refresh_schedules(self):
        """スケジュールを再計算して更新（+ 過去発表分のバックフィル）"""
        print("[FMPScheduler] Refreshing release schedules...")
        self.schedule_release_jobs()

        # 過去30日分の発表データをバックフィル（スケジューラー停止中の漏れを補完）
        await self._backfill_recent_releases()

    async def _backfill_recent_releases(self):
        """
        過去30日間の発表データをFMPから再取得してDBに補完する

        スケジューラー停止中に発表があったデータの漏れを防ぐ。
        全指標に対してFMPからactual値を持つ直近30日分のイベントを取得してUpsert。
        """
        print("[FMPScheduler] Starting backfill for past 30 days...")
        today = date.today()
        start_date = today - timedelta(days=30)

        backfilled_total = 0
        for config in FMP_INDICATOR_CONFIGS:
            name_ja = config["name_ja"]
            fmp_event = config["fmp_event"]
            country = config.get("country", "US")
            try:
                events = fmp_service.fetch_calendar(
                    start_date, today,
                    country=country,
                    event=fmp_event
                )
                if events:
                    # actual値があるイベントのみ処理
                    actual_events = [e for e in events if e.get("actual") is not None]
                    if actual_events:
                        processed = [fmp_service.process_event(e) for e in actual_events]
                        count = calendar_repository.upsert_events(processed)
                        if count > 0:
                            print(f"[FMPScheduler] Backfilled {count} events for: {name_ja}")
                            backfilled_total += count
                            # サービスキャッシュも無効化して再取得
                            service = self._get_service_instance(config)
                            if service and hasattr(service, 'invalidate_cache'):
                                service.invalidate_cache()
                            # ダッシュボードキャッシュも無効化
                            category = config.get("category")
                            if category:
                                invalidate_dashboard_cache(country, category)
            except Exception as e:
                print(f"[FMPScheduler] Backfill error for {name_ja}: {e}")

        if backfilled_total > 0:
            print(f"[FMPScheduler] Backfill complete: {backfilled_total} events updated")
        else:
            print("[FMPScheduler] Backfill complete: no missing data found")

    def start(self):
        """スケジューラーを開始"""
        print("[FMPScheduler] ========================================")
        print("[FMPScheduler] Starting FMP Release Scheduler")
        print("[FMPScheduler] ========================================")

        self.schedule_release_jobs()
        self.schedule_weekly_refresh()
        self.scheduler.start()

        # 起動時にバックフィルを実行（スケジューラー停止中の漏れを補完）
        asyncio.ensure_future(self._backfill_recent_releases())

        print("[FMPScheduler] Scheduler started successfully")
        self._print_status()

    def shutdown(self):
        """スケジューラーを停止"""
        print("[FMPScheduler] Shutting down FMP Release Scheduler...")
        self.scheduler.shutdown()
        print("[FMPScheduler] Scheduler stopped")

    def _print_status(self):
        """現在のスケジュール状態を表示"""
        jobs = self.scheduler.get_jobs()
        print(f"[FMPScheduler] Active jobs: {len(jobs)}")
        for job in jobs[:15]:  # 直近15件
            next_run = job.next_run_time
            if next_run:
                print(f"  - {job.id}: {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    def get_status(self) -> Dict[str, Any]:
        """スケジューラーの状態を取得"""
        jobs = self.scheduler.get_jobs()

        return {
            "running": self.scheduler.running,
            "total_jobs": len(jobs),
            "upcoming_releases": len(self._upcoming_releases),
            "jobs": [
                {
                    "id": job.id,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                }
                for job in jobs[:20]
            ],
        }

    def get_upcoming_releases(self) -> List[Dict[str, Any]]:
        """発表予定リストを取得"""
        return [
            {
                "name_ja": r["name_ja"],
                "event_name": r["event_name"],
                "datetime_jst": r["datetime_jst"].isoformat(),
                "estimate": r.get("estimate"),
            }
            for r in self._upcoming_releases
        ]


# グローバルスケジューラーインスタンス
fmp_release_scheduler = FMPReleaseScheduler()
