"""
経済指標レジストリ

全サービスと発表スケジュールチェッカーの対応を定義。
スケジューラーはこのレジストリを参照して、各指標の発表時刻にデータを事前取得する。
"""

from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass
from enum import Enum


class Category(Enum):
    """指標カテゴリ"""
    MONETARY_POLICY = "monetary_policy"  # 金融政策
    ECONOMY = "economy"                   # 経済
    CONSUMER = "consumer"                 # 消費
    EMPLOYMENT = "employment"             # 雇用


@dataclass
class IndicatorConfig:
    """指標設定"""
    name: str                          # 指標名（日本語）
    name_en: str                       # 指標名（英語）
    category: Category                 # カテゴリ
    service_module: str                # サービスモジュールパス
    service_class: str                 # サービスクラス名
    service_instance: str              # シングルトンインスタンス名
    fetch_method: str                  # データ取得メソッド名
    schedule_checker: Optional[str]    # スケジュールチェッカー名（release_schedule_utils内）
    enabled: bool = True               # スケジュール有効フラグ


# ============================================================
# 金融政策関連 (MONETARY_POLICY)
# ============================================================

MONETARY_POLICY_INDICATORS: List[IndicatorConfig] = [
    # CME FedWatch は独自スケジュール（FOMC前後で変動）
    # FOMC関連は既存スケジューラー（fomc_projections_scheduler, policy_rate_scheduler）で対応
]


# ============================================================
# 経済指標 (ECONOMY)
# ============================================================

