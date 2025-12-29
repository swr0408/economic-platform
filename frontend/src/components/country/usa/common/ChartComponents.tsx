/**
 * チャート共通コンポーネント
 *
 * ビューモードボタン、最新値表示ボックス、凡例コンポーネントなど
 */
import React from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  Bar,
  BarChart,
} from 'recharts'
import {
  LATEST_VALUE_BOX_STYLE,
  getViewModeButtonStyle,
  getDataTypeButtonStyle,
  CHART_COLORS,
  TOOLTIP_STYLE,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  TEXT_COLORS,
  DARK_THEME,
} from './chartConstants'
import { formatDateLabel, formatDateLabelJP, formatPercent } from './useChartData'

// =============================================================================
// ViewModeButton - ビューモード切り替えボタン
// =============================================================================

interface ViewModeButtonProps<T extends string> {
  mode: T
  currentMode: T
  label: string
  onClick: (mode: T) => void
}

export function ViewModeButton<T extends string>({
  mode,
  currentMode,
  label,
  onClick,
}: ViewModeButtonProps<T>) {
  const isActive = mode === currentMode
  return (
    <button
      onClick={() => onClick(mode)}
      style={getViewModeButtonStyle(mode, isActive)}
    >
      {label}
    </button>
  )
}

// =============================================================================
// ViewModeButtonGroup - ビューモードボタングループ
// =============================================================================

interface ViewModeOption<T extends string> {
  mode: T
  label: string
}

interface ViewModeButtonGroupProps<T extends string> {
  options: ViewModeOption<T>[]
  currentMode: T
  onChange: (mode: T) => void
}

export function ViewModeButtonGroup<T extends string>({
  options,
  currentMode,
  onChange,
}: ViewModeButtonGroupProps<T>) {
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
      {options.map((option) => (
        <ViewModeButton
          key={option.mode}
          mode={option.mode}
          currentMode={currentMode}
          label={option.label}
          onClick={onChange}
        />
      ))}
    </div>
  )
}

// =============================================================================
// DataTypeButton - データタイプ切り替えボタン（小さめ）
// =============================================================================

interface DataTypeButtonProps<T extends string> {
  type: T
  currentType: T
  label: string
  onClick: (type: T) => void
}

export function DataTypeButton<T extends string>({
  type,
  currentType,
  label,
  onClick,
}: DataTypeButtonProps<T>) {
  const isActive = type === currentType
  return (
    <button
      onClick={() => onClick(type)}
      style={getDataTypeButtonStyle(type, isActive)}
    >
      {label}
    </button>
  )
}

// =============================================================================
// DataTypeButtonGroup - データタイプボタングループ
// =============================================================================

interface DataTypeOption<T extends string> {
  type: T
  label: string
}

interface DataTypeButtonGroupProps<T extends string> {
  options: DataTypeOption<T>[]
  currentType: T
  onChange: (type: T) => void
}

export function DataTypeButtonGroup<T extends string>({
  options,
  currentType,
  onChange,
}: DataTypeButtonGroupProps<T>) {
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
      {options.map((option) => (
        <DataTypeButton
          key={option.type}
          type={option.type}
          currentType={currentType}
          label={option.label}
          onClick={onChange}
        />
      ))}
    </div>
  )
}

// =============================================================================
// LatestValueBox - 最新値表示ボックス
// =============================================================================

interface LatestValueItem {
  label: string
  value: string | number | null | undefined
  color?: string
  format?: 'percent' | 'currency' | 'number' | 'raw'
  unit?: string
  decimals?: number
}

interface LatestValueBoxProps {
  items: LatestValueItem[]
  date?: string
  nextRelease?: { date: string; label?: string } | null
  children?: React.ReactNode
  /** 日付のフォーマット関数（デフォルト: formatDateLabel） */
  dateFormatter?: (date: string) => string
}

function formatItemValue(item: LatestValueItem): string {
  const { value, format = 'raw', unit = '', decimals = 2 } = item

  if (value === null || value === undefined) return 'N/A'

  if (typeof value === 'string') return value

  switch (format) {
    case 'percent':
      return formatPercent(value, decimals)
    case 'currency':
      return `$${value.toFixed(decimals)}${unit}`
    case 'number':
      return `${value.toFixed(decimals)}${unit}`
    default:
      return String(value)
  }
}

