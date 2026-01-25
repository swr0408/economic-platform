/**
 * チャートコンポーネント共通定数
 *
 * 色、スタイル、設定値を一元管理
 * EconAlpha ダークテーマ対応
 */

// =============================================================================
// EconAlpha ダークテーマ カラーパレット
// =============================================================================

/** ダークテーマ基本色 */
export const DARK_THEME = {
  bgPrimary: '#0f172a',
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  bgElevated: '#475569',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textTertiary: '#64748b',
  border: '#334155',
  borderLight: '#475569',
  accent: '#10b981',
  accentHover: '#34d399',
} as const

// =============================================================================
// カラーパレット
// =============================================================================

/** 主要カラー */
export const CHART_COLORS = {
  // プライマリカラー（アクセント）
  primary: '#3b82f6',

  // プラス/マイナス
  positive: '#10b981',
  negative: '#ef4444',

  // セカンダリカラー
  purple: '#a855f7',
  cyan: '#06b6d4',
  magenta: '#ec4899',
  orange: '#f97316',
  gold: '#f59e0b',

  // ニュートラル（ダークテーマ用に調整）
  gray: '#64748b',
  lightGray: '#475569',
  green: '#2fb584',
  red: '#ef4444',


  // 背景色（ダークテーマ）
  bgLight: '#1e293b',
  bgLighter: '#334155',
} as const

/** セル背景色（ヒートマップ用・ダークテーマで見やすく調整） */
export const CELL_COLORS = {
  strongPositive: 'rgba(16, 185, 129, 0.55)',
  weakPositive: 'rgba(16, 185, 129, 0.30)',
  weakNegative: 'rgba(239, 68, 68, 0.30)',
  strongNegative: 'rgba(239, 68, 68, 0.55)',
  neutral: 'transparent',
} as const

/** テキストカラー（ダークテーマ用） */
export const TEXT_COLORS = {
  primary: '#f1f5f9',
  secondary: '#94a3b8',
  tertiary: '#64748b',
  quaternary: '#475569',
  muted: '#475569',
  positive: '#10b981',
  negative: '#ef4444',
} as const

// =============================================================================
// レイアウト・スタイル
// =============================================================================

/** 最新値表示ボックスのスタイル（ダークテーマ） */
export const LATEST_VALUE_BOX_STYLE: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  marginBottom: 12,
  padding: '12px 16px',
  background: DARK_THEME.bgSecondary,
  borderRadius: 8,
  border: `1px solid rgba(16, 185, 129, 0.4)`, // 濃い緑の枠線
  flexWrap: 'wrap',
  gap: 12,
}

/** ツールチップのスタイル（ダークテーマ） */
export const TOOLTIP_STYLE = {
  backgroundColor: DARK_THEME.bgTertiary,
  border: `1px solid ${DARK_THEME.borderLight}`,
  borderRadius: 8,
  color: DARK_THEME.textPrimary,
} as const

/** カスタムツールチップのコンテナスタイル（ダークテーマ） */
export const CUSTOM_TOOLTIP_STYLE: React.CSSProperties = {
  backgroundColor: DARK_THEME.bgTertiary,
  border: `1px solid ${DARK_THEME.borderLight}`,
  borderRadius: 8,
  padding: '12px 16px',
  boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
  color: DARK_THEME.textPrimary,
}

/** チャートマージン */
export const CHART_MARGIN = {
  top: 20,
  right: 30,
  left: 0,
  bottom: 5,
} as const

/** 軸のスタイル（ダークテーマ用に調整） */
export const AXIS_STYLE = {
  tick: { fontSize: 11, fill: '#94a3b8' },
  interval: 'preserveStartEnd' as const,
}

/** CartesianGrid の共通プロパティ（ダークテーマ用） */
export const CARTESIAN_GRID_PROPS = {
  strokeDasharray: '3 3',
  stroke: '#475569',
} as const

// =============================================================================
// 期間設定
// =============================================================================

/** デフォルト開始年（期間別） */
export const DEFAULT_START_YEARS = {
  economy: 2020,
  consumer: 2010,
  policy: 2020,
} as const

/** 月名（日本語） */
export const MONTH_NAMES = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'] as const

/** 四半期名（日本語） */
export const QUARTER_NAMES = ['Q1', 'Q2', 'Q3', 'Q4'] as const

// =============================================================================
// 閾値設定
// =============================================================================

/** 前月比の閾値設定 */
export const MOM_THRESHOLDS = {
  default: { strong: 0.5, weak: 0 },
  vehicle: { strong: 2, weak: 0 },
} as const

/** 前年比の閾値設定 */
export const YOY_THRESHOLDS = {
  default: { strong: 2, weak: 0 },
} as const

// =============================================================================
// ヘルパー関数
// =============================================================================

/**
 * セルの背景色を取得（ヒートマップ用）
 */