ECONOMY_INDICATORS: List[IndicatorConfig] = [
    # GDP関連
    IndicatorConfig(
        name="GDP成長率",
        name_en="GDP Growth Rate",
        category=Category.ECONOMY,
        service_module="services.usa.gdp_service",
        service_class="GDPService",
        service_instance="gdp_service",
        fetch_method="get_gdp_growth_data",
        schedule_checker="GDP_GROWTH_CHECKER",
    ),
    IndicatorConfig(
        name="GDP項目別成長率",
        name_en="GDP Components",
        category=Category.ECONOMY,
        service_module="services.usa.bea_gdp_components_service",
        service_class="BEAGDPComponentsService",
        service_instance="bea_gdp_components_service",
        fetch_method="get_components_data",
        schedule_checker="GDP_GROWTH_CHECKER",
    ),
    IndicatorConfig(
        name="GDP寄与度",
        name_en="GDP Contributions",
        category=Category.ECONOMY,
        service_module="services.usa.gdp_contributions_service",
        service_class="GDPContributionsService",
        service_instance="gdp_contributions_service",
        fetch_method="get_contributions_data",
        schedule_checker="GDP_GROWTH_CHECKER",
    ),
    IndicatorConfig(
        name="潜在GDP",
        name_en="Potential GDP",
        category=Category.ECONOMY,
        service_module="services.usa.potential_gdp_service",
        service_class="PotentialGDPService",
        service_instance="potential_gdp_service",
        fetch_method="get_potential_gdp_data",
        schedule_checker="GDP_GROWTH_CHECKER",
    ),

    # ISM関連
    IndicatorConfig(
        name="ISM製造業景況指数",
        name_en="ISM Manufacturing",
        category=Category.ECONOMY,
        service_module="services.usa.ism_manufacturing_service",
        service_class="ISMManufacturingService",
        service_instance="ism_manufacturing_service",
        fetch_method="get_ism_manufacturing_data",
        schedule_checker="ISM_MANUFACTURING_CHECKER",
    ),
    IndicatorConfig(
        name="ISM製造業構成指数",
        name_en="ISM Manufacturing Components",
        category=Category.ECONOMY,
        service_module="services.usa.ism_components_service",
        service_class="ISMComponentsService",
        service_instance="ism_components_service",
        fetch_method="get_ism_components_data",
        schedule_checker="ISM_MANUFACTURING_CHECKER",
    ),
    IndicatorConfig(
        name="ISM非製造業景況指数",
        name_en="ISM Non-Manufacturing",
        category=Category.ECONOMY,
        service_module="services.usa.ism_non_manufacturing_service",
        service_class="ISMNonManufacturingService",
        service_instance="ism_non_manufacturing_service",
        fetch_method="get_ism_non_manufacturing_data",
        schedule_checker="ISM_NON_MANUFACTURING_CHECKER",
    ),
    IndicatorConfig(
        name="ISM非製造業構成指数",
        name_en="ISM Non-Manufacturing Components",
        category=Category.ECONOMY,
        service_module="services.usa.ism_non_manufacturing_components_service",
        service_class="ISMNonManufacturingComponentsService",
        service_instance="ism_non_manufacturing_components_service",
        fetch_method="get_ism_non_manufacturing_components_data",
        schedule_checker="ISM_NON_MANUFACTURING_CHECKER",
    ),

    # 地区連銀調査
    IndicatorConfig(
        name="NY連銀製造業景気指数",
        name_en="Empire State Manufacturing",
        category=Category.ECONOMY,
        service_module="services.usa.empire_state_service",
        service_class="EmpireStateService",
        service_instance="empire_state_service",
        fetch_method="get_empire_state_data",
        schedule_checker="NY_FED_MANUFACTURING_CHECKER",
    ),
    IndicatorConfig(
        name="フィラデルフィア連銀製造業景気指数",
        name_en="Philadelphia Fed Manufacturing",
        category=Category.ECONOMY,
        service_module="services.usa.philadelphia_fed_service",
        service_class="PhiladelphiaFedService",
        service_instance="philadelphia_fed_service",
        fetch_method="get_philadelphia_fed_data",
        schedule_checker="PHILLY_FED_MANUFACTURING_CHECKER",
    ),

    # 鉱工業生産関連
    IndicatorConfig(
        name="鉱工業生産",
        name_en="Industrial Production",
        category=Category.ECONOMY,
        service_module="services.usa.industrial_production_service",
        service_class="IndustrialProductionService",
        service_instance="industrial_production_service",
        fetch_method="get_industrial_production_data",
        schedule_checker="INDUSTRIAL_PRODUCTION_CHECKER",
    ),
    IndicatorConfig(
        name="設備稼働率",
        name_en="Capacity Utilization",
        category=Category.ECONOMY,
        service_module="services.usa.capacity_utilization_service",
        service_class="CapacityUtilizationService",
        service_instance="capacity_utilization_service",
        fetch_method="get_capacity_utilization_data",
        schedule_checker="CAPACITY_UTILIZATION_CHECKER",
    ),
    IndicatorConfig(
        name="耐久財受注",
        name_en="Durable Goods Orders",
        category=Category.ECONOMY,
        service_module="services.usa.durable_goods_service",
        service_class="DurableGoodsService",
        service_instance="durable_goods_service",
        fetch_method="get_durable_goods_data",
        schedule_checker="DURABLE_GOODS_CHECKER",
    ),

    # NFIB関連
    IndicatorConfig(
        name="NFIB中小企業楽観指数",
        name_en="NFIB Small Business Optimism",
        category=Category.ECONOMY,
        service_module="services.usa.nfib_service",
        service_class="NFIBService",
        service_instance="nfib_service",
        fetch_method="get_nfib_data",
        schedule_checker="NFIB_CHECKER",
    ),
]


# ============================================================
# 消費関連 (CONSUMER)
# ============================================================

