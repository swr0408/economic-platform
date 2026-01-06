/**
 * オーバーレイ機能の設定定義
 * 色パレット・カテゴリ・比較可能な指標リスト
 */

// =============================================================================
// 型定義
// =============================================================================

export type IndicatorFrequency = 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'irregular';

export type AxisOption = 'auto' | 'left' | 'right';

export type TransformOption = 'raw' | 'index100';

export type DisplayOption = 'step' | 'dots';

export type DerivedValueType = 'diff';

export interface DerivedValueConfig {
  type: DerivedValueType;
  sourceField: string;
}

export interface OverlayIndicator {
  id: string;
  name: string;
  nameEn: string;
  frequency: IndicatorFrequency;
  country?: string;
  category: string;
  subCategory?: string;
  chartType?: 'line' | 'bar';
  apiEndpoint: string;
  dataKey: string;
  nestedKey?: string;  // カテゴリ配列データ内の特定カテゴリキー（例: ppi_categories内の'airline_passenger'）
  derived?: DerivedValueConfig;
  valueField?: string;  // 使用するフィールド名（省略時は自動検出）
  unit?: string;
}

export interface OverlaySettings {
  axis: AxisOption;
  transform: TransformOption;
  display: DisplayOption;
}

export interface OverlayConfig {
  indicator: OverlayIndicator;
  settings: OverlaySettings;
}

// =============================================================================
// 色パレット
// =============================================================================

/** メイン指標の色（固定） */
export const MAIN_INDICATOR_COLOR = '#2196f3';

/** 比較指標の色パレット（順番に割り当て、6色対応） */
export const OVERLAY_COLORS = [
  '#4caf50', // 緑
  '#ef5350', // 赤
  '#42a5f5', // 青
  '#ff9800', // オレンジ
  '#9c27b0', // 紫
  '#ffffff', // 白
] as const;

/** 色を取得 */
export function getOverlayColor(index: number): string {
  return OVERLAY_COLORS[index % OVERLAY_COLORS.length];
}

// =============================================================================
// 頻度ラベル
// =============================================================================

export const FREQUENCY_LABELS: Record<IndicatorFrequency, string> = {
  daily: '日次',
  weekly: '週次',
  monthly: '月次',
  quarterly: '四半期',
  irregular: '不定期',
};

export function getFrequencyLabel(frequency: IndicatorFrequency): string {
  return FREQUENCY_LABELS[frequency];
}

/**
 * 頻度の優先順位（数値が小さいほど細かい）
 * 日次 > 週次 > 月次 > 四半期
 */
export const FREQUENCY_PRIORITY: Record<IndicatorFrequency, number> = {
  daily: 1,
  weekly: 2,
  monthly: 3,
  quarterly: 4,
  irregular: 3, // 不定期は月次扱い
};

/**
 * 最も細かい頻度を取得
 */
export function getFinestFrequency(frequencies: IndicatorFrequency[]): IndicatorFrequency {
  if (frequencies.length === 0) return 'monthly';

  let finest: IndicatorFrequency = frequencies[0];
  let finestPriority = FREQUENCY_PRIORITY[finest];

  for (const freq of frequencies) {
    const priority = FREQUENCY_PRIORITY[freq];
    if (priority < finestPriority) {
      finest = freq;
      finestPriority = priority;
    }
  }

  return finest;
}

// =============================================================================
// カテゴリ定義（階層構造）
// =============================================================================

export const INDICATOR_CATEGORIES = {
  policy: '政策',
  economy: '経済',
  consumer: '消費',
  employment: '雇用',
  prices: '物価',
  housing: '住宅',
  market: '市場',
} as const;

export const INDICATOR_SUB_CATEGORIES = {
  // 政策
  interest_rate: '金利',
  fed: 'FRB',
  // 経済
  gdp: 'GDP',
  sentiment: '景況感',
  production: '生産',
  // 消費
  retail: '小売',
  spending: '支出',
  confidence: '消費者信頼感',
  // 雇用
  jobs: '雇用統計',
  claims: '失業保険',
  wages: '賃金',
  // 物価
  cpi: 'CPI',
  ppi: 'PPI',
  pce_deflator: 'PCEデフレーター',
  // 住宅
  starts: '住宅着工',
  sales: '住宅販売',
  permits: '建設許可',
  // 市場
  forex_usd: 'ドルストレート',
  forex_jpy: 'クロス円',
  forex_cross: 'その他クロス',
  forex_index: '通貨インデックス',
  index_us: '米国株価指数',
  index_asia: '日本・アジア株価指数',
  index_europe: '欧州株価指数',
  bond: '債券利回り',
  commodity_metal: '貴金属',
  commodity_energy: 'エネルギー',
  calculated: '計算値',
} as const;

export const INDICATOR_COUNTRIES = {
  usa: 'アメリカ',
  japan: '日本',
  eurozone: 'ユーロ圏',
  uk: 'イギリス',
  china: '中国',
  australia: 'オーストラリア',
  newzealand: 'ニュージーランド',
  canada: 'カナダ',
  switzerland: 'スイス',
} as const;

export type IndicatorCountry = keyof typeof INDICATOR_COUNTRIES;

const DEFAULT_INDICATOR_COUNTRY: IndicatorCountry = 'usa';

export function getIndicatorCountry(indicator: OverlayIndicator): IndicatorCountry {
  return (indicator.country || DEFAULT_INDICATOR_COUNTRY) as IndicatorCountry;
}

export type IndicatorCategory = keyof typeof INDICATOR_CATEGORIES;

// =============================================================================
// 比較可能な指標リスト（全指標）
// =============================================================================