export function LatestValueBox({
  items,
  date,
  nextRelease,
  children,
  dateFormatter = formatDateLabel,
}: LatestValueBoxProps) {
  return (
    <div style={LATEST_VALUE_BOX_STYLE}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12, color: TEXT_COLORS.secondary, fontWeight: 'bold' }}>最新値</span>

        {items.map((item, index) => (
          <div key={index} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>{item.label}:</span>
            <span
              style={{
                fontSize: 16,
                fontWeight: 'bold',
                color: item.color || CHART_COLORS.primary,
              }}
            >
              {formatItemValue(item)}
            </span>
          </div>
        ))}

        {date && (
          <span style={{ fontSize: 11, color: TEXT_COLORS.tertiary }}>
            ({dateFormatter(date)})
          </span>
        )}

        {children}
      </div>

      {nextRelease && (
        <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, textAlign: 'right' }}>
          <div>次回発表: {nextRelease.label || nextRelease.date}</div>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// SimpleLatestValueBox - シンプルな最新値表示ボックス
// =============================================================================

interface SimpleLatestValueBoxProps {
  label?: string
  value: string | number | null | undefined
  subValue?: string | number | null | undefined
  subLabel?: string
  valueColor?: string
  subValueColor?: string
  date?: string
  nextRelease?: { date: string; label?: string } | null
  format?: 'percent' | 'currency' | 'number' | 'raw'
  unit?: string
  decimals?: number
  /** 日付のフォーマット関数（デフォルト: formatDateLabel） */
  dateFormatter?: (date: string) => string
}

export function SimpleLatestValueBox({
  label = '最新値',
  value,
  subValue,
  subLabel,
  valueColor = CHART_COLORS.primary,
  subValueColor,
  date,
  nextRelease,
  format = 'raw',
  unit = '',
  decimals = 2,
  dateFormatter = formatDateLabel,
}: SimpleLatestValueBoxProps) {
  const formattedValue = formatItemValue({
    label: '',
    value,
    format,
    unit,
    decimals,
  })

  const formattedSubValue = subValue !== undefined
    ? formatItemValue({
        label: '',
        value: subValue,
        format,
        unit,
        decimals,
      })
    : null

  return (
    <div style={LATEST_VALUE_BOX_STYLE}>
      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
        <div>
          <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>{label}: </span>
          <span style={{ fontSize: 20, fontWeight: 'bold', color: valueColor }}>
            {formattedValue}
          </span>
        </div>

        {formattedSubValue && (
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>{subLabel}: </span>
            <span
              style={{
                fontSize: 20,
                fontWeight: 'bold',
                color: subValueColor || valueColor,
              }}
            >
              {formattedSubValue}
            </span>
          </div>
        )}

        {date && (
          <span style={{ fontSize: 12, color: TEXT_COLORS.tertiary, alignSelf: 'center' }}>
            ({dateFormatter(date)})
          </span>
        )}
      </div>

      {nextRelease && (
        <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, textAlign: 'right' }}>
          <div>次回発表: {nextRelease.date}</div>
          {nextRelease.label && (
            <div style={{ fontSize: 11, color: DARK_THEME.accent }}>{nextRelease.label}</div>
          )}
        </div>
      )}
    </div>
  )
}

// =============================================================================
// NoDataMessage - データなし表示
// =============================================================================

interface NoDataMessageProps {
  message?: string
}

export function NoDataMessage({ message = 'データが利用できません' }: NoDataMessageProps) {
  return (
    <div style={{ textAlign: 'center', padding: '40px 0', color: TEXT_COLORS.tertiary }}>
      {message}
    </div>
  )
}

// =============================================================================
// TableLegend - テーブル凡例
// =============================================================================

interface LegendItem {
  color: string
  label: string
}

interface TableLegendProps {
  items: LegendItem[]
}