CONSUMER_INDICATORS: List[IndicatorConfig] = [
    # 小売売上
    IndicatorConfig(
        name="小売売上高",
        name_en="Retail Sales",
        category=Category.CONSUMER,
        service_module="services.usa.retail_sales_service",
        service_class="RetailSalesService",
        service_instance="retail_sales_service",
        fetch_method="get_retail_sales_data",
        schedule_checker="RETAIL_SALES_CHECKER",
    ),
    IndicatorConfig(
        name="Retail Control",
        name_en="Retail Control",
        category=Category.CONSUMER,
        service_module="services.usa.retail_control_service",
        service_class="RetailControlService",
        service_instance="retail_control_service",
        fetch_method="get_retail_control_data",
        schedule_checker="RETAIL_SALES_CHECKER",
    ),

    # 消費者信頼感
    IndicatorConfig(
        name="CB消費者信頼感指数",
        name_en="CB Consumer Confidence",
        category=Category.CONSUMER,
        service_module="services.usa.cb_consumer_confidence_service",
        service_class="CBConsumerConfidenceService",
        service_instance="cb_consumer_confidence_service",
        fetch_method="get_cb_consumer_confidence_data",
        schedule_checker="CB_CONSUMER_CONFIDENCE_CHECKER",
    ),
    IndicatorConfig(
        name="ミシガン大学消費者信頼感指数",
        name_en="Michigan Consumer Sentiment",
        category=Category.CONSUMER,
        service_module="services.usa.michigan_consumer_sentiment_service",
        service_class="MichiganConsumerSentimentService",
        service_instance="michigan_consumer_sentiment_service",
        fetch_method="get_michigan_sentiment_data",
        schedule_checker="MICHIGAN_CONSUMER_SENTIMENT_CHECKER",
    ),

    # PCE関連
    IndicatorConfig(
        name="個人消費支出（PCE）",
        name_en="Personal Consumption Expenditures",
        category=Category.CONSUMER,
        service_module="services.usa.pce_service",
        service_class="PCEService",
        service_instance="pce_service",
        fetch_method="get_pce_data",
        schedule_checker="PERSONAL_INCOME_CHECKER",
    ),
    IndicatorConfig(
        name="PCEデフレーター飲食娯楽",
        name_en="PCE Food Recreation",
        category=Category.CONSUMER,
        service_module="services.usa.pce_food_recreation_service",
        service_class="PCEFoodRecreationService",
        service_instance="pce_food_recreation_service",
        fetch_method="get_pce_food_recreation_data",
        schedule_checker="PERSONAL_INCOME_CHECKER",
    ),

    # 個人所得関連
    IndicatorConfig(
        name="個人所得",
        name_en="Personal Income",
        category=Category.CONSUMER,
        service_module="services.usa.personal_income_service",
        service_class="PersonalIncomeService",
        service_instance="personal_income_service",
        fetch_method="get_personal_income_data",
        schedule_checker="PERSONAL_INCOME_CHECKER",
    ),
    IndicatorConfig(
        name="可処分所得",
        name_en="Disposable Personal Income",
        category=Category.CONSUMER,
        service_module="services.usa.disposable_income_service",
        service_class="DisposableIncomeService",
        service_instance="disposable_income_service",
        fetch_method="get_disposable_income_data",
        schedule_checker="PERSONAL_INCOME_CHECKER",
    ),
    IndicatorConfig(
        name="家計貯蓄率",
        name_en="Personal Saving Rate",
        category=Category.CONSUMER,
        service_module="services.usa.personal_saving_rate_service",
        service_class="PersonalSavingRateService",
        service_instance="personal_saving_rate_service",
        fetch_method="get_saving_rate_data",
        schedule_checker="PERSONAL_INCOME_CHECKER",
    ),

    # 週次指標
    IndicatorConfig(
        name="レッドブック",
        name_en="Redbook",
        category=Category.CONSUMER,
        service_module="services.usa.redbook_service",
        service_class="RedbookService",
        service_instance="redbook_service",
        fetch_method="get_redbook_data",
        schedule_checker="REDBOOK_CHECKER",
    ),

    # Consumer Credit
    IndicatorConfig(
        name="消費者信用残高",
        name_en="Consumer Credit",
        category=Category.CONSUMER,
        service_module="services.usa.consumer_credit_service",
        service_class="ConsumerCreditService",
        service_instance="consumer_credit_service",
        fetch_method="get_consumer_credit_data",
        schedule_checker="CONSUMER_CREDIT_CHECKER",
    ),

    # 自動車販売
    IndicatorConfig(
        name="自動車販売",
        name_en="Total Vehicle Sales",
        category=Category.CONSUMER,
        service_module="services.usa.total_vehicle_sales_service",
        service_class="TotalVehicleSalesService",
        service_instance="total_vehicle_sales_service",
        fetch_method="get_vehicle_sales_data",
        schedule_checker="VEHICLE_SALES_CHECKER",
    ),

    # CARTS（週次小売）
    IndicatorConfig(
        name="CARTS週次小売",
        name_en="CARTS Weekly Retail",
        category=Category.CONSUMER,
        service_module="services.usa.carts_service",
        service_class="CARTSService",
        service_instance="carts_service",
        fetch_method="get_carts_data",
        schedule_checker="CARTS_CHECKER",
    ),

    # 延滞率
    IndicatorConfig(
        name="延滞率",
        name_en="Delinquency Rate",
        category=Category.CONSUMER,
        service_module="services.usa.delinquency_rate_service",
        service_class="DelinquencyRateService",
        service_instance="delinquency_rate_service",
        fetch_method="get_delinquency_rate_data",
        schedule_checker="DELINQUENCY_RATE_CHECKER",
    ),

    # Visa Spending（特殊スケジュール）
    IndicatorConfig(
        name="Visa消費動向指数",
        name_en="Visa Spending Momentum",
        category=Category.CONSUMER,
        service_module="services.usa.visa_spending_service",
        service_class="VisaSpendingService",
        service_instance="visa_spending_service",
        fetch_method="get_visa_spending_data",
        schedule_checker="VISA_SPENDING_CHECKER",
        enabled=True,
    ),
]


