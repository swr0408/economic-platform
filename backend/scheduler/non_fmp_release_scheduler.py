"""
非FMP指標用スケジューラー

FMP Economic Calendarに登録されていない指標（e-Stat、FRED、独自ソース等）の
発表時刻ベースで自動更新を行うスケジューラー。

各指標に設定されたスケジュール（release_schedule_utils）に基づいて、
発表時刻の1分後にデータ取得ジョブをスケジュール。
"""

import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Set, Callable
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

# FMPスケジューラーからダッシュボードキャッシュ無効化を流用
try:
    from scheduler.fmp_release_scheduler import invalidate_dashboard_cache, FMP_COUNTRY_TO_DASHBOARD
except ImportError:
    from backend.scheduler.fmp_release_scheduler import invalidate_dashboard_cache, FMP_COUNTRY_TO_DASHBOARD


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")

# 発表後の更新設定
UPDATE_DELAY_MINUTES = 5  # 発表から5分後に取得開始（データソース反映ラグ考慮）
UPDATE_ITERATIONS = 3     # 3回取得
UPDATE_INTERVAL_SECONDS = 60

# ポーリングリトライ設定（FRED/e-Stat等の反映ラグ対策）
POLLING_RETRY_MINUTES = [15, 30, 45, 60]

# ============================================================
# 非FMP指標設定
# ============================================================
#
# 設定項目:
# - name_ja: 指標名（日本語）
# - country: ダッシュボード国コード（JP, US, EU, DE, GB）
# - category: ダッシュボードカテゴリ（economy, consumer, employment, inflation, housing, policy, price）
# - service_module: サービスモジュールパス
# - service_instance: シングルトンインスタンス名
# - fetch_method: データ取得メソッド名
# - schedule_type: スケジュールタイプ（cron, weekly, nth_week, daily）
# - schedule_config: スケジュール設定（タイプ別）
#
# schedule_configの例:
# - cron: {"day": 10, "hour": 8, "minute": 50} → 毎月10日 8:50 JST
# - cron (範囲): {"day": "10-18", "hour": 8, "minute": 50} → 毎月10-18日 8:50 JST
# - weekly: {"day_of_week": 2, "hour": 15, "minute": 15} → 毎週水曜 15:15 JST
# - quarterly: {"months": [1,4,7,10], "day": "3-8", "hour": 15, "minute": 0}
# ============================================================