export function TableLegend({ items }: TableLegendProps) {
  return (
    <div
      style={{
        marginTop: 8,
        fontSize: 11,
        color: TEXT_COLORS.tertiary,
        display: 'flex',
        gap: 16,
        flexWrap: 'wrap',
      }}
    >
      {items.map((item, index) => (
        <span key={index}>
          <span
            style={{
              display: 'inline-block',
              width: 12,
              height: 12,
              backgroundColor: item.color,
              marginRight: 4,
            }}
          />
          {item.label}
        </span>
      ))}
    </div>
  )
}

// =============================================================================
// 標準的な凡例プリセット
// =============================================================================

export const MOM_LEGEND_DEFAULT: LegendItem[] = [
  { color: 'rgba(82, 196, 26, 0.3)', label: 'プラス（+0.5%以上）' },
  { color: 'rgba(82, 196, 26, 0.15)', label: 'プラス（0〜+0.5%）' },
  { color: 'rgba(255, 77, 79, 0.15)', label: 'マイナス（0〜-0.5%）' },
  { color: 'rgba(255, 77, 79, 0.3)', label: 'マイナス（-0.5%以下）' },
]

export const MOM_LEGEND_VEHICLE: LegendItem[] = [
  { color: 'rgba(82, 196, 26, 0.3)', label: 'プラス（+2%以上）' },
  { color: 'rgba(82, 196, 26, 0.15)', label: 'プラス（0〜+2%）' },
  { color: 'rgba(255, 77, 79, 0.15)', label: 'マイナス（0〜-2%）' },
  { color: 'rgba(255, 77, 79, 0.3)', label: 'マイナス（-2%以下）' },
]

// =============================================================================
// NextReleaseDisplay - 次回発表表示
// =============================================================================

interface NextReleaseDisplayProps {
  nextRelease?: { date: string } | null
  style?: React.CSSProperties
}

const NEXT_RELEASE_STYLE: React.CSSProperties = {
  fontSize: 11,
  color: TEXT_COLORS.tertiary,
  textAlign: 'right',
}

export function NextReleaseDisplay({ nextRelease, style }: NextReleaseDisplayProps) {
  if (!nextRelease) return null

  return (
    <div style={{ ...NEXT_RELEASE_STYLE, ...style }}>
      次回発表: {nextRelease.date}
    </div>
  )
}

// =============================================================================
// ReferenceLine プリセット - チャート用基準線
// =============================================================================

/**
 * ゼロライン用の共通プロパティ
 * 使用例: <ReferenceLine {...ZERO_LINE_PROPS} />
 */
export const ZERO_LINE_PROPS = {
  y: 0,
  stroke: TEXT_COLORS.secondary,
  strokeWidth: 1,
} as const

/**
 * 50ライン用の共通プロパティ（ISM指数など）
 * 使用例: <ReferenceLine {...FIFTY_LINE_PROPS} />
 */
export const FIFTY_LINE_PROPS = {
  y: 50,
  stroke: TEXT_COLORS.secondary,
  strokeWidth: 1,
  label: {
    value: '50',
    position: 'right' as const,
    fontSize: 10,
    fill: TEXT_COLORS.secondary,
  },
} as const

// =============================================================================
// LatestValueBoxDual - 2値表示用の最新値ボックス（名目/実質など）
// =============================================================================

interface DualLatestItem {
  date: string
  yoy?: number | null
  mom?: number | null
}

interface LatestValueBoxDualProps {
  /** 1つ目の値（名目など） */
  primary: {
    label: string
    data: DualLatestItem | null | undefined
    color: string
  }
  /** 2つ目の値（実質など） */
  secondary: {
    label: string
    data: DualLatestItem | null | undefined
    color: string
  }
  /** 表示モード（yoy=前年比, mom=前月比） */
  viewMode: 'yoy' | 'mom' | 'mom_chart' | 'mom_table' | 'value'
  /** 次回発表日 */
  nextRelease?: { date: string } | null
}

/**
 * 名目/実質など2つの値を表示する最新値ボックス
 * PCE, PersonalIncome, DisposableIncome など共通で使用
 *
 * @example
 * <LatestValueBoxDual
 *   primary={{ label: '名目', data: nominalLatest, color: COLORS.nominal }}
 *   secondary={{ label: '実質', data: realLatest, color: COLORS.real }}
 *   viewMode={viewMode}
 *   nextRelease={nextRelease}
 * />
 */
