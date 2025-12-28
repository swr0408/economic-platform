/**
 * 雇用コスト指数（Employment Cost Index）チャートコンポーネント
 *
 * FRED ECIALLCIV（Total Compensation）の前期比データを表示
 * - 前期比テーブル
 * - 前期比グラフ
 * - 四半期ごと発表（1月、4月、7月、10月）8:30 ET
 *
 * 共通コンポーネントを使用
 */
import { useState, useCallback } from 'react'
import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { EmploymentCostIndexData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  TOOLTIP_STYLE,
  QUARTER_NAMES,
  MOM_THRESHOLDS,
  getCellColor,
  getValueColor,
  DARK_THEME,
  TEXT_COLORS,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  formatQuarterLabel,
  formatQuarterLabelJP,
  useQuarterlyTableData,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  ViewModeButtonGroup,
  TableLegend,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface EmploymentCostIndexChartProps {
  data: EmploymentCostIndexData | null
}

type ViewMode = 'qoq_table' | 'qoq_chart'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'qoq_table', label: '前期比テーブル' },
  { mode: 'qoq_chart', label: '前期比グラフ' },
]

// カラー設定
const COLORS = {
  qoq: '#1890ff', // 前期比 - 青
}

// 系列名（日本語）
const SERIES_NAMES = {
  qoq: '前期比',
}

// 前期比テーブルの凡例（単位：%）
const CHANGE_LEGEND = [
  { color: 'rgba(82, 196, 26, 0.3)', label: '+0.5%以上' },
  { color: 'rgba(82, 196, 26, 0.15)', label: '0〜+0.5%' },
  { color: 'rgba(255, 77, 79, 0.15)', label: '0〜-0.5%' },
  { color: 'rgba(255, 77, 79, 0.3)', label: '-0.5%以下' },
]

// =============================================================================
// カスタムツールチップ
// =============================================================================

interface TooltipPayload {
  name: string
  value: number
  color: string
  dataKey: string
}

interface CustomTooltipProps {
  active?: boolean
  payload?: TooltipPayload[]
  label?: string
  unit?: string
}

function ChangeTooltip({ active, payload, label, unit = '%' }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, padding: '8px 12px' }}>
        {formatQuarterLabelJP(label || '')}
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
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16 }}>
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
              {sign}{value.toFixed(2)}{unit}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// =============================================================================
// 四半期テーブルコンポーネント
// =============================================================================

interface QuarterlyTableData {
  years: number[]
  quarterlyData: Record<number, Record<number, number | null>>
}

interface QuarterlyTableProps {
  data: QuarterlyTableData
  decimals?: number
  helperText?: string
}

function QuarterlyTable({
  data,
  decimals = 2,
  helperText = '※ 直近10年間の前期比データ（単位: %）',
}: QuarterlyTableProps) {
  const thresholds = MOM_THRESHOLDS.default

  // デフォルトのフォーマット関数
  const formatValue = (value: number | null): string => {
    if (value === null || value === undefined) return '-'
    return `${value >= 0 ? '+' : ''}${value.toFixed(decimals)}`
  }

  if (data.years.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
        データがありません
      </div>
    )
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, marginBottom: 12 }}>
        {helperText}
      </div>
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: 12,
          textAlign: 'center',
          color: DARK_THEME.textPrimary,
        }}
      >
        <thead>
          <tr style={{ backgroundColor: DARK_THEME.bgTertiary }}>
            <th
              style={{
                padding: '8px 4px',
                borderBottom: `2px solid ${DARK_THEME.borderLight}`,
                fontWeight: 'bold',
              }}
            >
              年
            </th>
            {QUARTER_NAMES.map((quarter, idx) => (
              <th
                key={idx}
                style={{
                  padding: '8px 4px',
                  borderBottom: `2px solid ${DARK_THEME.borderLight}`,
                  fontWeight: 'bold',
                  minWidth: 80,
                }}
              >
                {quarter}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.years.map((year) => (
            <tr key={year}>
              <td
                style={{
                  padding: '6px 4px',
                  borderBottom: `1px solid ${DARK_THEME.border}`,
                  fontWeight: 'bold',
                  backgroundColor: DARK_THEME.bgTertiary,
                }}
              >
                {year}
              </td>
              {Array.from({ length: 4 }, (_, quarter) => {
                const value = data.quarterlyData[year]?.[quarter] ?? null
                const displayValue = formatValue(value)
                const bgColor = getCellColor(value, thresholds)
                const textColor = getValueColor(value)

                return (
                  <td
                    key={quarter}
                    style={{
                      padding: '6px 4px',
                      borderBottom: `1px solid ${DARK_THEME.border}`,
                      backgroundColor: bgColor,
                    }}
                  >
                    <span style={{ color: value === null ? TEXT_COLORS.quaternary : textColor }}>
                      {displayValue}
                    </span>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>

      <TableLegend items={CHANGE_LEGEND} />
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function EmploymentCostIndexChart({ data }: EmploymentCostIndexChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('qoq_table')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    qoq_chart: 'default',
    qoq_table: 'default',
  })

  // データのソート
  const sortedData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // 四半期テーブルデータの生成
  const tableData = useQuarterlyTableData(
    sortedData,
    useCallback((item: { pch?: number | null }) => item.pch ?? null, []),
    10
  )

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="雇用コスト指数（前期比）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="雇用コスト指数（前期比）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latest) return []

    return [
      {
        label: SERIES_NAMES.qoq,
        value: latest.pch !== null ? `${latest.pch >= 0 ? '+' : ''}${latest.pch.toFixed(2)}%` : 'N/A',
        color: latest.pch !== null && latest.pch >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative,
      },
    ]
  }

  return (
    <div id="employment-cost-index">
      <ChartContainer
        title="雇用コスト指数（前期比）"
        showPeriodSelector={false}
        dataSource="FRED - ECIALLCIV"
        sourceUrl="https://www.bls.gov/eci/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latest?.date}
          nextRelease={nextRelease}
          dateFormatter={formatQuarterLabel}
        />

        {/* ビューモード切り替え */}
        <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />

        {/* 前期比グラフ */}
        {viewMode === 'qoq_chart' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <ResponsiveContainer width="100%" height={450}>
              <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatQuarterLabel}
                  tick={AXIS_STYLE.tick}
                  interval={AXIS_STYLE.interval}
                />
                <YAxis
                  tick={AXIS_STYLE.tick}
                  tickFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}`}
                  domain={['dataMin - 0.2', 'dataMax + 0.2']}
                  label={{
                    angle: -90,
                    position: 'insideLeft',
                    dy: 20,
                    style: { fontSize: 11, fill: '#666' }
                  }}
                />
                <Tooltip content={<ChangeTooltip />} />
                <Legend />
                <ReferenceLine y={0} stroke="#000" strokeWidth={1} />

                <Bar
                  dataKey="pch"
                  fill={COLORS.qoq}
                  name={SERIES_NAMES.qoq}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </>
        )}

        {/* 前期比テーブル */}
        {viewMode === 'qoq_table' && <QuarterlyTable data={tableData} />}
      </ChartContainer>
    </div>
  )
}