NON_FMP_INDICATOR_CONFIGS = [
    # ============================================================
    # 日本 - 物価
    # ============================================================
    # ※ CGPI関連（企業物価指数、飲食料品、輸入/輸出物価）はFMPマッピング済み
    #    → fmp_release_scheduler.py の "Producer Price Index" で管理
    {
        # 発表: 毎週水曜日 15:15 JST
        # 出典: 日経・東大日次物価指数
        # ※ FMP未登録のため非FMPスケジューラーで管理
        "name_ja": "POS消費者購買単価指数（POS-UVPI）",
        "country": "JP",
        "category": "price",
        "service_module": "services.japan.japan_pos_uvpi_service",
        "service_instance": "japan_pos_uvpi_service",
        "fetch_method": "get_pos_uvpi_data",
        "schedule_type": "weekly",
        "schedule_config": {
            "day_of_week": 2,  # 水曜日
            "hour": 15,
            "minute": 15,
        },
    },
    {
        # 発表: 半年ごと（3月調査・9月調査の結果を数ヶ月後にPDF公開）
        # 毎週金曜 15:50 JST に新規PDF公開をチェック
        # 出典: 中小企業庁 価格交渉促進月間フォローアップ調査
        # ※ FMP未登録のため非FMPスケジューラーで管理
        "name_ja": "価格転嫁率（中小企業庁）",
        "country": "JP",
        "category": "price",
        "service_module": "services.japan.price_pass_through_rate_service",
        "service_instance": "price_pass_through_rate_service",
        "fetch_method": "get_data",
        "schedule_type": "weekly",
        "schedule_config": {
            "day_of_week": 4,  # 金曜日
            "hour": 15,
            "minute": 50,
        },
    },
    {
        # 3月・9月は毎営業日もチェック（公表月のため）
        "name_ja": "価格転嫁率（中小企業庁）3月チェック",
        "country": "JP",
        "category": "price",
        "service_module": "services.japan.price_pass_through_rate_service",
        "service_instance": "price_pass_through_rate_service",
        "fetch_method": "get_data",
        "schedule_type": "cron_range",
        "schedule_config": {
            "day_start": 1,
            "day_end": 31,
            "month": 3,
            "hour": 15,
            "minute": 50,
        },
    },
    {
        # 9月も毎営業日チェック
        "name_ja": "価格転嫁率（中小企業庁）9月チェック",
        "country": "JP",
        "category": "price",
        "service_module": "services.japan.price_pass_through_rate_service",
        "service_instance": "price_pass_through_rate_service",
        "fetch_method": "get_data",
        "schedule_type": "cron_range",
        "schedule_config": {
            "day_start": 1,
            "day_end": 30,
            "month": 9,
            "hour": 15,
            "minute": 50,
        },
    },
    # ============================================================
    # 日本 - 経済
    # ============================================================
    # ※ 機械受注はFMPマッピング済み → "Machinery Orders MoM/YoY"
    # ※ 第3次産業活動指数はFMPマッピング済み → "Tertiary Industry Index MoM"
    {
        # 発表: 四半期（4/7/10月初旬、12月中旬）8:50 JST
        # 出典: 日本銀行 短観
        # ※ FMPにはTankan Large Manufacturers Indexとして登録あり（next_release用）
        #    Excel公開タイミングはFMPイベントと同日だが、自動取得は非FMPスケジューラーで管理
        "name_ja": "日銀短観（DI）",
        "country": "JP",
        "category": "economy",
        "service_module": "services.japan.boj_tankan_service",
        "service_instance": "boj_tankan_service",
        "fetch_method": "get_tankan_data",
        "schedule_type": "quarterly",
        "schedule_config": {
            "months": [1, 4, 7, 10],
            "day_start": 1,
            "day_end": 5,
            "hour": 9,
            "minute": 0,
        },
    },
    {
        # 発表: 日銀短観DIと同時
        # 出典: 日本銀行 短観（包括的データ - 設備投資額）
        "name_ja": "日銀短観（設備投資）",
        "country": "JP",
        "category": "economy",
        "service_module": "services.japan.boj_tankan_comprehensive_service",
        "service_instance": "boj_tankan_comprehensive_service",
        "fetch_method": "get_comprehensive_data",
        "schedule_type": "quarterly",
        "schedule_config": {
            "months": [1, 4, 7, 10],
            "day_start": 1,
            "day_end": 5,
            "hour": 9,
            "minute": 0,
        },
        "fetch_kwargs": {"data_type": "capital_investment"},
    },
    {
        # 発表: 四半期（1/4/7/10月）3-8日頃 15:00 JST
        # 出典: 日本銀行
        # ※ FMP未登録のため非FMPスケジューラーで管理
        "name_ja": "日銀GDPギャップ",
        "country": "JP",
        "category": "economy",
        "service_module": "services.japan.boj_gdp_gap_service",
        "service_instance": "boj_gdp_gap_service",
        "fetch_method": "get_boj_gdp_gap_data",
        "schedule_type": "quarterly",
        "schedule_config": {
            "months": [1, 4, 7, 10],
            "day_start": 3,
            "day_end": 8,
            "hour": 15,
            "minute": 0,
        },
    },
    {
        # 発表: 毎月20-28日頃（月例経済報告）15:00 JST
        # 出典: 内閣府
        # ※ FMP未登録のため非FMPスケジューラーで管理
        "name_ja": "内閣府GDPギャップ",
        "country": "JP",
        "category": "economy",
        "service_module": "services.japan.japan_gdp_gap_service",
        "service_instance": "japan_gdp_gap_service",
        "fetch_method": "get_japan_gdp_gap_data",
        "schedule_type": "cron_range",
        "schedule_config": {
            "day_start": 20,
            "day_end": 28,
            "hour": 15,
            "minute": 0,
        },
    },
    # ============================================================
    # 日本 - 雇用
    # ============================================================
    # ※ 毎月勤労統計（現金給与総額、実質賃金、所定内給与）はFMPマッピング済み
    #    → "Average Cash Earnings YoY" で管理

    # ============================================================
    # 日本 - 消費者
    # ============================================================
    # ※ 消費動向調査（消費者態度指数）はFMPマッピング済み → "Consumer Confidence"
    # ※ 景気ウォッチャー調査はFMPマッピング済み → "Eco Watchers Survey Current"

    # ============================================================
    # 日本 - 金融政策
    # ============================================================
    {
        # 発表: 毎営業日 18:00頃 JST（市場終了後）
        # 出典: 日本銀行・財務省（物価連動国債利回り）
        # ※ FMP未登録のため非FMPスケジューラーで管理
        "name_ja": "日銀BEI（ブレークイーブン・インフレ率）",
        "country": "JP",
        "category": "policy",
        "service_module": "services.japan.bei_service",
        "service_instance": "bei_service",
        "fetch_method": "get_bei_data",
        "schedule_type": "business_day",
        "schedule_config": {
            "hour": 18,
            "minute": 0,
        },
    },
    {
        # 発表: 毎営業日 16:00頃 JST（市場終了後）
        # 出典: JSCC (Japan Securities Clearing Corporation) Settlement Rates PDF
        # ※ FMP未登録のため非FMPスケジューラーで管理
        "name_ja": "JSCC OISカーブ",
        "country": "JP",
        "category": "policy",
        "service_module": "services.japan.ois_curve_service",
        "service_instance": "ois_curve_service",
        "fetch_method": "get_ois_curve",
        "schedule_type": "business_day",
        "schedule_config": {
            "hour": 16,
            "minute": 0,
        },
    },
    # ============================================================
    # 米国 - FRED系
    # ============================================================
    # ※ GDPNowはFMPマッピング済み → "Atlanta Fed GDPNow"
    # ※ Median CPIはCPI発表と同時 → FMP "CPI" でトリガー
    # ※ Trimmed Mean PCEはPCE発表と同時 → FMP "PCE Price Index" でトリガー
    # ※ Sahm Ruleは雇用統計発表と同時 → FMP "Unemployment Rate" でトリガー
    # ※ 実質小売売上高はRetail Sales発表と同時 → FMP "Retail Sales" でトリガー
    {
        # 発表: 毎営業日 10:00 ET = 翌0:00 JST（冬時間）/ 23:00 JST（夏時間）
        # 出典: クリーブランド連銀
        # ※ FMP未登録のため非FMPスケジューラーで管理
        "name_ja": "Inflation Nowcasting（クリーブランド連銀）",
        "country": "US",
        "category": "inflation",
        "service_module": "services.usa.inflation_nowcasting_service",
        "service_instance": "inflation_nowcasting_service",
        "fetch_method": "get_inflation_nowcasting_data",
        "schedule_type": "business_day",
        "schedule_config": {
            "hour": 0,  # 10:00 ET = 翌0:00 JST（冬時間基準）
            "minute": 0,
        },
    },
    {
        # 発表: 毎週木曜日 4:30 PM ET = 金曜日 6:30 JST（冬時間）
        # 出典: FRB H.4.1 Release
        # ※ FMP未登録のため非FMPスケジューラーで管理
        "name_ja": "FRB総資産",
        "country": "US",
        "category": "policy",
        "service_module": "services.usa.frb_total_assets_service",
        "service_instance": "frb_total_assets_service",
        "fetch_method": "get_frb_total_assets_data",
        "schedule_type": "weekly",
        "schedule_config": {
            "day_of_week": 4,  # 金曜日（木曜日ET発表 → 金曜日JST）
            "hour": 6,
            "minute": 30,
        },
    },
    {
        # 発表: 毎週木曜日 4:30 PM ET = 金曜日 6:30 JST（冬時間）
        # 出典: FRB H.4.1 Release
        # ※ FMP未登録のため非FMPスケジューラーで管理
        "name_ja": "準備預金残高",
        "country": "US",
        "category": "policy",
        "service_module": "services.usa.reserve_balances_service",
        "service_instance": "reserve_balances_service",
        "fetch_method": "get_reserve_balances_data",
        "schedule_type": "weekly",
        "schedule_config": {
            "day_of_week": 4,  # 金曜日（木曜日ET発表 → 金曜日JST）
            "hour": 6,
            "minute": 30,
        },
    },
    {
        # 発表: 毎営業日 4:00 PM ET = 翌6:00 JST（冬時間）
        # 出典: 米財務省 Daily Treasury Statement
        # ※ FMP未登録のため非FMPスケジューラーで管理
        "name_ja": "TGA（財務省一般勘定）",
        "country": "US",
        "category": "policy",
        "service_module": "services.usa.tga_service",
        "service_instance": "tga_service",
        "fetch_method": "get_tga_data",
        "schedule_type": "business_day",
        "schedule_config": {
            "hour": 6,
            "minute": 0,
        },
    },
    {
        # 発表: 毎営業日（市場終了後）
        # 出典: FRED (ICE BofA)
        # ※ FMP未登録のため非FMPスケジューラーで管理
        "name_ja": "OASスプレッド",
        "country": "US",
        "category": "policy",
        "service_module": "services.usa.oas_service",
        "service_instance": "oas_service",
        "fetch_method": "get_oas_data",
        "schedule_type": "business_day",
        "schedule_config": {
            "hour": 6,
            "minute": 0,
        },
    },
    {
        # Quarterly Refunding - Financing Estimates
        # 発表: 2月/5月/8月/11月 第1週前半 15:00 ET = 翌5:00 JST
        # 出典: U.S. Department of the Treasury
        "name_ja": "Quarterly Refunding（Financing Estimates）",
        "country": "US",
        "category": "policy",
        "service_module": "services.usa.quarterly_refunding_service",
        "service_instance": "quarterly_refunding_service",
        "fetch_method": "get_data",
        "schedule_type": "cron_range",
        "schedule_config": {
            "day_start": 1,
            "day_end": 7,
            "month": "2,5,8,11",
            "hour": 5,   # 15:00 ET = 翌5:00 JST
            "minute": 0,
        },
    },
    {
        # Quarterly Refunding - Policy Statement / TBAC / Auction Schedule / Buyback Schedule
        # 発表: 2月/5月/8月/11月 第1水曜 8:30 ET = 22:30 JST
        # 出典: U.S. Department of the Treasury
        "name_ja": "Quarterly Refunding（Policy Statement）",
        "country": "US",
        "category": "policy",
        "service_module": "services.usa.quarterly_refunding_service",
        "service_instance": "quarterly_refunding_service",
        "fetch_method": "get_data",
        "schedule_type": "cron_range",
        "schedule_config": {
            "day_start": 1,
            "day_end": 7,
            "month": "2,5,8,11",
            "hour": 22,   # 8:30 ET = 22:30 JST
            "minute": 31,
        },
    },
    # ============================================================
    # イギリス
    # ============================================================
    # ※ Nationwide住宅価格指数はFMPマッピング済み → "Nationwide Housing Prices MoM/YoY"
    # ※ BoE住宅ローン金利はFMPマッピング済み → "BBA Mortgage Rate"
    # ※ BoE住宅ローン承認件数はFMPマッピング済み → "Mortgage Approvals"
    {
        # 発表: 毎月7日頃 7:00 UK = 16:00 JST（冬時間）/ 15:00 JST（夏時間）
        # 出典: Halifax (Lloyds Banking Group)
        # ※ FMP未登録のため非FMPスケジューラーで管理
        "name_ja": "Halifax住宅価格指数",
        "country": "GB",
        "category": "housing",
        "service_module": "services.uk.halifax_house_price_service",
        "service_instance": "halifax_house_price_service",
        "fetch_method": "get_halifax_house_price_data",
        "schedule_type": "cron_range",
        "schedule_config": {
            "day_start": 5,
            "day_end": 10,
            "hour": 16,  # 7:00 UK = 16:00 JST（冬時間）
            "minute": 0,
        },
    },
    {
        # 発表: 毎月第3週月曜日 00:01 UK = 9:01 JST
        # 出典: Rightmove
        # ※ FMP未登録のため非FMPスケジューラーで管理
        "name_ja": "Rightmove住宅価格指数",
        "country": "GB",
        "category": "housing",
        "service_module": "services.uk.rightmove_house_price_service",
        "service_instance": "rightmove_house_price_service",
        "fetch_method": "get_rightmove_house_price_data",
        "schedule_type": "cron_range",
        "schedule_config": {
            "day_start": 15,
            "day_end": 22,
            "hour": 9,  # 00:01 UK = 9:01 JST（冬時間）
            "minute": 1,
        },
    },
    {
        # 発表: 毎営業日 9:00 UK = 18:00 JST
        # 出典: Bank of England
        # ※ FMP未登録のため非FMPスケジューラーで管理
        "name_ja": "SONIA（翌日物金利）",
        "country": "GB",
        "category": "policy",
        "service_module": "services.uk.sonia_service",
        "service_instance": "sonia_service",
        "fetch_method": "get_sonia_data",
        "schedule_type": "business_day",
        "schedule_config": {
            "hour": 18,  # 9:00 UK = 18:00 JST（冬時間）
            "minute": 0,
        },
    },
    {
        # 発表: 毎UK営業日にYield Curve ZIPが更新（~17:00 UK = ~02:00 JST翌日 冬時間）
        # 出典: Bank of England Yield Curves ZIP
        # ※ FMP未登録のため非FMPスケジューラーで管理
        # JST営業日 04:00 に取得（BOE発行ラグ吸収）
        "name_ja": "BOE OISフォワードカーブ",
        "country": "GB",
        "category": "policy",
        "service_module": "services.uk.boe_ois_curve_service",
        "service_instance": "boe_ois_curve_service",
        "fetch_method": "get_ois_curve_data",
        "schedule_type": "business_day",
        "schedule_config": {
            "hour": 4,
            "minute": 0,
        },
    },
]


