/**
 * チャートコンポーネント共通定数
 *
 * 色、スタイル、設定値を一元管理
 */

// =============================================================================
// カラーパレット
// =============================================================================

/** 主要カラー */
export const CHART_COLORS = {
  // プライマリカラー
  primary: '#1890ff',

  // プラス/マイナス
  positive: '#52c41a',
  negative: '#ff4d4f',

  // セカンダリカラー
  purple: '#722ed1',
  cyan: '#13c2c2',
  magenta: '#eb2f96',
  orange: '#fa8c16',
  gold: '#faad14',

  // ニュートラル
  gray: '#8c8c8c',
  lightGray: '#d9d9d9',

  // 背景色
  bgLight: '#f5f5f5',
  bgLighter: '#fafafa',
} as const

/** セル背景色（ヒートマップ用） */
export const CELL_COLORS = {
  strongPositive: 'rgba(82, 196, 26, 0.3)',
  weakPositive: 'rgba(82, 196, 26, 0.15)',
  weakNegative: 'rgba(255, 77, 79, 0.15)',
  strongNegative: 'rgba(255, 77, 79, 0.3)',
  neutral: 'transparent',
} as const

/** テキストカラー */
export const TEXT_COLORS = {
  primary: '#333',
  secondary: '#666',
  tertiary: '#888',
  quaternary: '#999',
  muted: '#bfbfbf',
  positive: '#389e0d',
  negative: '#cf1322',
} as const

// =============================================================================
// レイアウト・スタイル
// =============================================================================

/** 最新値表示ボックスのスタイル */
export const LATEST_VALUE_BOX_STYLE: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  marginBottom: 12,
  padding: '12px 16px',
  background: CHART_COLORS.bgLight,
  borderRadius: 8,
  flexWrap: 'wrap',
  gap: 12,
}

/** ツールチップのスタイル（Recharts標準Tooltip用） */
export const TOOLTIP_STYLE = {
  backgroundColor: 'rgba(255, 255, 255, 0.95)',
  border: '1px solid #d9d9d9',
  borderRadius: 4,
} as const

/** カスタムツールチップのコンテナスタイル */
export const CUSTOM_TOOLTIP_STYLE: React.CSSProperties = {
  backgroundColor: 'rgba(255, 255, 255, 0.95)',
  border: '1px solid #ddd',
  borderRadius: 8,
  padding: '12px 16px',
  boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
}

/** チャートマージン */
export const CHART_MARGIN = {
  top: 20,
  right: 30,
  left: 0,
  bottom: 5,
} as const

/** 軸のスタイル */
export const AXIS_STYLE = {
  tick: { fontSize: 11 },
  interval: 'preserveStartEnd' as const,
}

/** CartesianGrid の共通プロパティ */
export const CARTESIAN_GRID_PROPS = {
  strokeDasharray: '3 3',
  stroke: '#f0f0f0',
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
// ビューモードボタン用スタイル
// =============================================================================

interface ButtonStyleConfig {
  color: string
  bgColor: string
}

const VIEW_MODE_BUTTON_CONFIGS: Record<string, ButtonStyleConfig> = {
  value: { color: CHART_COLORS.magenta, bgColor: '#fff0f6' },
  yoy: { color: CHART_COLORS.positive, bgColor: '#f6ffed' },
  mom: { color: CHART_COLORS.primary, bgColor: '#e6f7ff' },
  mom_table: { color: CHART_COLORS.primary, bgColor: '#e6f7ff' },
  mom_chart: { color: CHART_COLORS.primary, bgColor: '#e6f7ff' },
  total: { color: CHART_COLORS.positive, bgColor: '#f6ffed' },
  ex_auto: { color: CHART_COLORS.purple, bgColor: '#f9f0ff' },
  control_group: { color: CHART_COLORS.cyan, bgColor: '#e6fffb' },
}

/**
 * ビューモードボタンのスタイルを取得
 */
export function getViewModeButtonStyle(
  mode: string,
  isActive: boolean
): React.CSSProperties {
  const config = VIEW_MODE_BUTTON_CONFIGS[mode] || VIEW_MODE_BUTTON_CONFIGS.yoy

  return {
    padding: '6px 12px',
    border: isActive ? `2px solid ${config.color}` : '1px solid #d9d9d9',
    borderRadius: 4,
    background: isActive ? config.bgColor : '#fff',
    cursor: 'pointer',
    fontWeight: isActive ? 'bold' : 'normal',
  }
}

/**
 * データタイプボタンのスタイルを取得（小さめサイズ）
 */
export function getDataTypeButtonStyle(
  type: string,
  isActive: boolean
): React.CSSProperties {
  const config = VIEW_MODE_BUTTON_CONFIGS[type] || VIEW_MODE_BUTTON_CONFIGS.total

  return {
    padding: '4px 10px',
    border: isActive ? `2px solid ${config.color}` : '1px solid #d9d9d9',
    borderRadius: 4,
    background: isActive ? config.bgColor : '#fff',
    cursor: 'pointer',
    fontWeight: isActive ? 'bold' : 'normal',
    fontSize: 12,
  }
}
