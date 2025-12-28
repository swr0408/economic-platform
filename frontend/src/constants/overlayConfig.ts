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

/** 比較指標の色パレット（順番に割り当て） */
export const OVERLAY_COLORS = [
  '#ff9800', // オレンジ
  '#9c27b0', // 紫
  '#4caf50', // 緑
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

// =============================================================================
// カテゴリ定義（階層構造）
// =============================================================================

export const INDICATOR_CATEGORIES = {
  economy: '経済',
  employment: '雇用',
  consumer: '消費',
  policy: '金融政策',
} as const;

export const INDICATOR_SUB_CATEGORIES = {
  // 経済
  gdp: 'GDP',
  sentiment: '景況感',
  production: '生産',
  // 雇用
  jobs: '雇用統計',
  claims: '失業保険',
  wages: '賃金',
  // 消費
  retail: '小売',
  spending: '支出',
  confidence: '消費者信頼感',
  // 金融政策
  rates: '金利',
  fed: 'FRB',
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
    valueField: 'current',
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

  // =========================================================================
  // 経済 - 生産
  // =========================================================================
  {
    id: 'industrial_production',
    name: '鉱工業生産',
    nameEn: 'Industrial Production',
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
    id: 'durable_goods',
    name: '耐久財受注',
    nameEn: 'Durable Goods Orders',
    frequency: 'monthly',
    category: 'economy',
    subCategory: 'production',
    apiEndpoint: '/api/usa/economy',
    dataKey: 'durable_goods',
    valueField: 'mom',
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
    unit: '%',
  },

  // =========================================================================
  // 消費 - 小売
  // =========================================================================
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
    id: 'personal_income',
    name: '個人所得（前月比）',
    nameEn: 'Personal Income MoM',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'spending',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'personal_income',
    valueField: 'mom',
    chartType: 'bar',
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
    id: 'consumer_credit',
    name: '消費者信用残高（前月比）',
    nameEn: 'Consumer Credit MoM',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'spending',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'consumer_credit',
    valueField: 'mom',
    chartType: 'bar',
    unit: '%',
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
    id: 'michigan_consumer_sentiment',
    name: 'ミシガン大学消費者信頼感指数',
    nameEn: 'Michigan Consumer Sentiment',
    frequency: 'monthly',
    category: 'consumer',
    subCategory: 'confidence',
    apiEndpoint: '/api/usa/consumer',
    dataKey: 'michigan_consumer_sentiment',
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