export function LatestValueBoxDual({
  primary,
  secondary,
  viewMode,
  nextRelease,
}: LatestValueBoxDualProps) {
  // yoy/mom/mom_chart/mom_tableに応じて適切な値を選択
  const getDisplayValue = (data: DualLatestItem | null | undefined) => {
    if (!data) return null
    if (viewMode === 'yoy' || viewMode === 'value') {
      return data.yoy
    }
    return data.mom
  }

  return (
    <div style={LATEST_VALUE_BOX_STYLE}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12, color: TEXT_COLORS.secondary, fontWeight: 'bold' }}>最新値</span>

        {/* Primary value */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>{primary.label}:</span>
          {primary.data && (
            <>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: primary.color }}>
                {formatPercent(getDisplayValue(primary.data))}
              </span>
              <span style={{ fontSize: 11, color: TEXT_COLORS.tertiary }}>
                ({formatDateLabel(primary.data.date)})
              </span>
            </>
          )}
        </div>

        {/* Secondary value */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>{secondary.label}:</span>
          {secondary.data && (
            <>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: secondary.color }}>
                {formatPercent(getDisplayValue(secondary.data))}
              </span>
              <span style={{ fontSize: 11, color: TEXT_COLORS.tertiary }}>
                ({formatDateLabel(secondary.data.date)})
              </span>
            </>
          )}
        </div>
      </div>

      {nextRelease && (
        <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, textAlign: 'right' }}>
          次回発表: {nextRelease.date}
        </div>
      )}
    </div>
  )
}

// =============================================================================
// LatestValueBoxWithSub - メイン値+サブ値表示用ボックス（総合/輸送除外など）
// =============================================================================

interface LatestValueBoxWithSubProps {
  /** メイン値 */
  main: {
    label: string
    yoyValue: number | null | undefined
    momValue: number | null | undefined
    color: string
  }
  /** サブ値 */
  sub: {
    label: string
    yoyValue: number | null | undefined
    momValue: number | null | undefined
    color: string
  }
  /** 日付 */
  date?: string
  /** 表示モード */
  viewMode: 'yoy' | 'mom' | 'mom_chart' | 'mom_table' | 'value'
  /** 次回発表日 */
  nextRelease?: { date: string } | null
}

/**
 * メイン値とサブ値を横並びで表示する最新値ボックス
 * DurableGoods（総合/輸送除外）など共通で使用
 */
export function LatestValueBoxWithSub({
  main,
  sub,
  date,
  viewMode,
  nextRelease,
}: LatestValueBoxWithSubProps) {
  const getDisplayValue = (yoy: number | null | undefined, mom: number | null | undefined) => {
    if (viewMode === 'yoy' || viewMode === 'value') {
      return yoy
    }
    return mom
  }

  return (
    <div style={LATEST_VALUE_BOX_STYLE}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12, color: TEXT_COLORS.secondary, fontWeight: 'bold' }}>最新値</span>

        {/* Main value */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>{main.label}:</span>
          <span style={{ fontSize: 16, fontWeight: 'bold', color: main.color }}>
            {formatPercent(getDisplayValue(main.yoyValue, main.momValue))}
          </span>
          {date && (
            <span style={{ fontSize: 11, color: TEXT_COLORS.tertiary }}>
              ({formatDateLabel(date)})
            </span>
          )}
        </div>

        {/* Sub value */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>{sub.label}:</span>
          <span style={{ fontSize: 16, fontWeight: 'bold', color: sub.color }}>
            {formatPercent(getDisplayValue(sub.yoyValue, sub.momValue))}
          </span>
        </div>
      </div>

      {nextRelease && (
        <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, textAlign: 'right' }}>
          次回発表: {nextRelease.date}
        </div>
      )}
    </div>
  )
}

// =============================================================================
// StandardLineChart - 標準的な折れ線グラフ
// =============================================================================