export function getCellColor(
  value: number | null | undefined,
  thresholds: { strong: number; weak: number } = MOM_THRESHOLDS.default
): string {
  if (value === null || value === undefined) return CELL_COLORS.neutral
  if (value > thresholds.strong) return CELL_COLORS.strongPositive
  if (value > thresholds.weak) return CELL_COLORS.weakPositive
  if (value < -thresholds.strong) return CELL_COLORS.strongNegative
  if (value < -thresholds.weak) return CELL_COLORS.weakNegative
  // 値が正確に0の場合は薄い背景色を付ける（データ有無を視覚的に区別）
  if (value === 0) return CELL_COLORS.weakPositive
  return CELL_COLORS.neutral
}

/**
 * 値の符号に応じたテキストカラーを取得
 */
export function getValueColor(value: number | null | undefined): string {
  if (value === null || value === undefined) return TEXT_COLORS.muted
  return value >= 0 ? TEXT_COLORS.positive : TEXT_COLORS.negative
}

// =============================================================================
// ビューモードボタン用スタイル（ダークテーマ）
// =============================================================================

interface ButtonStyleConfig {
  color: string
  bgColor: string
}

const VIEW_MODE_BUTTON_CONFIGS: Record<string, ButtonStyleConfig> = {
  value: { color: '#ec4899', bgColor: 'rgba(236, 72, 153, 0.15)' },
  yoy: { color: '#10b981', bgColor: 'rgba(16, 185, 129, 0.15)' },
  mom: { color: '#3b82f6', bgColor: 'rgba(59, 130, 246, 0.15)' },
  mom_table: { color: '#3b82f6', bgColor: 'rgba(59, 130, 246, 0.15)' },
  mom_chart: { color: '#3b82f6', bgColor: 'rgba(59, 130, 246, 0.15)' },
  annualized: { color: '#f97316', bgColor: 'rgba(249, 115, 22, 0.15)' },  // 年率（オレンジ）
  total: { color: '#10b981', bgColor: 'rgba(16, 185, 129, 0.15)' },
  ex_auto: { color: '#a855f7', bgColor: 'rgba(168, 85, 247, 0.15)' },
  control_group: { color: '#06b6d4', bgColor: 'rgba(6, 182, 212, 0.15)' },
}

/**
 * ビューモードボタンのスタイルを取得（ダークテーマ）
 */
export function getViewModeButtonStyle(
  mode: string,
  isActive: boolean
): React.CSSProperties {
  const config = VIEW_MODE_BUTTON_CONFIGS[mode] || VIEW_MODE_BUTTON_CONFIGS.yoy

  return {
    padding: '6px 12px',
    border: isActive ? `2px solid ${config.color}` : `1px solid ${DARK_THEME.border}`,
    borderRadius: 4,
    background: isActive ? config.bgColor : DARK_THEME.bgSecondary,
    cursor: 'pointer',
    fontWeight: isActive ? 'bold' : 'normal',
    color: isActive ? config.color : DARK_THEME.textSecondary,
  }
}

/**
 * データタイプボタンのスタイルを取得（小さめサイズ・ダークテーマ）
 */
export function getDataTypeButtonStyle(
  type: string,
  isActive: boolean
): React.CSSProperties {
  const config = VIEW_MODE_BUTTON_CONFIGS[type] || VIEW_MODE_BUTTON_CONFIGS.total

  return {
    padding: '4px 10px',
    border: isActive ? `2px solid ${config.color}` : `1px solid ${DARK_THEME.border}`,
    borderRadius: 4,
    background: isActive ? config.bgColor : DARK_THEME.bgSecondary,
    cursor: 'pointer',
    fontWeight: isActive ? 'bold' : 'normal',
    fontSize: 12,
    color: isActive ? config.color : DARK_THEME.textSecondary,
  }
}

// =============================================================================
// 共通ビューモード・データタイプ設定
// =============================================================================

/** 標準ビューモードタイプ（前年比/前月比テーブル/前月比グラフ） */
export type StandardViewMode = 'yoy' | 'mom_table' | 'mom_chart'

/** 標準ビューモード設定（前年比/前月比/前月比テーブル） */
export const STANDARD_VIEW_MODE_OPTIONS: { mode: StandardViewMode; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom_chart', label: '前月比' },
  { mode: 'mom_table', label: '前月比（テーブル）' },
]

/** 名目/実質データタイプ */
export type NominalRealDataType = 'nominal' | 'real'

/** 名目/実質データタイプ設定 */
export const NOMINAL_REAL_DATA_TYPE_OPTIONS: { type: NominalRealDataType; label: string }[] = [
  { type: 'nominal', label: '名目' },
  { type: 'real', label: '実質' },
]

/** 小売売上データタイプ */
export type RetailDataType = 'total' | 'ex_auto' | 'control_group'

/** 小売売上データタイプ設定 */
export const RETAIL_DATA_TYPE_OPTIONS: { type: RetailDataType; label: string }[] = [
  { type: 'total', label: '総合' },
  { type: 'ex_auto', label: '自動車除く' },
  { type: 'control_group', label: 'コントロールグループ' },
]

/** 耐久財データタイプ */
export type DurableGoodsDataType = 'total' | 'ex_transport'

/** 耐久財データタイプ設定 */
export const DURABLE_GOODS_DATA_TYPE_OPTIONS: { type: DurableGoodsDataType; label: string }[] = [
  { type: 'total', label: '総合' },
  { type: 'ex_transport', label: '輸送除く' },
]