# ============================================================
# 雇用関連 (EMPLOYMENT)
# ============================================================

EMPLOYMENT_INDICATORS: List[IndicatorConfig] = [
    # 雇用統計（BLS）
    IndicatorConfig(
        name="失業率",
        name_en="Unemployment Rate",
        category=Category.EMPLOYMENT,
        service_module="services.usa.unemployment_rate_service",
        service_class="UnemploymentRateService",
        service_instance="unemployment_rate_service",
        fetch_method="get_unemployment_data",
        schedule_checker="UNEMPLOYMENT_RATE_CHECKER",
    ),
    IndicatorConfig(
        name="失業理由別内訳",
        name_en="Unemployment by Reason",
        category=Category.EMPLOYMENT,
        service_module="services.usa.unemployment_by_reason_service",
        service_class="UnemploymentByReasonService",
        service_instance="unemployment_by_reason_service",
        fetch_method="get_unemployment_by_reason_data",
        schedule_checker="UNEMPLOYMENT_RATE_CHECKER",
    ),
    IndicatorConfig(
        name="非農業部門雇用者数",
        name_en="Nonfarm Payrolls",
        category=Category.EMPLOYMENT,
        service_module="services.usa.nonfarm_payrolls_service",
        service_class="NonfarmPayrollsService",
        service_instance="nonfarm_payrolls_service",
        fetch_method="get_nonfarm_payrolls_data",
        schedule_checker="UNEMPLOYMENT_RATE_CHECKER",
    ),
    IndicatorConfig(
        name="フルタイム/パートタイム雇用者数",
        name_en="Full/Part-time Employment",
        category=Category.EMPLOYMENT,
        service_module="services.usa.fullpart_time_employment_service",
        service_class="FullPartTimeEmploymentService",
        service_instance="fullpart_time_employment_service",
        fetch_method="get_employment_data",
        schedule_checker="UNEMPLOYMENT_RATE_CHECKER",
    ),
    IndicatorConfig(
        name="複数の仕事を持つ人/経済的理由によるパートタイム",
        name_en="Multiple Jobs/Part-time for Economic Reasons",
        category=Category.EMPLOYMENT,
        service_module="services.usa.multiple_jobs_parttime_service",
        service_class="MultipleJobsParttimeService",
        service_instance="multiple_jobs_parttime_service",
        fetch_method="get_multiple_jobs_parttime_data",
        schedule_checker="UNEMPLOYMENT_RATE_CHECKER",
    ),
    IndicatorConfig(
        name="労働参加率",
        name_en="Labor Force Participation Rate",
        category=Category.EMPLOYMENT,
        service_module="services.usa.labor_force_participation_service",
        service_class="LaborForceParticipationService",
        service_instance="labor_force_participation_service",
        fetch_method="get_lfpr_data",
        schedule_checker="UNEMPLOYMENT_RATE_CHECKER",
    ),
    IndicatorConfig(
        name="平均時給",
        name_en="Average Hourly Earnings",
        category=Category.EMPLOYMENT,
        service_module="services.usa.average_hourly_earnings_service",
        service_class="AverageHourlyEarningsService",
        service_instance="average_hourly_earnings_service",
        fetch_method="get_average_hourly_earnings_data",
        schedule_checker="UNEMPLOYMENT_RATE_CHECKER",
    ),
    IndicatorConfig(
        name="平均残業時間",
        name_en="Overtime Hours",
        category=Category.EMPLOYMENT,
        service_module="services.usa.overtime_hours_service",
        service_class="OvertimeHoursService",
        service_instance="overtime_hours_service",
        fetch_method="get_overtime_hours_data",
        schedule_checker="UNEMPLOYMENT_RATE_CHECKER",
    ),

    # 雇用コスト指数（四半期）
    IndicatorConfig(
        name="雇用コスト指数",
        name_en="Employment Cost Index",
        category=Category.EMPLOYMENT,
        service_module="services.usa.employment_cost_index_service",
        service_class="EmploymentCostIndexService",
        service_instance="employment_cost_index_service",
        fetch_method="get_eci_data",
        schedule_checker="EMPLOYMENT_COST_INDEX_CHECKER",
    ),

    # JOLTS
    IndicatorConfig(
        name="JOLTS求人/Indeed求人件数指数",
        name_en="JOLTS/Indeed Job Openings",
        category=Category.EMPLOYMENT,
        service_module="services.usa.jolts_indeed_service",
        service_class="JOLTSIndeedService",
        service_instance="jolts_indeed_service",
        fetch_method="get_job_openings_data",
        schedule_checker="JOLTS_OPENINGS_CHECKER",
    ),
    IndicatorConfig(
        name="JOLTS採用数/解雇数",
        name_en="JOLTS Hires/Layoffs",
        category=Category.EMPLOYMENT,
        service_module="services.usa.jolts_hires_layoffs_service",
        service_class="JOLTSHiresLayoffsService",
        service_instance="jolts_hires_layoffs_service",
        fetch_method="get_hires_layoffs_data",
        schedule_checker="JOLTS_OPENINGS_CHECKER",
    ),
    IndicatorConfig(
        name="失業者1人あたり求人数",
        name_en="Job Openings per Unemployed",
        category=Category.EMPLOYMENT,
        service_module="services.usa.job_openings_per_unemployed_service",
        service_class="JobOpeningsPerUnemployedService",
        service_instance="job_openings_per_unemployed_service",
        fetch_method="get_openings_per_unemployed_data",
        schedule_checker="JOLTS_OPENINGS_CHECKER",
    ),

    # 単位労働コスト
    IndicatorConfig(
        name="単位労働コスト",
        name_en="Unit Labor Cost",
        category=Category.EMPLOYMENT,
        service_module="services.usa.unit_labor_cost_service",
        service_class="UnitLaborCostService",
        service_instance="unit_labor_cost_service",
        fetch_method="get_unit_labor_cost_data",
        schedule_checker="UNIT_LABOR_COST_CHECKER",
    ),

    # Challenger人員削減
    IndicatorConfig(
        name="Challenger人員削減",
        name_en="Challenger Job Cuts",
        category=Category.EMPLOYMENT,
        service_module="services.usa.challenger_job_cuts_service",
        service_class="ChallengerJobCutsService",
        service_instance="challenger_job_cuts_service",
        fetch_method="get_job_cuts_data",
        schedule_checker="CHALLENGER_LAYOFFS_CHECKER",
    ),

    # ADP関連
    IndicatorConfig(
        name="ADP雇用者数",
        name_en="ADP Employment",
        category=Category.EMPLOYMENT,
        service_module="services.usa.adp_employment_service",
        service_class="ADPEmploymentService",
        service_instance="adp_employment_service",
        fetch_method="get_adp_employment_data",
        schedule_checker="ADP_EMPLOYMENT_CHECKER",
    ),
    IndicatorConfig(
        name="ADP賃金上昇率",
        name_en="ADP Wage Growth",
        category=Category.EMPLOYMENT,
        service_module="services.usa.adp_wage_growth_service",
        service_class="ADPWageGrowthService",
        service_instance="adp_wage_growth_service",
        fetch_method="get_adp_wage_growth_data",
        schedule_checker="ADP_EMPLOYMENT_CHECKER",
    ),

    # 週次失業保険申請件数
    IndicatorConfig(
        name="新規失業保険申請件数",
        name_en="Initial Jobless Claims",
        category=Category.EMPLOYMENT,
        service_module="services.usa.initial_claims_service",
        service_class="InitialClaimsService",
        service_instance="initial_claims_service",
        fetch_method="get_initial_claims_data",
        schedule_checker="WEEKLY_CLAIMS_CHECKER",
    ),
    IndicatorConfig(
        name="継続失業保険申請件数",
        name_en="Continuing Claims",
        category=Category.EMPLOYMENT,
        service_module="services.usa.continued_claims_service",
        service_class="ContinuedClaimsService",
        service_instance="continued_claims_service",
        fetch_method="get_continued_claims_data",
        schedule_checker="WEEKLY_CLAIMS_CHECKER",
    ),

    # CB雇用判断
    IndicatorConfig(
        name="CB雇用機会業況判断",
        name_en="CB Jobs Labor Differential",
        category=Category.EMPLOYMENT,
        service_module="services.usa.cb_jobs_labor_differential_service",
        service_class="CBJobsLaborDifferentialService",
        service_instance="cb_jobs_labor_differential_service",
        fetch_method="get_jobs_labor_data",
        schedule_checker="CB_CONSUMER_CONFIDENCE_CHECKER",
    ),

    # NER Pulse（特殊スケジュール）
    IndicatorConfig(
        name="NER Pulse週次雇用変動",
        name_en="NER Pulse Weekly Employment",
        category=Category.EMPLOYMENT,
        service_module="services.usa.ner_pulse_service",
        service_class="NERPulseService",
        service_instance="ner_pulse_service",
        fetch_method="get_ner_pulse_data",
        schedule_checker="NER_PULSE_CHECKER",
        enabled=True,
    ),

    # 賃金トラッカー（特殊スケジュール）
    IndicatorConfig(
        name="Atlanta Fed賃金トラッカー",
        name_en="Atlanta Fed Wage Tracker",
        category=Category.EMPLOYMENT,
        service_module="services.usa.atlanta_fed_wage_service",
        service_class="AtlantaFedWageService",
        service_instance="atlanta_fed_wage_service",
        fetch_method="get_atlanta_fed_wage_data",
        schedule_checker="ATLANTA_FED_WAGE_CHECKER",
        enabled=True,
    ),
    IndicatorConfig(
        name="Indeed賃金トラッカー",
        name_en="Indeed Wage Tracker",
        category=Category.EMPLOYMENT,
        service_module="services.usa.indeed_wage_tracker_service",
        service_class="IndeedWageTrackerService",
        service_instance="indeed_wage_tracker_service",
        fetch_method="get_indeed_wage_data",
        schedule_checker="INDEED_WAGE_CHECKER",
        enabled=True,
    ),
]


