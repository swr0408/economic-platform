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