/** 住宅着工/建設許可データタイプ */
export type HousingStartsPermitsDataType = 'housing_starts' | 'building_permits'

/** 住宅着工/建設許可データタイプ設定 */
export const HOUSING_STARTS_PERMITS_DATA_TYPE_OPTIONS: { type: HousingStartsPermitsDataType; label: string }[] = [
  { type: 'housing_starts', label: '住宅着工' },
  { type: 'building_permits', label: '建設許可' },
]

// =============================================================================
// 現数値/前月増減幅ビューモード（NonfarmPayrollsChart等で使用）
// =============================================================================

/** 現数値/増減幅ビューモードタイプ */
export type ValueChangeViewMode = 'value' | 'change_chart' | 'change_table'

/** 現数値/増減幅ビューモード設定 */
export const VALUE_CHANGE_VIEW_MODE_OPTIONS: { mode: ValueChangeViewMode; label: string }[] = [
  { mode: 'value', label: '現数値' },
  { mode: 'change_chart', label: '前月増減幅' },
  { mode: 'change_table', label: '前月増減幅（テーブル）' },
]

// =============================================================================
// 増減幅テーブル用ヘルパー（共通化）
// =============================================================================

/** 増減幅閾値プリセット */
export const CHANGE_THRESHOLDS = {
  /** 雇用者数（200k千人） */
  employment_200k: 200,
  /** 雇用者数（100k千人） */
  employment_100k: 100,
  /** 前月比（0.4%） */
  mom_04: 0.4,
  /** 前月比（0.5%） */
  mom_05: 0.5,
  /** 前月比（1.0%） */
  mom_10: 1.0,
} as const

/**
 * 増減幅テーブル用のセル背景色を取得する関数を生成
 * @param threshold 閾値（正の値、例: 200, 0.4）
 */
export function createChangeCellColorFn(threshold: number): (value: number | null | undefined) => string {
  return (value: number | null | undefined): string => {
    if (value === null || value === undefined) return 'transparent'
    if (value > threshold) return 'rgba(82, 196, 26, 0.3)'
    if (value > 0) return 'rgba(82, 196, 26, 0.15)'
    if (value < -threshold) return 'rgba(255, 77, 79, 0.3)'
    if (value < 0) return 'rgba(255, 77, 79, 0.15)'
    // 値が正確に0の場合は薄い背景色を付ける（データ有無を視覚的に区別）
    if (value === 0) return 'rgba(82, 196, 26, 0.15)'
    return 'transparent'
  }
}

/**
 * 増減幅テーブル用の凡例を生成
 * @param threshold 閾値（正の値）
 * @param unit 単位（'k' | '%'）
 */
export function createChangeLegend(
  threshold: number,
  unit: 'k' | '%'
): { color: string; label: string }[] {
  const suffix = unit === 'k' ? 'k' : '%'
  const thresholdStr = unit === 'k' ? threshold.toString() : threshold.toFixed(1)
  return [
    { color: 'rgba(82, 196, 26, 0.3)', label: `+${thresholdStr}${suffix}以上` },
    { color: 'rgba(82, 196, 26, 0.15)', label: `0〜+${thresholdStr}${suffix}` },
    { color: 'rgba(255, 77, 79, 0.15)', label: `0〜-${thresholdStr}${suffix}` },
    { color: 'rgba(255, 77, 79, 0.3)', label: `-${thresholdStr}${suffix}以下` },
  ]
}

/** 事前定義済み凡例: 雇用者数200k */
export const CHANGE_LEGEND_200K = createChangeLegend(200, 'k')

/** 事前定義済み凡例: 雇用者数100k */
export const CHANGE_LEGEND_100K = createChangeLegend(100, 'k')

/** 事前定義済み凡例: 前月比0.4% */
export const CHANGE_LEGEND_04PCT = createChangeLegend(0.4, '%')

/** 事前定義済み凡例: 前月比0.5% */
export const CHANGE_LEGEND_05PCT = createChangeLegend(0.5, '%')

/** 事前定義済み凡例: 前月比1.0% */
export const CHANGE_LEGEND_10PCT = createChangeLegend(1.0, '%')

/** 事前定義済みセル背景色関数: 200k閾値 */
export const getChangeCellColor200k = createChangeCellColorFn(CHANGE_THRESHOLDS.employment_200k)

/** 事前定義済みセル背景色関数: 100k閾値 */
export const getChangeCellColor100k = createChangeCellColorFn(CHANGE_THRESHOLDS.employment_100k)

/** 事前定義済みセル背景色関数: 0.4%閾値 */
export const getChangeCellColor04pct = createChangeCellColorFn(CHANGE_THRESHOLDS.mom_04)

/** 事前定義済みセル背景色関数: 0.5%閾値 */
export const getChangeCellColor05pct = createChangeCellColorFn(CHANGE_THRESHOLDS.mom_05)

/** 事前定義済みセル背景色関数: 1.0%閾値 */
export const getChangeCellColor10pct = createChangeCellColorFn(CHANGE_THRESHOLDS.mom_10)