export const OVERLAY_INDICATORS: OverlayIndicator[] = [
  // =========================================================================
  // 経済 - GDP
  // =========================================================================
  {
    id: 'gdp_growth',
    name: 'GDP成長率（前期比年率）',
    nameEn: 'GDP Growth Rate (QoQ SAAR)',
    frequency: 'quarterly',
    category: 'economy',
    subCategory: 'gdp',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'gdp_growth_rate',
    unit: '%',
  },
  {
    id: 'potential_gdp_real',
    name: '実質潜在成長率',
    nameEn: 'Real Potential GDP Growth',
    frequency: 'quarterly',
    category: 'economy',
    subCategory: 'gdp',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'potential_gdp',
    valueField: 'real',
    unit: '%',
  },
  {
    id: 'potential_gdp_nominal',
    name: '名目潜在成長率',
    nameEn: 'Nominal Potential GDP Growth',
    frequency: 'quarterly',
    category: 'economy',
    subCategory: 'gdp',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'potential_gdp',
    valueField: 'nominal',
    unit: '%',
  },

  // =========================================================================
  // 経済 - 金融環境
  // =========================================================================
  {
    id: 'bank_lending',
    name: '銀行貸し出し態度（SLOOS）',
    nameEn: 'Senior Loan Officer Survey',
    frequency: 'quarterly',
    category: 'economy',
    subCategory: 'sentiment',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'bank_lending',
    unit: '%',
  },
  {
    id: 'fci_baseline',
    name: 'FCI-G（Baseline 3年）',
    nameEn: 'FCI-G Baseline (3-year)',
    frequency: 'monthly',
    category: 'economy',
    subCategory: 'sentiment',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'fci',
    valueField: 'baseline.data',
  },
  {
    id: 'fci_oneyear',
    name: 'FCI-G（1年ルックバック）',
    nameEn: 'FCI-G One-year Lookback',
    frequency: 'monthly',
    category: 'economy',
    subCategory: 'sentiment',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'fci',
    valueField: 'oneyear.data',
  },
  {
    id: 'nfci',
    name: 'シカゴ連銀金融環境指数（NFCI）',
    nameEn: 'Chicago Fed NFCI',
    frequency: 'weekly',
    category: 'economy',
    subCategory: 'sentiment',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'nfci',
  },

  // =========================================================================
  // 経済 - 景況感
  // =========================================================================
  {
    id: 'ism_manufacturing',
    name: 'ISM製造業景況指数',
    nameEn: 'ISM Manufacturing PMI',
    frequency: 'monthly',
    category: 'economy',
    subCategory: 'sentiment',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'ism_manufacturing',
  },
  {
    id: 'ism_order_inventory_balance',
    name: 'ISM製造業受注在庫バランス',
    nameEn: 'ISM Order-Inventory Balance',
    frequency: 'monthly',
    category: 'economy',
    subCategory: 'sentiment',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'ism_components',
    valueField: 'order_inventory_balance',
  },
  {
    id: 'ism_order_inventory_balance_3ma',
    name: 'ISM製造業受注在庫バランス（3MA）',
    nameEn: 'ISM Order-Inventory Balance (3MA)',
    frequency: 'monthly',
    category: 'economy',
    subCategory: 'sentiment',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'ism_components',
    valueField: 'order_inventory_balance_3ma',
  },
  {
    id: 'ism_non_manufacturing',
    name: 'ISM非製造業景況指数',
    nameEn: 'ISM Non-Manufacturing PMI',
    frequency: 'monthly',
    category: 'economy',
    subCategory: 'sentiment',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'ism_non_manufacturing',
  },
  {
    id: 'empire_state',
    name: 'NY連銀製造業景気指数',
    nameEn: 'Empire State Manufacturing',
    frequency: 'monthly',
    category: 'economy',
    subCategory: 'sentiment',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'empire_state',
    valueField: 'current',
  },
  {
    id: 'philadelphia_fed',
    name: 'フィラデルフィア連銀製造業景気指数',
    nameEn: 'Philadelphia Fed Manufacturing',
    frequency: 'monthly',
    category: 'economy',
    subCategory: 'sentiment',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'philadelphia_fed',
    valueField: 'general_activity_current',
  },
  {
    id: 'nfib',
    name: 'NFIB中小企業楽観指数',
    nameEn: 'NFIB Small Business Optimism',
    frequency: 'monthly',
    category: 'economy',
    subCategory: 'sentiment',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'nfib',
  },
  {
    id: 'nfib_capex',
    name: 'NFIB設備投資計画',
    nameEn: 'NFIB Capital Expenditure Plans',
    frequency: 'monthly',
    category: 'economy',
    subCategory: 'sentiment',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'nfib_capex',
    valueField: 'value',
    unit: '%',
  },

  // =========================================================================
  // 経済 - 生産
  // =========================================================================
  {
    id: 'industrial_production_mom',
    name: '鉱工業生産（前月比）',
    nameEn: 'Industrial Production MoM',
    frequency: 'monthly',
    category: 'economy',
    subCategory: 'production',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'industrial_production',
    valueField: 'mom',
    chartType: 'bar',
    unit: '%',
  },
  {
    id: 'industrial_production_yoy',
    name: '鉱工業生産（前年比）',
    nameEn: 'Industrial Production YoY',
    frequency: 'monthly',
    category: 'economy',
    subCategory: 'production',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'industrial_production',
    valueField: 'yoy',
    unit: '%',
  },
  {
    id: 'industrial_production_index',
    name: '鉱工業生産（指数）',
    nameEn: 'Industrial Production Index',
    frequency: 'monthly',
    category: 'economy',
    subCategory: 'production',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'industrial_production',
    valueField: 'value',
  },
  {
    id: 'capacity_utilization',
    name: '設備稼働率',
    nameEn: 'Capacity Utilization',
    frequency: 'monthly',
    category: 'economy',
    subCategory: 'production',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'capacity_utilization',
  },
  {
    id: 'durable_goods_mom',
    name: '耐久財受注（前月比）',
    nameEn: 'Durable Goods Orders MoM',
    frequency: 'monthly',
    category: 'economy',
    subCategory: 'production',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'durable_goods',
    valueField: 'mom',
    chartType: 'bar',
    unit: '%',
  },
  {
    id: 'durable_goods_yoy',
    name: '耐久財受注（前年比）',
    nameEn: 'Durable Goods Orders YoY',
    frequency: 'monthly',
    category: 'economy',
    subCategory: 'production',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'durable_goods',
    valueField: 'yoy',
    unit: '%',
  },
  {
    id: 'durable_goods_value',
    name: '耐久財受注（原数値）',
    nameEn: 'Durable Goods Orders (Value)',
    frequency: 'monthly',
    category: 'economy',
    subCategory: 'production',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'durable_goods',
    valueField: 'value',
    unit: 'M',
  },
  {
    id: 'durable_goods_ex_transport_mom',
    name: '耐久財受注（輸送除く・前月比）',
    nameEn: 'Durable Goods ex Transport MoM',
    frequency: 'monthly',
    category: 'economy',
    subCategory: 'production',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'durable_goods',
    valueField: 'ex_transport_mom',
    chartType: 'bar',
    unit: '%',
  },

  // =========================================================================
  // 雇用 - 雇用統計
  // =========================================================================
  {
    id: 'unemployment_rate',
    name: '失業率',
    nameEn: 'Unemployment Rate',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'jobs',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'unemployment_rate',
    valueField: 'unrate',
    unit: '%',
  },
  {
    id: 'u6_unemployment_rate',
    name: '広義の失業率 (U-6)',
    nameEn: 'U-6 Unemployment Rate',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'jobs',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'unemployment_rate',
    valueField: 'u6rate',
    unit: '%',
  },
  {
    id: 'unemployment_layoff',
    name: '失業率（レイオフ）',
    nameEn: 'Unemployment - Layoff',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'jobs',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'unemployment_by_reason',
    valueField: 'layoff',
    unit: 'K',
  },
  {
    id: 'unemployment_other_losers',
    name: '失業率（レイオフ以外）',
    nameEn: 'Unemployment - Other Losers',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'jobs',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'unemployment_by_reason',
    valueField: 'other_losers',
    unit: 'K',
  },
  {
    id: 'unemployment_leavers',
    name: '失業率（自発的離職者）',
    nameEn: 'Unemployment - Leavers',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'jobs',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'unemployment_by_reason',
    valueField: 'leavers',
    unit: 'K',
  },
  {
    id: 'unemployment_reentrants',
    name: '失業率（再参入者）',
    nameEn: 'Unemployment - Reentrants',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'jobs',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'unemployment_by_reason',
    valueField: 'reentrants',
    unit: 'K',
  },
  {
    id: 'unemployment_new_entrants',
    name: '失業率（新規参入者）',
    nameEn: 'Unemployment - New Entrants',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'jobs',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'unemployment_by_reason',
    valueField: 'new_entrants',
    unit: 'K',
  },
  {
    id: 'nonfarm_payrolls',
    name: '非農業部門雇用者数（増減）',
    nameEn: 'Nonfarm Payrolls Change',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'jobs',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'nonfarm_payrolls',
    derived: { type: 'diff', sourceField: 'nonfarm' },
    chartType: 'bar',
    unit: 'K',
  },
  {
    id: 'fulltime_employment',
    name: 'フルタイム雇用者数（増減）',
    nameEn: 'Full-Time Employment Change',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'jobs',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'fullpart_time_employment',
    derived: { type: 'diff', sourceField: 'fulltime' },
    chartType: 'bar',
    unit: 'K',
  },
  {
    id: 'parttime_employment',
    name: 'パートタイム雇用者数（増減）',
    nameEn: 'Part-Time Employment Change',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'jobs',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'fullpart_time_employment',
    derived: { type: 'diff', sourceField: 'parttime' },
    chartType: 'bar',
    unit: 'K',
  },
  {
    id: 'multiple_jobs',
    name: '複数の仕事を持つ人（増減）',
    nameEn: 'Multiple Jobholders Change',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'jobs',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'multiple_jobs_parttime',
    derived: { type: 'diff', sourceField: 'multiple_jobs' },
    chartType: 'bar',
    unit: 'K',
  },
  {
    id: 'parttime_economic',
    name: '経済的理由によるパートタイム（増減）',
    nameEn: 'Part-Time for Economic Reasons Change',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'jobs',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'multiple_jobs_parttime',
    derived: { type: 'diff', sourceField: 'parttime_econ' },
    chartType: 'bar',
    unit: 'K',
  },
  {
    id: 'adp_employment',
    name: 'ADP雇用者数（増減）',
    nameEn: 'ADP Employment Change',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'jobs',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'adp_employment',
    valueField: 'mom',
    chartType: 'bar',
    unit: 'K',
  },
  {
    id: 'jolts_openings',
    name: 'JOLTS求人件数',
    nameEn: 'JOLTS Job Openings',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'jobs',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'jolts_indeed',
    valueField: 'jolts',
    unit: 'K',
  },
  {
    id: 'job_openings_per_unemployed',
    name: '求人倍率',
    nameEn: 'Job Openings per Unemployed',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'jobs',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'job_openings_per_unemployed',
    valueField: 'value',
  },
  {
    id: 'labor_force_participation',
    name: '労働参加率',
    nameEn: 'Labor Force Participation Rate',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'jobs',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'labor_force_participation',
    unit: '%',
  },

  // =========================================================================
  // 雇用 - 失業保険
  // =========================================================================
  {
    id: 'initial_claims',
    name: '新規失業保険申請件数',
    nameEn: 'Initial Jobless Claims',
    frequency: 'weekly',
    category: 'employment',
    subCategory: 'claims',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'initial_claims',
    valueField: 'icsa',
    unit: 'K',
  },
  {
    id: 'continued_claims',
    name: '継続受給者数',
    nameEn: 'Continued Jobless Claims',
    frequency: 'weekly',
    category: 'employment',
    subCategory: 'claims',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'continued_claims',
    valueField: 'ccsa',
    unit: 'K',
  },
  {
    id: 'challenger_job_cuts',
    name: 'チャレンジャー人員削減',
    nameEn: 'Challenger Job Cuts',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'claims',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'challenger_job_cuts',
    unit: 'K',
  },

  // =========================================================================
  // 雇用 - 賃金
  // =========================================================================
  {
    id: 'average_hourly_earnings_yoy',
    name: '平均時給（前年比）',
    nameEn: 'Average Hourly Earnings YoY',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'wages',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'average_hourly_earnings',
    valueField: 'yoy',
    unit: '%',
  },
  {
    id: 'average_hourly_earnings_mom',
    name: '平均時給（前月比）',
    nameEn: 'Average Hourly Earnings MoM',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'wages',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'average_hourly_earnings',
    valueField: 'mom',
    chartType: 'bar',
    unit: '%',
  },
  {
    id: 'atlanta_fed_wage',
    name: 'アトランタ連銀賃金トラッカー',
    nameEn: 'Atlanta Fed Wage Tracker',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'wages',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'atlanta_fed_wage',
    unit: '%',
  },
  {
    id: 'employment_cost_index',
    name: '雇用コスト指数',
    nameEn: 'Employment Cost Index',
    frequency: 'quarterly',
    category: 'employment',
    subCategory: 'wages',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'employment_cost_index',
    valueField: 'pch',
    unit: '%',
  },
  {
    id: 'unit_labor_cost',
    name: '単位労働コスト',
    nameEn: 'Unit Labor Cost',
    frequency: 'quarterly',
    category: 'employment',
    subCategory: 'wages',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'unit_labor_cost',
    valueField: 'ulc_pch',
    unit: '%',
  },
  {
    id: 'labor_productivity',
    name: '労働生産性',
    nameEn: 'Labor Productivity',
    frequency: 'quarterly',
    category: 'employment',
    subCategory: 'wages',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'unit_labor_cost',
    valueField: 'productivity_pch',
    unit: '%',
  },
  {
    id: 'indeed_wage_tracker',
    name: 'Indeed賃金トラッカー',
    nameEn: 'Indeed Wage Tracker',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'wages',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'indeed_wage_tracker',
    valueField: 'value',
    unit: '%',
  },
  {
    id: 'nfib_compensation_plans',
    name: 'NFIB人件費計画',
    nameEn: 'NFIB Compensation Plans',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'wages',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'nfib_compensation',
    valueField: 'compensation_plans',
    unit: '%',
  },
  {
    id: 'nfib_hiring_plans',
    name: 'NFIB雇用計画',
    nameEn: 'NFIB Hiring Plans',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'wages',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'nfib_compensation',
    valueField: 'hiring_plans',
    unit: '%',
  },
  {
    id: 'overtime_hours',
    name: '平均残業時間',
    nameEn: 'Overtime Hours',
    frequency: 'monthly',
    category: 'employment',
    subCategory: 'wages',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'overtime_hours',
    valueField: 'value',
    unit: 'H',
  },

  // =========================================================================
  // 消費 - 小売
  // =========================================================================
  {
    id: 'carts',
    name: 'シカゴ連銀小売指数（CARTS）',
    nameEn: 'Chicago Fed CARTS',
    frequency: 'weekly',
    category: 'consumer',
    subCategory: 'retail',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'carts',
    valueField: 'weekly.nominal',
  },
  {
    id: 'visa_spending',
    name: 'Visa支出モメンタム指数',
    nameEn: 'Visa Spending Momentum',
    frequency: 'weekly',
    category: 'consumer',
    subCategory: 'retail',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'visa_spending',
    valueField: 'value',
    unit: '%',
  },
  {
    id: 'affinity_spending',
    name: 'クレジット/デビットカード支出',
    nameEn: 'Credit/Debit Card Spending',
    frequency: 'weekly',
    category: 'consumer',
    subCategory: 'retail',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'affinity_spend',
    unit: '%',
  },
  {
    id: 'retail_sales_mom',
    name: '小売売上高（前月比）',
    nameEn: 'Retail Sales MoM',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'retail',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'retail_sales',
    valueField: 'mom',
    chartType: 'bar',
    unit: '%',
  },
  {
    id: 'retail_sales_yoy',
    name: '小売売上高（前年比）',
    nameEn: 'Retail Sales YoY',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'retail',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'retail_sales',
    valueField: 'yoy',
    unit: '%',
  },
  {
    id: 'retail_sales_value',
    name: '小売売上高（原数値）',
    nameEn: 'Retail Sales (Value)',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'retail',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'retail_sales',
    valueField: 'value',
    unit: 'M',
  },
  {
    id: 'retail_sales_ex_auto_mom',
    name: '小売売上高（自動車除く・前月比）',
    nameEn: 'Retail Sales ex Auto MoM',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'retail',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'retail_sales',
    valueField: 'ex_auto_mom',
    chartType: 'bar',
    unit: '%',
  },
  {
    id: 'retail_sales_ex_auto_yoy',
    name: '小売売上高（自動車除く・前年比）',
    nameEn: 'Retail Sales ex Auto YoY',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'retail',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'retail_sales',
    valueField: 'ex_auto_yoy',
    unit: '%',
  },
  {
    id: 'retail_control',
    name: 'コントロールグループ（前月比）',
    nameEn: 'Retail Control MoM',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'retail',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'retail_control',
    valueField: 'mom',
    chartType: 'bar',
    unit: '%',
  },
  {
    id: 'total_vehicle_sales',
    name: '自動車販売台数',
    nameEn: 'Total Vehicle Sales',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'retail',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'total_vehicle_sales',
    unit: 'M',
  },
  {
    id: 'redbook',
    name: 'レッドブック（前年比）',
    nameEn: 'Redbook YoY',
    frequency: 'weekly',
    category: 'consumer',
    subCategory: 'retail',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'redbook',
    unit: '%',
  },

  // =========================================================================
  // 消費 - 支出
  // =========================================================================
  {
    id: 'pce_mom',
    name: 'PCE（前月比）',
    nameEn: 'PCE MoM',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'spending',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'pce',
    valueField: 'nominal.mom',
    chartType: 'bar',
    unit: '%',
  },
  {
    id: 'pce_food_services_yoy',
    name: 'PCEデフレーター飲食宿泊（前年比）',
    nameEn: 'PCE Food Services YoY',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'spending',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'pce_food_recreation',
    valueField: 'food_services_yoy',
    unit: '%',
  },
  {
    id: 'pce_recreation_yoy',
    name: 'PCEデフレーター娯楽（前年比）',
    nameEn: 'PCE Recreation YoY',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'spending',
    apiEndpoint: '/api/usa/employment',
    dataKey: 'pce_food_recreation',
    valueField: 'recreation_yoy',
    unit: '%',
  },
  {
    id: 'personal_income_mom',
    name: '個人所得（前月比）',
    nameEn: 'Personal Income MoM',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'spending',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'personal_income',
    valueField: 'nominal.mom',
    chartType: 'bar',
    unit: '%',
  },
  {
    id: 'personal_income_yoy',
    name: '個人所得（前年比）',
    nameEn: 'Personal Income YoY',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'spending',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'personal_income',
    valueField: 'nominal.yoy',
    unit: '%',
  },
  {
    id: 'personal_saving_rate',
    name: '個人貯蓄率',
    nameEn: 'Personal Saving Rate',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'spending',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'personal_saving_rate',
    unit: '%',
  },
  {
    id: 'disposable_income',
    name: '可処分所得（前年比）',
    nameEn: 'Disposable Income YoY',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'spending',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'disposable_income',
    valueField: 'yoy',
    unit: '%',
  },
  {
    id: 'delinquency_rate',
    name: 'クレジットカードローン延滞率',
    nameEn: 'Credit Card Delinquency Rate',
    frequency: 'quarterly',
    category: 'consumer',
    subCategory: 'spending',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'delinquency_rate',
    unit: '%',
  },
  {
    id: 'consumer_credit',
    name: 'クレジットカードローン残高（前月比）',
    nameEn: 'Credit Card Loan MoM',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'spending',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'consumer_credit',
    valueField: 'mom',
    chartType: 'bar',
    unit: '%',
  },
  {
    id: 'consumer_credit_value',
    name: 'クレジットカードローン残高（原数値）',
    nameEn: 'Credit Card Loan (Value)',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'spending',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'consumer_credit',
    valueField: 'value',
    unit: 'B',
  },

  // =========================================================================
  // 消費 - 消費者信頼感
  // =========================================================================
  {
    id: 'cb_consumer_confidence',
    name: 'CB消費者信頼感指数',
    nameEn: 'CB Consumer Confidence',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'confidence',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'cb_consumer_confidence',
  },
  {
    id: 'cb_jobs_plentiful',
    name: 'CB雇用機会業況判断（仕事豊富）',
    nameEn: 'CB Jobs Plentiful',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'confidence',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'cb_jobs_labor',
    valueField: 'plentiful',
    unit: '%',
  },
  {
    id: 'cb_jobs_hard',
    name: 'CB雇用機会業況判断（仕事困難）',
    nameEn: 'CB Jobs Hard to Get',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'confidence',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'cb_jobs_labor',
    valueField: 'hard',
    unit: '%',
  },
  {
    id: 'cb_jobs_differential',
    name: 'CB雇用機会業況判断（差分）',
    nameEn: 'CB Jobs Differential',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'confidence',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'cb_jobs_labor',
    valueField: 'differential',
    unit: '%',
  },
  {
    id: 'michigan_consumer_sentiment',
    name: 'ミシガン大学消費者信頼感指数',
    nameEn: 'Michigan Consumer Sentiment',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'confidence',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'michigan_consumer_sentiment',
  },

  // =========================================================================
  // 物価 - CPI
  // =========================================================================
  {
    id: 'us_cpi_yoy',
    name: 'CPI（前年比）',
    nameEn: 'CPI YoY',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'cpi',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'cpi',
    valueField: 'yoy',
    unit: '%',
  },
  {
    id: 'us_cpi_mom',
    name: 'CPI（前月比）',
    nameEn: 'CPI MoM',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'cpi',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'cpi',
    valueField: 'mom',
    chartType: 'bar',
    unit: '%',
  },
  {
    id: 'us_core_cpi_yoy',
    name: 'コアCPI（前年比）',
    nameEn: 'Core CPI YoY',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'cpi',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'core_cpi',
    valueField: 'yoy',
    unit: '%',
  },
  {
    id: 'us_core_cpi_mom',
    name: 'コアCPI（前月比）',
    nameEn: 'Core CPI MoM',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'cpi',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'core_cpi',
    valueField: 'mom',
    chartType: 'bar',
    unit: '%',
  },

  // =========================================================================
  // 物価 - PCEデフレーター
  // =========================================================================
  {
    id: 'us_pce_deflator_yoy',
    name: 'PCEデフレーター（前年比）',
    nameEn: 'PCE Deflator YoY',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'pce',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'pce_deflator',
    valueField: 'yoy',
    unit: '%',
  },
  {
    id: 'us_pce_deflator_mom',
    name: 'PCEデフレーター（前月比）',
    nameEn: 'PCE Deflator MoM',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'pce',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'pce_deflator',
    valueField: 'mom',
    chartType: 'bar',
    unit: '%',
  },
  {
    id: 'us_core_pce_deflator_yoy',
    name: 'コアPCEデフレーター（前年比）',
    nameEn: 'Core PCE Deflator YoY',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'pce',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'core_pce_deflator',
    valueField: 'yoy',
    unit: '%',
  },
  {
    id: 'us_core_pce_deflator_mom',
    name: 'コアPCEデフレーター（前月比）',
    nameEn: 'Core PCE Deflator MoM',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'pce',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'core_pce_deflator',
    valueField: 'mom',
    chartType: 'bar',
    unit: '%',
  },

  // =========================================================================
  // 物価 - PPI（生産者物価指数）
  // =========================================================================
  {
    id: 'us_ppi_yoy',
    name: 'PPI（前年比）',
    nameEn: 'PPI YoY',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'ppi',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'ppi',
    valueField: 'yoy',
    unit: '%',
  },
  {
    id: 'us_ppi_mom',
    name: 'PPI（前月比）',
    nameEn: 'PPI MoM',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'ppi',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'ppi',
    valueField: 'mom',
    chartType: 'bar',
    unit: '%',
  },
  {
    id: 'us_core_ppi_yoy',
    name: 'コアPPI（前年比）',
    nameEn: 'Core PPI YoY',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'ppi',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'core_ppi',
    valueField: 'yoy',
    unit: '%',
  },
  {
    id: 'us_core_ppi_mom',
    name: 'コアPPI（前月比）',
    nameEn: 'Core PPI MoM',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'ppi',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'core_ppi',
    valueField: 'mom',
    chartType: 'bar',
    unit: '%',
  },

  // =========================================================================
  // 物価 - PPI項目別（PCEデフレーター算出項目）
  // =========================================================================
  {
    id: 'us_ppi_airline_passenger_yoy',
    name: 'PPI 航空会社乗客サービス（前年比）',
    nameEn: 'PPI Airline Passenger Services YoY',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'ppi_categories',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'ppi_categories',
    nestedKey: 'airline_passenger',
    valueField: 'yoy',
    unit: '%',
  },
  {
    id: 'us_ppi_portfolio_management_yoy',
    name: 'PPI ポートフォリオ管理（前年比）',
    nameEn: 'PPI Portfolio Management YoY',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'ppi_categories',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'ppi_categories',
    nestedKey: 'portfolio_management',
    valueField: 'yoy',
    unit: '%',
  },
  {
    id: 'us_ppi_medical_care_yoy',
    name: 'PPI 医療ケア（前年比）',
    nameEn: 'PPI Medical Care YoY',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'ppi_categories',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'ppi_categories',
    nestedKey: 'medical_care',
    valueField: 'yoy',
    unit: '%',
  },
  {
    id: 'us_ppi_home_health_hospice_yoy',
    name: 'PPI 在宅医療・ホスピスケア（前年比）',
    nameEn: 'PPI Home Health Care, Hospice YoY',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'ppi_categories',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'ppi_categories',
    nestedKey: 'home_health_hospice',
    valueField: 'yoy',
    unit: '%',
  },
  {
    id: 'us_ppi_hospital_outpatient_yoy',
    name: 'PPI 病院外来医療（前年比）',
    nameEn: 'PPI Hospital Outpatient YoY',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'ppi_categories',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'ppi_categories',
    nestedKey: 'hospital_outpatient',
    valueField: 'yoy',
    unit: '%',
  },
  {
    id: 'us_ppi_hospital_inpatient_yoy',
    name: 'PPI 病院入院治療（前年比）',
    nameEn: 'PPI Hospital Inpatient YoY',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'ppi_categories',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'ppi_categories',
    nestedKey: 'hospital_inpatient',
    valueField: 'yoy',
    unit: '%',
  },
  {
    id: 'us_ppi_nursing_home_yoy',
    name: 'PPI 特別養護老人ホームケア（前年比）',
    nameEn: 'PPI Nursing Home Care YoY',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'ppi_categories',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'ppi_categories',
    nestedKey: 'nursing_home',
    valueField: 'yoy',
    unit: '%',
  },

  // =========================================================================
  // 物価 - 住宅関連指標
  // =========================================================================
  {
    id: 'us_zillow_rent_yoy',
    name: 'Zillow家賃指数（前年比）',
    nameEn: 'Zillow Rent Index YoY',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'cpi',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'housing_indicators',
    valueField: 'zillow',
    unit: '%',
  },
  {
    id: 'us_case_shiller_yoy',
    name: 'ケースシラー住宅価格指数（前年比）',
    nameEn: 'Case-Shiller Home Price Index YoY',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'cpi',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'housing_indicators',
    valueField: 'case_shiller',
    unit: '%',
  },
  {
    id: 'us_rent_cpi_yoy',
    name: '家賃CPI（前年比）',
    nameEn: 'Rent CPI YoY',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'cpi',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'housing_indicators',
    valueField: 'rent_cpi',
    unit: '%',
  },

  // =========================================================================
  // 物価 - Zillow家賃指数 / 家賃CPI（CSV/FRED独立取得）
  // =========================================================================
  {
    id: 'us_zillow_rent_index_yoy',
    name: 'Zillow家賃指数（前年比・CSV）',
    nameEn: 'Zillow Observed Rent Index YoY',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'housing',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'zillow_rent_index',
    valueField: 'yoy',
    unit: '%',
  },
  {
    id: 'us_rent_cpi_standalone_yoy',
    name: '家賃CPI（前年比・FRED）',
    nameEn: 'Rent CPI YoY (FRED)',
    frequency: 'monthly',
    country: 'usa',
    category: 'prices',
    subCategory: 'housing',
    apiEndpoint: '/api/usa/inflation',
    dataKey: 'rent_cpi',
    valueField: 'yoy',
    unit: '%',
  },

  // =========================================================================
  // 市場 - 為替（ドルストレート）
  // =========================================================================
  {
    id: 'usdjpy',
    name: 'ドル円',
    nameEn: 'USD/JPY',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_usd',
    apiEndpoint: '/api/market',
    dataKey: 'usdjpy',
    valueField: 'close',
  },
  {
    id: 'eurusd',
    name: 'ユーロドル',
    nameEn: 'EUR/USD',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_usd',
    apiEndpoint: '/api/market',
    dataKey: 'eurusd',
    valueField: 'close',
  },
  {
    id: 'gbpusd',
    name: 'ポンドドル',
    nameEn: 'GBP/USD',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_usd',
    apiEndpoint: '/api/market',
    dataKey: 'gbpusd',
    valueField: 'close',
  },
  {
    id: 'audusd',
    name: '豪ドル米ドル',
    nameEn: 'AUD/USD',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_usd',
    apiEndpoint: '/api/market',
    dataKey: 'audusd',
    valueField: 'close',
  },
  {
    id: 'nzdusd',
    name: 'NZドル米ドル',
    nameEn: 'NZD/USD',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_usd',
    apiEndpoint: '/api/market',
    dataKey: 'nzdusd',
    valueField: 'close',
  },
  {
    id: 'usdcad',
    name: 'ドルカナダ',
    nameEn: 'USD/CAD',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_usd',
    apiEndpoint: '/api/market',
    dataKey: 'usdcad',
    valueField: 'close',
  },
  {
    id: 'usdchf',
    name: 'ドルスイス',
    nameEn: 'USD/CHF',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_usd',
    apiEndpoint: '/api/market',
    dataKey: 'usdchf',
    valueField: 'close',
  },

  // =========================================================================
  // 市場 - 為替（クロス円）
  // =========================================================================
  {
    id: 'eurjpy',
    name: 'ユーロ円',
    nameEn: 'EUR/JPY',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_jpy',
    apiEndpoint: '/api/market',
    dataKey: 'eurjpy',
    valueField: 'close',
  },
  {
    id: 'gbpjpy',
    name: 'ポンド円',
    nameEn: 'GBP/JPY',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_jpy',
    apiEndpoint: '/api/market',
    dataKey: 'gbpjpy',
    valueField: 'close',
  },
  {
    id: 'audjpy',
    name: '豪ドル円',
    nameEn: 'AUD/JPY',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_jpy',
    apiEndpoint: '/api/market',
    dataKey: 'audjpy',
    valueField: 'close',
  },
  {
    id: 'nzdjpy',
    name: 'NZドル円',
    nameEn: 'NZD/JPY',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_jpy',
    apiEndpoint: '/api/market',
    dataKey: 'nzdjpy',
    valueField: 'close',
  },
  {
    id: 'cadjpy',
    name: 'カナダ円',
    nameEn: 'CAD/JPY',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_jpy',
    apiEndpoint: '/api/market',
    dataKey: 'cadjpy',
    valueField: 'close',
  },
  {
    id: 'chfjpy',
    name: 'スイス円',
    nameEn: 'CHF/JPY',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_jpy',
    apiEndpoint: '/api/market',
    dataKey: 'chfjpy',
    valueField: 'close',
  },

  // =========================================================================
  // 市場 - 為替（その他クロス）
  // =========================================================================
  {
    id: 'eurgbp',
    name: 'ユーロポンド',
    nameEn: 'EUR/GBP',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_cross',
    apiEndpoint: '/api/market',
    dataKey: 'eurgbp',
    valueField: 'close',
  },
  {
    id: 'euraud',
    name: 'ユーロ豪ドル',
    nameEn: 'EUR/AUD',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_cross',
    apiEndpoint: '/api/market',
    dataKey: 'euraud',
    valueField: 'close',
  },
  {
    id: 'eurnzd',
    name: 'ユーロNZドル',
    nameEn: 'EUR/NZD',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_cross',
    apiEndpoint: '/api/market',
    dataKey: 'eurnzd',
    valueField: 'close',
  },
  {
    id: 'eurcad',
    name: 'ユーロカナダ',
    nameEn: 'EUR/CAD',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_cross',
    apiEndpoint: '/api/market',
    dataKey: 'eurcad',
    valueField: 'close',
  },
  {
    id: 'eurchf',
    name: 'ユーロスイス',
    nameEn: 'EUR/CHF',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_cross',
    apiEndpoint: '/api/market',
    dataKey: 'eurchf',
    valueField: 'close',
  },
  {
    id: 'gbpaud',
    name: 'ポンド豪ドル',
    nameEn: 'GBP/AUD',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_cross',
    apiEndpoint: '/api/market',
    dataKey: 'gbpaud',
    valueField: 'close',
  },
  {
    id: 'gbpnzd',
    name: 'ポンドNZドル',
    nameEn: 'GBP/NZD',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_cross',
    apiEndpoint: '/api/market',
    dataKey: 'gbpnzd',
    valueField: 'close',
  },
  {
    id: 'gbpcad',
    name: 'ポンドカナダ',
    nameEn: 'GBP/CAD',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_cross',
    apiEndpoint: '/api/market',
    dataKey: 'gbpcad',
    valueField: 'close',
  },
  {
    id: 'gbpchf',
    name: 'ポンドスイス',
    nameEn: 'GBP/CHF',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_cross',
    apiEndpoint: '/api/market',
    dataKey: 'gbpchf',
    valueField: 'close',
  },
  {
    id: 'audnzd',
    name: '豪ドルNZドル',
    nameEn: 'AUD/NZD',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_cross',
    apiEndpoint: '/api/market',
    dataKey: 'audnzd',
    valueField: 'close',
  },
  {
    id: 'audcad',
    name: '豪ドルカナダ',
    nameEn: 'AUD/CAD',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_cross',
    apiEndpoint: '/api/market',
    dataKey: 'audcad',
    valueField: 'close',
  },
  {
    id: 'audchf',
    name: '豪ドルスイス',
    nameEn: 'AUD/CHF',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_cross',
    apiEndpoint: '/api/market',
    dataKey: 'audchf',
    valueField: 'close',
  },
  {
    id: 'nzdcad',
    name: 'NZドルカナダ',
    nameEn: 'NZD/CAD',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_cross',
    apiEndpoint: '/api/market',
    dataKey: 'nzdcad',
    valueField: 'close',
  },
  {
    id: 'nzdchf',
    name: 'NZドルスイス',
    nameEn: 'NZD/CHF',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_cross',
    apiEndpoint: '/api/market',
    dataKey: 'nzdchf',
    valueField: 'close',
  },
  {
    id: 'cadchf',
    name: 'カナダスイス',
    nameEn: 'CAD/CHF',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_cross',
    apiEndpoint: '/api/market',
    dataKey: 'cadchf',
    valueField: 'close',
  },

  // =========================================================================
  // 市場 - 通貨インデックス
  // =========================================================================
  {
    id: 'dxy',
    name: 'ドルインデックス',
    nameEn: 'USD Index (DXY)',
    frequency: 'daily',
    category: 'market',
    subCategory: 'forex_index',
    apiEndpoint: '/api/market',
    dataKey: 'dxy',
    valueField: 'close',
  },

  // =========================================================================
  // 市場 - 米国株価指数
  // =========================================================================
  {
    id: 'sp500',
    name: 'S&P500',
    nameEn: 'S&P 500',
    frequency: 'daily',
    category: 'market',
    subCategory: 'index_us',
    apiEndpoint: '/api/market',
    dataKey: 'sp500',
    valueField: 'close',
  },
  {
    id: 'dow',
    name: 'ダウ平均',
    nameEn: 'Dow Jones',
    frequency: 'daily',
    category: 'market',
    subCategory: 'index_us',
    apiEndpoint: '/api/market',
    dataKey: 'dow',
    valueField: 'close',
  },
  {
    id: 'nasdaq100',
    name: 'ナスダック100',
    nameEn: 'Nasdaq 100',
    frequency: 'daily',
    category: 'market',
    subCategory: 'index_us',
    apiEndpoint: '/api/market',
    dataKey: 'nasdaq100',
    valueField: 'close',
  },
  {
    id: 'nasdaq',
    name: 'ナスダック総合',
    nameEn: 'Nasdaq Composite',
    frequency: 'daily',
    category: 'market',
    subCategory: 'index_us',
    apiEndpoint: '/api/market',
    dataKey: 'nasdaq',
    valueField: 'close',
  },
  {
    id: 'russell2000',
    name: 'ラッセル2000',
    nameEn: 'Russell 2000',
    frequency: 'daily',
    category: 'market',
    subCategory: 'index_us',
    apiEndpoint: '/api/market',
    dataKey: 'russell2000',
    valueField: 'close',
  },
  {
    id: 'sox',
    name: 'フィラデルフィア半導体指数',
    nameEn: 'SOX (Semiconductor)',
    frequency: 'daily',
    category: 'market',
    subCategory: 'index_us',
    apiEndpoint: '/api/market',
    dataKey: 'sox',
    valueField: 'close',
  },
  {
    id: 'vix',
    name: 'VIX（恐怖指数）',
    nameEn: 'VIX',
    frequency: 'daily',
    category: 'market',
    subCategory: 'index_us',
    apiEndpoint: '/api/market',
    dataKey: 'vix',
    valueField: 'close',
  },

  // =========================================================================
  // 市場 - 日本・アジア株価指数
  // =========================================================================
  {
    id: 'nikkei225',
    name: '日経平均',
    nameEn: 'Nikkei 225',
    frequency: 'daily',
    category: 'market',
    subCategory: 'index_asia',
    apiEndpoint: '/api/market',
    dataKey: 'nikkei225',
    valueField: 'close',
  },
  {
    id: 'topix',
    name: 'TOPIX',
    nameEn: 'TOPIX',
    frequency: 'daily',
    category: 'market',
    subCategory: 'index_asia',
    apiEndpoint: '/api/market',
    dataKey: 'topix',
    valueField: 'close',
  },
  {
    id: 'hangseng',
    name: 'ハンセン指数',
    nameEn: 'Hang Seng',
    frequency: 'daily',
    category: 'market',
    subCategory: 'index_asia',
    apiEndpoint: '/api/market',
    dataKey: 'hangseng',
    valueField: 'close',
  },

  // =========================================================================
  // 市場 - 欧州株価指数
  // =========================================================================
  {
    id: 'dax',
    name: 'DAX',
    nameEn: 'DAX',
    frequency: 'daily',
    category: 'market',
    subCategory: 'index_europe',
    apiEndpoint: '/api/market',
    dataKey: 'dax',
    valueField: 'close',
  },
  {
    id: 'ftse100',
    name: 'FTSE100',
    nameEn: 'FTSE 100',
    frequency: 'daily',
    category: 'market',
    subCategory: 'index_europe',
    apiEndpoint: '/api/market',
    dataKey: 'ftse100',
    valueField: 'close',
  },
  {
    id: 'cac40',
    name: 'CAC40',
    nameEn: 'CAC 40',
    frequency: 'daily',
    category: 'market',
    subCategory: 'index_europe',
    apiEndpoint: '/api/market',
    dataKey: 'cac40',
    valueField: 'close',
  },

  // =========================================================================
  // 市場 - 債券利回り
  // =========================================================================
  {
    id: 'us02y',
    name: '米国2年債利回り',
    nameEn: 'US 2Y Yield',
    frequency: 'daily',
    category: 'market',
    subCategory: 'bond',
    apiEndpoint: '/api/market',
    dataKey: 'us02y',
    valueField: 'close',
    unit: '%',
  },
  {
    id: 'us10y',
    name: '米国10年債利回り',
    nameEn: 'US 10Y Yield',
    frequency: 'daily',
    category: 'market',
    subCategory: 'bond',
    apiEndpoint: '/api/market',
    dataKey: 'us10y',
    valueField: 'close',
    unit: '%',
  },
  {
    id: 'us30y',
    name: '米国30年債利回り',
    nameEn: 'US 30Y Yield',
    frequency: 'daily',
    category: 'market',
    subCategory: 'bond',
    apiEndpoint: '/api/market',
    dataKey: 'us30y',
    valueField: 'close',
    unit: '%',
  },

  // =========================================================================
  // 金融政策
  // =========================================================================
  {
    id: 'policy_rate',
    name: '政策金利（FFレート）',
    nameEn: 'Fed Funds Policy Rate',
    frequency: 'daily',
    country: 'usa',
    category: 'policy',
    subCategory: 'interest_rate',
    apiEndpoint: '/api/fed-h15/policy-rate',
    dataKey: 'policy_rate',
    valueField: 'rate',
    unit: '%',
  },
  {
    id: 'term_premium',
    name: 'タームプレミアム（ACM）',
    nameEn: 'ACM Term Premium',
    frequency: 'daily',
    country: 'usa',
    category: 'policy',
    subCategory: 'interest_rate',
    apiEndpoint: '/api/nyfed/term-premium',
    dataKey: 'term_premium',
    valueField: 'term_premium',
    unit: '%',
  },
  {
    id: 'expected_rate',
    name: '期待短期金利',
    nameEn: 'Expected Short Rate',
    frequency: 'daily',
    country: 'usa',
    category: 'policy',
    subCategory: 'interest_rate',
    apiEndpoint: '/api/nyfed/term-premium',
    dataKey: 'expected_rate',
    valueField: 'expected_rate',
    unit: '%',
  },

  // =========================================================================
  // 市場 - 貴金属
  // =========================================================================
  {
    id: 'gold',
    name: '金（ドル建て）',
    nameEn: 'Gold (USD)',
    frequency: 'daily',
    category: 'market',
    subCategory: 'commodity_metal',
    apiEndpoint: '/api/market',
    dataKey: 'gold',
    valueField: 'close',
  },
  {
    id: 'silver',
    name: '銀（ドル建て）',
    nameEn: 'Silver (USD)',
    frequency: 'daily',
    category: 'market',
    subCategory: 'commodity_metal',
    apiEndpoint: '/api/market',
    dataKey: 'silver',
    valueField: 'close',
  },
  {
    id: 'copper',
    name: '銅',
    nameEn: 'Copper',
    frequency: 'daily',
    category: 'market',
    subCategory: 'commodity_metal',
    apiEndpoint: '/api/market',
    dataKey: 'copper',
    valueField: 'close',
  },

  // =========================================================================
  // 市場 - エネルギー
  // =========================================================================
  {
    id: 'crude_oil',
    name: '原油（WTI）',
    nameEn: 'Crude Oil (WTI)',
    frequency: 'daily',
    category: 'market',
    subCategory: 'commodity_energy',
    apiEndpoint: '/api/market',
    dataKey: 'crude_oil',
    valueField: 'close',
  },
  {
    id: 'brent_oil',
    name: '原油（ブレント）',
    nameEn: 'Brent Crude',
    frequency: 'daily',
    category: 'market',
    subCategory: 'commodity_energy',
    apiEndpoint: '/api/market',
    dataKey: 'brent_oil',
    valueField: 'close',
  },
  {
    id: 'natural_gas',
    name: '天然ガス',
    nameEn: 'Natural Gas',
    frequency: 'daily',
    category: 'market',
    subCategory: 'commodity_energy',
    apiEndpoint: '/api/market',
    dataKey: 'natural_gas',
    valueField: 'close',
  },

  // =========================================================================
  // 市場 - 計算値（株価指数系）
  // =========================================================================
  {
    id: 'nikkei_usd',
    name: '日経平均（ドル建て）',
    nameEn: 'Nikkei 225 (USD)',
    frequency: 'daily',
    category: 'market',
    subCategory: 'calculated_index',
    apiEndpoint: '/api/market',
    dataKey: 'nikkei_usd',
    valueField: 'close',
  },

  // =========================================================================
  // 市場 - 計算値（商品系）
  // =========================================================================
  {
    id: 'gold_jpy',
    name: '金（円建て）',
    nameEn: 'Gold (JPY)',
    frequency: 'daily',
    category: 'market',
    subCategory: 'calculated_commodity',
    apiEndpoint: '/api/market',
    dataKey: 'gold_jpy',
    valueField: 'close',
  },
  {
    id: 'gold_eur',
    name: '金（ユーロ建て）',
    nameEn: 'Gold (EUR)',
    frequency: 'daily',
    category: 'market',
    subCategory: 'calculated_commodity',
    apiEndpoint: '/api/market',
    dataKey: 'gold_eur',
    valueField: 'close',
  },
  {
    id: 'gold_gbp',
    name: '金（ポンド建て）',
    nameEn: 'Gold (GBP)',
    frequency: 'daily',
    category: 'market',
    subCategory: 'calculated_commodity',
    apiEndpoint: '/api/market',
    dataKey: 'gold_gbp',
    valueField: 'close',
  },
  {
    id: 'gold_aud',
    name: '金（豪ドル建て）',
    nameEn: 'Gold (AUD)',
    frequency: 'daily',
    category: 'market',
    subCategory: 'calculated_commodity',
    apiEndpoint: '/api/market',
    dataKey: 'gold_aud',
    valueField: 'close',
  },
  {
    id: 'gold_cad',
    name: '金（カナダドル建て）',
    nameEn: 'Gold (CAD)',
    frequency: 'daily',
    category: 'market',
    subCategory: 'calculated_commodity',
    apiEndpoint: '/api/market',
    dataKey: 'gold_cad',
    valueField: 'close',
  },
  {
    id: 'gold_chf',
    name: '金（スイスフラン建て）',
    nameEn: 'Gold (CHF)',
    frequency: 'daily',
    category: 'market',
    subCategory: 'calculated_commodity',
    apiEndpoint: '/api/market',
    dataKey: 'gold_chf',
    valueField: 'close',
  },
  {
    id: 'gold_nzd',
    name: '金（NZドル建て）',
    nameEn: 'Gold (NZD)',
    frequency: 'daily',
    category: 'market',
    subCategory: 'calculated_commodity',
    apiEndpoint: '/api/market',
    dataKey: 'gold_nzd',
    valueField: 'close',
  },
];