class NonFMPReleaseScheduler:
    """
    非FMP指標用スケジューラー

    FMPに登録されていない指標の発表時刻に基づいてデータ取得ジョブをスケジュール。
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._service_cache: Dict[str, Any] = {}
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    def start(self):
        """スケジューラーを開始"""
        if self._is_running:
            print("[NonFMPScheduler] Already running")
            return

        try:
            # 各指標のスケジュールを登録
            self._schedule_all_indicators()

            # スケジューラーを開始
            self.scheduler.start()
            self._is_running = True

            print(f"[NonFMPScheduler] Started with {len(NON_FMP_INDICATOR_CONFIGS)} indicators")

        except Exception as e:
            print(f"[NonFMPScheduler] Failed to start: {e}")
            import traceback
            traceback.print_exc()

    def stop(self):
        """スケジューラーを停止"""
        if not self._is_running:
            return

        try:
            self.scheduler.shutdown(wait=False)
            self._is_running = False
            print("[NonFMPScheduler] Stopped")
        except Exception as e:
            print(f"[NonFMPScheduler] Error stopping: {e}")

    def _schedule_all_indicators(self):
        """全ての非FMP指標のスケジュールを登録"""
        for config in NON_FMP_INDICATOR_CONFIGS:
            try:
                self._schedule_indicator(config)
            except Exception as e:
                print(f"[NonFMPScheduler] Error scheduling {config['name_ja']}: {e}")

    def _schedule_indicator(self, config: Dict[str, Any]):
        """
        指標のスケジュールを登録

        Args:
            config: 指標設定
        """
        name_ja = config["name_ja"]
        schedule_type = config["schedule_type"]
        schedule_config = config["schedule_config"]

        job_id = f"non_fmp_{name_ja.replace(' ', '_').replace('（', '_').replace('）', '')}"

        if schedule_type == "cron_range":
            # 日付範囲ベース（毎日チェック）
            day_start = schedule_config["day_start"]
            day_end = schedule_config["day_end"]
            hour = schedule_config["hour"]
            minute = schedule_config["minute"]
            month = schedule_config.get("month")  # オプション: 特定月のみ

            # 発表期間中の毎日、発表時刻+1分にスケジュール
            cron_kwargs = dict(
                day=f"{day_start}-{day_end}",
                hour=hour,
                minute=minute + UPDATE_DELAY_MINUTES,
                timezone=JST,
            )
            if month is not None:
                cron_kwargs["month"] = month
            trigger = CronTrigger(**cron_kwargs)

        elif schedule_type == "weekly":
            # 週次
            day_of_week = schedule_config["day_of_week"]
            hour = schedule_config["hour"]
            minute = schedule_config["minute"]

            trigger = CronTrigger(
                day_of_week=day_of_week,
                hour=hour,
                minute=minute + UPDATE_DELAY_MINUTES,
                timezone=JST
            )

        elif schedule_type == "quarterly":
            # 四半期
            months = schedule_config["months"]
            day_start = schedule_config["day_start"]
            day_end = schedule_config["day_end"]
            hour = schedule_config["hour"]
            minute = schedule_config["minute"]

            trigger = CronTrigger(
                month=",".join(str(m) for m in months),
                day=f"{day_start}-{day_end}",
                hour=hour,
                minute=minute + UPDATE_DELAY_MINUTES,
                timezone=JST
            )

        elif schedule_type == "daily":
            # 毎日
            hour = schedule_config["hour"]
            minute = schedule_config["minute"]

            trigger = CronTrigger(
                hour=hour,
                minute=minute + UPDATE_DELAY_MINUTES,
                timezone=JST
            )

        elif schedule_type == "business_day":
            # 営業日（月-金）
            hour = schedule_config["hour"]
            minute = schedule_config["minute"]

            trigger = CronTrigger(
                day_of_week="mon-fri",
                hour=hour,
                minute=minute + UPDATE_DELAY_MINUTES,
                timezone=JST
            )

        else:
            print(f"[NonFMPScheduler] Unknown schedule type: {schedule_type} for {name_ja}")
            return

        self.scheduler.add_job(
            self._update_indicator,
            trigger=trigger,
            args=[config],
            id=job_id,
            replace_existing=True,
            name=f"NonFMP: {name_ja}"
        )

        print(f"[NonFMPScheduler] Scheduled: {name_ja} ({schedule_type})")

    async def _update_indicator(self, config: Dict[str, Any]):
        """
        指標データを更新（3回取得方式 + ポーリングリトライ）

        Args:
            config: 指標設定
        """
        name_ja = config["name_ja"]
        print(f"[NonFMPScheduler] Starting update: {name_ja}")

        # 初回取得前のサービス最新日付を記録
        latest_before = self._get_service_latest_date(config)

        for iteration in range(1, UPDATE_ITERATIONS + 1):
            try:
                await self._fetch_indicator_data(config, iteration)

                if iteration < UPDATE_ITERATIONS:
                    await asyncio.sleep(UPDATE_INTERVAL_SECONDS)

            except Exception as e:
                print(f"[NonFMPScheduler] Error in iteration {iteration} for {name_ja}: {e}")

        # 初回取得後のサービス最新日付を確認
        latest_after = self._get_service_latest_date(config)

        # データが更新されなかった場合、ポーリングリトライをスケジュール
        if latest_before == latest_after and latest_before is not None:
            print(f"[NonFMPScheduler] Data unchanged for {name_ja} "
                  f"(latest={latest_before}), scheduling polling retries...")
            now_jst = datetime.now(JST)
            for delay_min in POLLING_RETRY_MINUTES:
                retry_time = now_jst + timedelta(minutes=delay_min)
                retry_job_id = f"nonfmp_retry_{name_ja}_{now_jst.strftime('%Y%m%d_%H%M')}_{delay_min}m"
                try:
                    self.scheduler.add_job(
                        self._polling_retry,
                        trigger=DateTrigger(run_date=retry_time),
                        args=[config, latest_before],
                        id=retry_job_id,
                        replace_existing=True,
                    )
                except Exception as e:
                    print(f"[NonFMPScheduler] Failed to schedule retry: {e}")

    async def _polling_retry(self, config: Dict[str, Any], latest_before: str):
        """
        ポーリングリトライ: データが更新されるまで再取得を試みる

        Args:
            config: 指標設定
            latest_before: 更新前のサービス最新日付
        """
        name_ja = config["name_ja"]
        country = config["country"]
        category = config["category"]

        # 現在の最新日付を確認
        current_latest = self._get_service_latest_date(config)
        if current_latest and current_latest != latest_before:
            print(f"[NonFMPScheduler] Polling skip for {name_ja}: "
                  f"already updated ({latest_before} -> {current_latest})")
            return

        print(f"[NonFMPScheduler] Polling retry for {name_ja}: "
              f"latest still {current_latest}, retrying...")

        try:
            service = self._get_service_instance(config)
            if not service:
                return

            fetch_method = getattr(service, config["fetch_method"], None)
            if not fetch_method:
                return

            extra_kwargs = config.get("fetch_kwargs", {})
            result = fetch_method(force_refresh=True, **extra_kwargs)

            if result and not result.get("error"):
                new_latest = result.get("latest", {})
                new_date = new_latest.get("date") if new_latest else None
                if new_date and new_date != latest_before:
                    print(f"[NonFMPScheduler] Polling success for {name_ja}: "
                          f"{latest_before} -> {new_date}")
                    if category:
                        invalidate_dashboard_cache(country, category)
                else:
                    print(f"[NonFMPScheduler] Polling: {name_ja} still at {new_date}")

        except Exception as e:
            print(f"[NonFMPScheduler] Polling error for {name_ja}: {e}")

    def _get_service_latest_date(self, config: Dict[str, Any]) -> Optional[str]:
        """サービスのキャッシュから最新データ日付を取得"""
        try:
            service = self._get_service_instance(config)
            if not service:
                return None

            # redis_client経由でキャッシュを取得
            try:
                from core.redis_client import redis_client
            except ImportError:
                from backend.core.redis_client import redis_client

            for key_attr in ['REDIS_KEY', 'DATA_CACHE_KEY', 'CACHE_KEY']:
                key = getattr(service, key_attr, None)
                if key:
                    data = redis_client.get(key)
                    if data and isinstance(data, dict):
                        latest = data.get("latest", {})
                        if isinstance(latest, dict):
                            return latest.get("date")
            return None
        except Exception:
            return None

    async def _fetch_indicator_data(self, config: Dict[str, Any], iteration: int):
        """
        指標データを取得

        Args:
            config: 指標設定
            iteration: 取得回数（1-3）
        """
        name_ja = config["name_ja"]
        country = config["country"]
        category = config["category"]

        try:
            print(f"[NonFMPScheduler] Fetching {name_ja} (iteration {iteration}/{UPDATE_ITERATIONS})...")

            # サービスインスタンスを取得
            service = self._get_service_instance(config)
            if service is None:
                print(f"[NonFMPScheduler] Service not found: {config['service_module']}")
                return

            # データ取得メソッドを取得
            fetch_method_name = config["fetch_method"]
            if not hasattr(service, fetch_method_name):
                print(f"[NonFMPScheduler] Method not found: {fetch_method_name}")
                return

            fetch_method = getattr(service, fetch_method_name)

            # データを取得（force_refresh=True）
            extra_kwargs = config.get("fetch_kwargs", {})
            result = fetch_method(force_refresh=True, **extra_kwargs)

            if result and not result.get("error"):
                latest = result.get("latest", {})
                latest_date = latest.get("date") if latest else "N/A"
                latest_value = latest.get("value") if latest else "N/A"
                print(f"[NonFMPScheduler] ✓ {name_ja}: date={latest_date}, value={latest_value}, source={result.get('source')}")

                # ダッシュボードキャッシュを無効化
                if category:
                    invalidate_dashboard_cache(country, category)
            else:
                error = result.get("error") if result else "Unknown error"
                print(f"[NonFMPScheduler] ✗ {name_ja}: {error}")

        except Exception as e:
            print(f"[NonFMPScheduler] Error fetching {name_ja}: {e}")
            import traceback
            traceback.print_exc()

    def _get_service_instance(self, config: Dict[str, Any]) -> Optional[Any]:
        """
        サービスインスタンスを取得（キャッシュ利用）

        Args:
            config: 指標設定

        Returns:
            サービスインスタンス
        """
        module_path = config["service_module"]
        instance_name = config["service_instance"]

        cache_key = f"{module_path}.{instance_name}"

        if cache_key in self._service_cache:
            return self._service_cache[cache_key]

        try:
            import importlib
            module = importlib.import_module(module_path)
            service = getattr(module, instance_name, None)

            if service:
                self._service_cache[cache_key] = service

            return service

        except Exception as e:
            print(f"[NonFMPScheduler] Failed to load service: {e}")
            return None

    async def manual_update(self, indicator_name: str):
        """
        指標を手動更新

        Args:
            indicator_name: 指標名（部分一致）
        """
        for config in NON_FMP_INDICATOR_CONFIGS:
            if indicator_name.lower() in config["name_ja"].lower():
                await self._update_indicator(config)
                return

        print(f"[NonFMPScheduler] Indicator not found: {indicator_name}")

    def get_status(self) -> Dict[str, Any]:
        """スケジューラーの状態を取得"""
        jobs = []
        if self._is_running:
            for job in self.scheduler.get_jobs():
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                })

        return {
            "is_running": self._is_running,
            "total_indicators": len(NON_FMP_INDICATOR_CONFIGS),
            "scheduled_jobs": len(jobs),
            "jobs": jobs[:20],  # 直近20件
        }

    def get_indicators(self) -> List[Dict[str, Any]]:
        """登録されている指標一覧を取得"""
        return [
            {
                "name_ja": c["name_ja"],
                "country": c["country"],
                "category": c["category"],
                "schedule_type": c["schedule_type"],
                "schedule_config": c["schedule_config"],
            }
            for c in NON_FMP_INDICATOR_CONFIGS
        ]


# シングルトンインスタンス
non_fmp_release_scheduler = NonFMPReleaseScheduler()