/** 折れ線の定義 */
interface LineConfig {
  /** データキー */
  dataKey: string
  /** 線の色 */
  color: string
  /** 表示名 */
  name: string
  /** 非表示フラグ */
  hide?: boolean
  /** 線幅（デフォルト: 2） */
  strokeWidth?: number
  /** 破線パターン（例: "5 5"） */
  strokeDasharray?: string
}

interface StandardLineChartProps<T> {
  /** チャートデータ */
  data: T[]
  /** 折れ線の設定 */
  lines: LineConfig[]
  /** 高さ（デフォルト: 450） */
  height?: number
  /** X軸のフォーマッター（デフォルト: formatDateLabel） */
  xAxisFormatter?: (value: string) => string
  /** Y軸のフォーマッター */
  yAxisFormatter?: (value: number) => string
  /** ツールチップのラベルフォーマッター */
  tooltipLabelFormatter?: (label: string) => string
  /** ツールチップの値フォーマッター（文字列を返す関数） */
  tooltipValueFormatter?: (value: number, dataKey: string) => string
  /** @deprecated 使用しないでください。tooltipValueFormatterを使用してください */
  tooltipFormatter?: (value: unknown, name: string) => [string, string]
  /** Y軸のドメイン */
  yDomain?: [string | number, string | number]
  /** ゼロラインを表示するか（デフォルト: true） */
  showZeroLine?: boolean
  /** 50ラインを表示するか（デフォルト: false） - ISM等で使用 */
  showFiftyLine?: boolean
  /** 凡例のクリックハンドラ */
  onLegendClick?: (dataKey: string) => void
  /** 凡例を表示するか（デフォルト: true） */
  showLegend?: boolean
}

/**
 * 標準的な折れ線グラフコンポーネント
 *
 * @example
 * <StandardLineChart
 *   data={filteredData}
 *   lines={[
 *     { dataKey: 'yoy', color: '#1890ff', name: '前年比', hide: hiddenSeries.has('yoy') },
 *     { dataKey: 'ex_yoy', color: '#722ed1', name: '除外前年比', hide: hiddenSeries.has('ex_yoy') },
 *   ]}
 *   yAxisFormatter={(v) => `${v}%`}
 *   tooltipFormatter={createPercentFormatter()}
 *   onLegendClick={handleLegendClick}
 * />
 */