// =============================================================================
// ヘルパー関数
// =============================================================================

/** カテゴリ別に指標をグループ化（サブカテゴリ付き） */

/** 国別に指標をグループ化 */
export function getIndicatorsByCountry(): Record<string, OverlayIndicator[]> {
  const grouped: Record<string, OverlayIndicator[]> = {};

  for (const indicator of OVERLAY_INDICATORS) {
    const country = getIndicatorCountry(indicator);
    if (!grouped[country]) {
      grouped[country] = [];
    }
    grouped[country].push(indicator);
  }

  return grouped;
}

export function getIndicatorsByCategory(): Record<string, OverlayIndicator[]> {
  const grouped: Record<string, OverlayIndicator[]> = {};

  for (const indicator of OVERLAY_INDICATORS) {
    const category = indicator.category;
    if (!grouped[category]) {
      grouped[category] = [];
    }
    grouped[category].push(indicator);
  }

  return grouped;
}

/** サブカテゴリ別に指標をグループ化 */
export function getIndicatorsBySubCategory(category: string, country?: IndicatorCountry): Record<string, OverlayIndicator[]> {
  const grouped: Record<string, OverlayIndicator[]> = {};
  const indicators = OVERLAY_INDICATORS.filter(i => i.category === category && (!country || getIndicatorCountry(i) === country));

  for (const indicator of indicators) {
    const subCategory = indicator.subCategory || 'other';
    if (!grouped[subCategory]) {
      grouped[subCategory] = [];
    }
    grouped[subCategory].push(indicator);
  }

  return grouped;
}