# ============================================================
# 全指標リスト
# ============================================================

ALL_INDICATORS: List[IndicatorConfig] = (
    MONETARY_POLICY_INDICATORS +
    ECONOMY_INDICATORS +
    CONSUMER_INDICATORS +
    EMPLOYMENT_INDICATORS
)


def get_indicators_by_category(category: Category) -> List[IndicatorConfig]:
    """カテゴリ別に指標を取得"""
    return [ind for ind in ALL_INDICATORS if ind.category == category and ind.enabled]


def get_indicators_by_schedule_checker(checker_name: str) -> List[IndicatorConfig]:
    """同じスケジュールチェッカーを使用する指標をグループ化"""
    return [ind for ind in ALL_INDICATORS if ind.schedule_checker == checker_name and ind.enabled]


def get_enabled_indicators() -> List[IndicatorConfig]:
    """有効な指標のみ取得"""
    return [ind for ind in ALL_INDICATORS if ind.enabled]


def get_indicator_summary() -> Dict[str, Any]:
    """指標サマリーを取得"""
    enabled = get_enabled_indicators()
    by_category = {}
    for cat in Category:
        indicators = get_indicators_by_category(cat)
        by_category[cat.value] = {
            "count": len(indicators),
            "indicators": [ind.name for ind in indicators]
        }

    # スケジュールチェッカー別グループ
    checker_groups = {}
    for ind in enabled:
        checker = ind.schedule_checker or "NONE"
        if checker not in checker_groups:
            checker_groups[checker] = []
        checker_groups[checker].append(ind.name)

    return {
        "total": len(enabled),
        "by_category": by_category,
        "by_schedule_checker": checker_groups
    }