export function StandardLineChart<T extends { date: string }>({
  data,
  lines,
  height = 450,
  xAxisFormatter = formatDateLabel,
  yAxisFormatter,
  tooltipLabelFormatter = formatDateLabel,
  tooltipValueFormatter = (v) => `${v.toFixed(2)}%`,
  yDomain = ['auto', 'auto'],
  showZeroLine = true,
  showFiftyLine = false,
  onLegendClick,
  showLegend = true,
}: StandardLineChartProps<T>) {
  // カスタムTooltipコンポーネント（数値にチャートの色を使用）
  const LineChartTooltip = ({ active, payload, label }: {
    active?: boolean
    payload?: TooltipPayloadItem[]
    label?: string
  }) => {
    if (!active || !payload || payload.length === 0) return null

    return (
      <div style={TOOLTIP_STYLE}>
        <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
          {tooltipLabelFormatter(label || '')}
        </div>
        {payload.map((item, index) => (
          <div
            key={index}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 4,
              fontSize: 13,
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span
                style={{
                  display: 'inline-block',
                  width: 10,
                  height: 10,
                  borderRadius: 2,
                  backgroundColor: item.color,
                  marginRight: 6,
                }}
              />
              {item.name}
            </span>
            <span style={{ fontWeight: 500, color: item.color }}>
              {tooltipValueFormatter(item.value, item.dataKey)}
            </span>
          </div>
        ))}
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={CHART_MARGIN}>
        <CartesianGrid {...CARTESIAN_GRID_PROPS} />
        <XAxis
          dataKey="date"
          tickFormatter={xAxisFormatter}
          tick={AXIS_STYLE.tick}
          interval={AXIS_STYLE.interval}
        />
        <YAxis
          domain={yDomain}
          tick={AXIS_STYLE.tick}
          tickFormatter={yAxisFormatter}
        />
        <Tooltip content={<LineChartTooltip />} />
        {showLegend && (
          <Legend
            onClick={onLegendClick ? (e) => onLegendClick(e.dataKey as string) : undefined}
            wrapperStyle={onLegendClick ? { cursor: 'pointer' } : undefined}
          />
        )}
        {showZeroLine && <ReferenceLine {...ZERO_LINE_PROPS} />}
        {showFiftyLine && (
          <ReferenceLine
            y={50}
            stroke={TEXT_COLORS.secondary}
            strokeWidth={1}
            label={{
              value: '50',
              position: 'right',
              fontSize: 10,
              fill: TEXT_COLORS.secondary,
            }}
          />
        )}
        {lines.map((line) => (
          <Line
            key={line.dataKey}
            type="monotone"
            dataKey={line.dataKey}
            stroke={line.color}
            strokeWidth={line.strokeWidth ?? 2}
            strokeDasharray={line.strokeDasharray}
            dot={false}
            name={line.name}
            hide={line.hide}
            isAnimationActive={false}
            connectNulls={true}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}

// =============================================================================
// StandardBarChart - 標準的な棒グラフ
// =============================================================================

/** 棒の定義 */
interface BarConfig {
  /** データキー */
  dataKey: string
  /** 塗りつぶし色 */
  color: string
  /** 表示名 */
  name: string
  /** 非表示フラグ */
  hide?: boolean
}

interface StandardBarChartProps<T> {
  /** チャートデータ */
  data: T[]
  /** 棒の設定 */
  bars: BarConfig[]
  /** 高さ（デフォルト: 450） */
  height?: number
  /** X軸のフォーマッター（デフォルト: formatDateLabel） */
  xAxisFormatter?: (value: string) => string
  /** Y軸のフォーマッター */
  yAxisFormatter?: (value: number) => string
  /** ツールチップのラベルフォーマッター */
  tooltipLabelFormatter?: (label: string) => string
  /** ツールチップの値フォーマッター（文字列を返す関数） */
  tooltipValueFormatter?: (value: number, dataKey: string) => string
  /** @deprecated 使用しないでください。tooltipValueFormatterを使用してください */
  tooltipFormatter?: (value: unknown, name: string) => [string, string]
  /** Y軸のドメイン */
  yDomain?: [string | number, string | number]
  /** ゼロラインを表示するか（デフォルト: true） */
  showZeroLine?: boolean
  /** 凡例を表示するか（デフォルト: true） */
  showLegend?: boolean
}

/**
 * 標準的な棒グラフコンポーネント
 *
 * @example
 * <StandardBarChart
 *   data={filteredData}
 *   bars={[
 *     { dataKey: 'mom', color: '#52c41a', name: '前月比' },
 *   ]}
 *   yAxisFormatter={(v) => `${v}%`}
 *   tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
 * />
 */
export function StandardBarChart<T extends { date: string }>({
  data,
  bars,
  height = 450,
  xAxisFormatter = formatDateLabel,
  yAxisFormatter,
  tooltipLabelFormatter = formatDateLabel,
  tooltipValueFormatter = (v) => `${v.toFixed(2)}%`,
  yDomain = ['auto', 'auto'],
  showZeroLine = true,
  showLegend = true,
}: StandardBarChartProps<T>) {
  // カスタムTooltipコンポーネント（数値にチャートの色を使用）
  const BarChartTooltip = ({ active, payload, label }: {
    active?: boolean
    payload?: TooltipPayloadItem[]
    label?: string
  }) => {
    if (!active || !payload || payload.length === 0) return null

    return (
      <div style={TOOLTIP_STYLE}>
        <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
          {tooltipLabelFormatter(label || '')}
        </div>
        {payload.map((item, index) => (
          <div
            key={index}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 4,
              fontSize: 13,
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span
                style={{
                  display: 'inline-block',
                  width: 10,
                  height: 10,
                  borderRadius: 2,
                  backgroundColor: item.color,
                  marginRight: 6,
                }}
              />
              {item.name}
            </span>
            <span style={{ fontWeight: 500, color: item.color }}>
              {tooltipValueFormatter(item.value, item.dataKey)}
            </span>
          </div>
        ))}
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={CHART_MARGIN}>
        <CartesianGrid {...CARTESIAN_GRID_PROPS} />
        <XAxis
          dataKey="date"
          tickFormatter={xAxisFormatter}
          tick={AXIS_STYLE.tick}
          interval={AXIS_STYLE.interval}
        />
        <YAxis
          domain={yDomain}
          tick={AXIS_STYLE.tick}
          tickFormatter={yAxisFormatter}
        />
        <Tooltip content={<BarChartTooltip />} />
        {showLegend && <Legend />}
        {showZeroLine && <ReferenceLine {...ZERO_LINE_PROPS} />}
        {bars.map((bar) => (
          <Bar
            key={bar.dataKey}
            dataKey={bar.dataKey}
            fill={bar.color}
            name={bar.name}
            hide={bar.hide}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}

// =============================================================================
// 共通ツールチップ型定義
// =============================================================================

/** カスタムツールチップのpayloadアイテム型 */
export interface TooltipPayloadItem {
  name: string
  value: number
  color: string
  dataKey: string
}

/** 共通ツールチッププロパティ型（各チャートで使用） */
export interface CommonTooltipProps {
  active?: boolean
  payload?: TooltipPayloadItem[]
  label?: string
}

// =============================================================================
// ChangeTooltip - 増減幅表示用ツールチップ（共通化）
// =============================================================================

interface ChangeTooltipProps extends CommonTooltipProps {
  /** 単位（デフォルト: '%'） */
  unit?: string
  /** 小数点以下の桁数（デフォルト: 2） */
  decimals?: number
  /** 値のフォーマット関数（カスタムフォーマットが必要な場合） */
  formatValue?: (value: number) => string
  /** ラベルのフォーマット関数（四半期表示などに使用、デフォルト: formatDateLabelJP） */
  labelFormatter?: (label: string) => string
}

/**
 * 増減幅表示用の共通ツールチップ
 *
 * 符号付きの値を表示（正=緑、負=赤）
 * 前月比、前年比、増減幅の表示に使用
 *
 * @example
 * // パーセント表示（デフォルト）
 * <Tooltip content={<ChangeTooltip />} />
 *
 * // 千人単位表示
 * <Tooltip content={<ChangeTooltip unit="k" decimals={0} formatValue={(v) => v.toLocaleString()} />} />
 */
export function ChangeTooltip({
  active,
  payload,
  label,
  unit = '%',
  decimals = 2,
  formatValue,
  labelFormatter = formatDateLabelJP,
}: ChangeTooltipProps) {
  if (!active || !payload || payload.length === 0) return null

  const format = formatValue || ((v: number) => v.toFixed(decimals))

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, padding: '8px 12px' }}>
        {labelFormatter(label || '')}
      </div>
      {payload.map((item, index) => {
        const value = item.value
        const sign = value >= 0 ? '+' : ''
        return (
          <div
            key={index}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 4,
              fontSize: 13,
              padding: '4px 12px',
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span
                style={{
                  display: 'inline-block',
                  width: 10,
                  height: 10,
                  borderRadius: 2,
                  backgroundColor: item.color,
                  marginRight: 6,
                }}
              />
              {item.name}
            </span>
            <span style={{ fontWeight: 500, color: value >= 0 ? '#52c41a' : '#ff4d4f' }}>
              {sign}{format(value)}{unit}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// =============================================================================
// ValueTooltip - 現数値表示用ツールチップ（共通化）
// =============================================================================

interface ValueTooltipProps extends CommonTooltipProps {
  /** 単位（デフォルト: ''） */
  unit?: string
  /** 小数点以下の桁数（デフォルト: 0） */
  decimals?: number
  /** 値のフォーマット関数（カスタムフォーマットが必要な場合） */
  formatValue?: (value: number) => string
  /** ラベルのフォーマット関数（デフォルト: formatDateLabelJP） */
  labelFormatter?: (label: string) => string
}

/**
 * 現数値表示用の共通ツールチップ
 *
 * 系列の色で値を表示（符号なし）
 * 雇用者数、指数などの現数値表示に使用
 *
 * @example
 * // 千人単位表示
 * <Tooltip content={<ValueTooltip unit="k" />} />
 *
 * // カスタムフォーマット
 * <Tooltip content={<ValueTooltip formatValue={(v) => v.toLocaleString()} unit="k" />} />
 */
export function ValueTooltip({
  active,
  payload,
  label,
  unit = '',
  decimals = 0,
  formatValue,
  labelFormatter = formatDateLabelJP,
}: ValueTooltipProps) {
  if (!active || !payload || payload.length === 0) return null

  const format = formatValue || ((v: number) => decimals > 0 ? v.toFixed(decimals) : v.toLocaleString())

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, padding: '8px 12px' }}>
        {labelFormatter(label || '')}
      </div>
      {payload.map((item, index) => (
        <div
          key={index}
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 4,
            fontSize: 13,
            padding: '4px 12px',
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
            <span
              style={{
                display: 'inline-block',
                width: 10,
                height: 10,
                borderRadius: 2,
                backgroundColor: item.color,
                marginRight: 6,
              }}
            />
            {item.name}
          </span>
          <span style={{ fontWeight: 500, color: item.color }}>
            {format(item.value)}{unit}
          </span>
        </div>
      ))}
    </div>
  )
}

// =============================================================================
// CustomTooltip - カスタムツールチップ（複数系列対応）
// =============================================================================

/** カスタムツールチップのプロパティ */
interface CustomTooltipProps {
  active?: boolean
  payload?: TooltipPayloadItem[]
  label?: string
  /** ラベルフォーマッター */
  labelFormatter?: (label: string) => string
  /** 値フォーマッター */
  valueFormatter?: (value: number, dataKey: string) => string
  /** 値の色を動的に決定（デフォルト: 正負で緑/赤） */
  getValueColor?: (value: number, dataKey: string) => string
  /** データキーに対する表示名のマップ */
  nameMap?: Record<string, string>
}

/**
 * カスタムツールチップコンポーネント
 *
 * GDP寄与度やFCI等の複数系列チャートで使用
 *
 * @example
 * <Tooltip content={<CustomTooltip valueFormatter={formatPercentage} />} />
 */
export function CustomTooltip({
  active,
  payload,
  label,
  labelFormatter = (l) => l,
  valueFormatter = (v) => v.toFixed(2),
  getValueColor,
  nameMap,
}: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div
      style={{
        backgroundColor: DARK_THEME.bgTertiary,
        border: `1px solid ${DARK_THEME.borderLight}`,
        borderRadius: 8,
        padding: '12px 16px',
        boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
        color: DARK_THEME.textPrimary,
      }}
    >
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
        {labelFormatter(label || '')}
      </div>
      {payload.map((item, index) => {
        const displayName = nameMap?.[item.dataKey] ?? item.name
        return (
          <div
            key={index}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 4,
              fontSize: 13,
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span
                style={{
                  display: 'inline-block',
                  width: 10,
                  height: 10,
                  borderRadius: 2,
                  backgroundColor: item.color,
                  marginRight: 6,
                }}
              />
              {displayName}
            </span>
            <span style={{ fontWeight: 500, color: getValueColor ? getValueColor(item.value, item.dataKey) : item.color }}>
              {valueFormatter(item.value, item.dataKey)}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// =============================================================================
// PercentageTooltip - パーセント用カスタムツールチップ
// =============================================================================

/**
 * パーセント表示用のカスタムツールチップ
 *
 * GDP成長率、寄与度などで使用。符号付きパーセント表示。
 *
 * @example
 * <Tooltip content={<PercentageTooltip labelFormatter={formatQuarterLabel} />} />
 */
export function PercentageTooltip({
  active,
  payload,
  label,
  labelFormatter = (l) => l,
  nameMap,
  decimals = 2,
}: Omit<CustomTooltipProps, 'valueFormatter' | 'getValueColor'> & { decimals?: number }) {
  const formatPercentage = (value: number) => {
    if (value === null || value === undefined) return '-'
    const sign = value >= 0 ? '+' : ''
    return `${sign}${value.toFixed(decimals)}%`
  }

  return (
    <CustomTooltip
      active={active}
      payload={payload}
      label={label}
      labelFormatter={labelFormatter}
      valueFormatter={formatPercentage}
      nameMap={nameMap}
    />
  )
}