/** 市場データのみを取得 */
export function getMarketIndicators(): OverlayIndicator[] {
  return OVERLAY_INDICATORS.filter(i => i.category === 'market');
}

/** 市場データをサブカテゴリ別にグループ化 */
export function getMarketIndicatorsBySubCategory(): Record<string, OverlayIndicator[]> {
  const grouped: Record<string, OverlayIndicator[]> = {};
  const indicators = getMarketIndicators();

  for (const indicator of indicators) {
    const subCategory = indicator.subCategory || 'other';
    if (!grouped[subCategory]) {
      grouped[subCategory] = [];
    }
    grouped[subCategory].push(indicator);
  }

  return grouped;
}

/** 経済指標のみを取得（市場データを除く） */
export function getEconomicIndicators(): OverlayIndicator[] {
  return OVERLAY_INDICATORS.filter(i => i.category !== 'market');
}

/** 経済指標を国別にグループ化（市場データを除く） */
export function getEconomicIndicatorsByCountry(): Record<string, OverlayIndicator[]> {
  const grouped: Record<string, OverlayIndicator[]> = {};

  for (const indicator of getEconomicIndicators()) {
    const country = getIndicatorCountry(indicator);
    if (!grouped[country]) {
      grouped[country] = [];
    }
    grouped[country].push(indicator);
  }

  return grouped;
}

/** 指標IDから指標情報を取得 */
export function getIndicatorById(id: string): OverlayIndicator | undefined {
  return OVERLAY_INDICATORS.find(ind => ind.id === id);
}

/** 指標を検索 */
export function searchIndicators(query: string): OverlayIndicator[] {
  const lowerQuery = query.toLowerCase();
  return OVERLAY_INDICATORS.filter(
    ind =>
      ind.name.toLowerCase().includes(lowerQuery) ||
      ind.nameEn.toLowerCase().includes(lowerQuery)
  );
}

// =============================================================================
// デフォルト設定
// =============================================================================

export const DEFAULT_OVERLAY_SETTINGS: OverlaySettings = {
  axis: 'right',  // デフォルトで右軸を使用
  transform: 'raw',
  display: 'step',
};

// =============================================================================
// localStorage キー
// =============================================================================

export const OVERLAY_STORAGE_KEY_PREFIX = 'overlay_';

export function getOverlayStorageKey(mainIndicatorId: string): string {
  return `${OVERLAY_STORAGE_KEY_PREFIX}${mainIndicatorId}`;
}
