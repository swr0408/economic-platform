/**
 * ADP雇用者数チャートコンポーネント
 *
 * FRED ADPMNUSNERSA データを使用してADP雇用者数を表示
 *
 * 表示モード:
 * - 現数値（レベル）
 * - 前年比グラフ
 * - 前月比グラフ
 * - 前月比テーブル
 *
 * 共通コンポーネントを使用
 */
import { useState, useMemo } from 'react'
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
import type { ADPEmploymentData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  MONTH_NAMES,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  TOOLTIP_STYLE,
  DARK_THEME,
  TEXT_COLORS,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  formatDateLabel,
  formatDateLabelJP,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  StandardLineChart,
  ViewModeButtonGroup,
  TableLegend,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface ADPEmploymentChartProps {
  data: ADPEmploymentData | null
}

type ViewMode = 'value' | 'mom_chart' | 'mom_table'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'value', label: '現数値' },
  { mode: 'mom_table', label: '前月比テーブル' },
  { mode: 'mom_chart', label: '前月比グラフ' },
]

// カラー設定
const DEFAULT_COLOR = CHART_COLORS.primary

// 前月比テーブルの凡例（単位：千人）
const CHANGE_LEGEND = [
  { color: 'rgba(82, 196, 26, 0.3)', label: '+200k以上' },
  { color: 'rgba(82, 196, 26, 0.15)', label: '0〜+200k' },
  { color: 'rgba(255, 77, 79, 0.15)', label: '0〜-200k' },
  { color: 'rgba(255, 77, 79, 0.3)', label: '-200k以下' },
]

// =============================================================================
// ヘルパー関数
// =============================================================================

/** 前月増減幅用のセル背景色を取得 */
function getChangeCellColor(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'transparent'
  // 閾値: ±200k
  if (value > 200) return 'rgba(82, 196, 26, 0.3)'
  if (value > 0) return 'rgba(82, 196, 26, 0.15)'
  if (value < -200) return 'rgba(255, 77, 79, 0.3)'
  if (value < 0) return 'rgba(255, 77, 79, 0.15)'
  return 'transparent'
}

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

function ChangeTooltip({ active, payload, label, unit = 'k' }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, padding: '8px 12px' }}>
        {formatDateLabelJP(label || '')}
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
              {sign}{value.toLocaleString()}{unit}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function ADPEmploymentChart({ data }: ADPEmploymentChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('value')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    value: 'default',
    mom_chart: 3,
    mom_table: 'default',
  })

  // データのソート
  const sortedData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // テーブル用データ（年別×月別のマトリックス）
  const changeTableData = useMemo(() => {
    if (sortedData.length === 0) return { years: [] as number[], monthlyData: {} as Record<number, Record<number, number | null>> }

    const currentYear = new Date().getFullYear()
    const startYear = currentYear - 9
    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) {
      years.push(y)
    }

    const monthlyData: Record<number, Record<number, number | null>> = {}

    sortedData.forEach((item) => {
      const date = new Date(item.date)
      const year = date.getFullYear()
      const month = date.getMonth()

      if (year >= startYear && year <= currentYear) {
        if (!monthlyData[year]) {
          monthlyData[year] = {}
        }
        monthlyData[year][month] = item.mom ?? null
      }
    })

    return { years, monthlyData }
  }, [sortedData])

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="ADP雇用者数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="ADP雇用者数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latest) return []

    switch (viewMode) {
      case 'value':
        return [
          { label: 'ADP雇用者数', value: latest.value, color: DEFAULT_COLOR, format: 'number' as const, unit: 'k', decimals: 0 },
        ]
      case 'mom_chart':
      case 'mom_table':
        return [
          {
            label: 'ADP雇用者数（前月比）',
            value: latest.mom !== null ? `${latest.mom >= 0 ? '+' : ''}${latest.mom.toLocaleString()}k` : 'N/A',
            color: latest.mom !== null && latest.mom >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative,
          },
        ]
      default:
        return []
    }
  }

  // 前月比テーブルコンポーネント（ダークテーマ）
  const ChangeTable = () => (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, marginBottom: 12 }}>
        ※ 直近10年間の前月増減幅データ（単位: 千人）
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, textAlign: 'center', color: DARK_THEME.textPrimary }}>
        <thead>
          <tr style={{ backgroundColor: DARK_THEME.bgTertiary }}>
            <th style={{ padding: '8px 4px', borderBottom: `2px solid ${DARK_THEME.borderLight}`, fontWeight: 'bold' }}>年</th>
            {MONTH_NAMES.map((month, idx) => (
              <th key={idx} style={{ padding: '8px 4px', borderBottom: `2px solid ${DARK_THEME.borderLight}`, fontWeight: 'bold', minWidth: 55 }}>
                {month}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {changeTableData.years.map((year: number) => (
            <tr key={year}>
              <td style={{ padding: '6px 4px', borderBottom: `1px solid ${DARK_THEME.border}`, fontWeight: 'bold', backgroundColor: DARK_THEME.bgTertiary }}>
                {year}
              </td>
              {Array.from({ length: 12 }, (_, month) => {
                const value = changeTableData.monthlyData[year]?.[month]

                return (
                  <td key={month} style={{ padding: '6px 4px', borderBottom: `1px solid ${DARK_THEME.border}`, backgroundColor: getChangeCellColor(value) }}>
                    {value !== null && value !== undefined ? (
                      <span style={{ color: value >= 0 ? TEXT_COLORS.positive : TEXT_COLORS.negative }}>
                        {value >= 0 ? '+' : ''}{value.toLocaleString()}
                      </span>
                    ) : (
                      <span style={{ color: TEXT_COLORS.quaternary }}>-</span>
                    )}
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

  return (
    <div id="adp-employment">
      <ChartContainer
        title="ADP雇用者数"
        showPeriodSelector={false}
        dataSource="FRED / ADP"
        sourceUrl="https://adpemploymentreport.com/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latest?.date}
          nextRelease={nextRelease}
        />

        {/* ビューモード切り替え */}
        <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />

        {/* 現数値グラフ */}
        {viewMode === 'value' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardLineChart
              data={filteredData}
              lines={[
                {
                  dataKey: 'value',
                  color: DEFAULT_COLOR,
                  name: 'ADP雇用者数',
                },
              ]}
              yAxisFormatter={(v) => `${v.toLocaleString()}`}
              yDomain={['dataMin - 1000', 'dataMax + 1000']}
              tooltipLabelFormatter={formatDateLabelJP}
              tooltipFormatter={(value: unknown, name: string) => [
                `${(value as number).toLocaleString()}k`,
                name,
              ]}
              showZeroLine={false}
            />
          </>
        )}

        {/* 前月比グラフ */}
        {viewMode === 'mom_chart' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <ResponsiveContainer width="100%" height={450}>
              <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatDateLabel}
                  tick={AXIS_STYLE.tick}
                  interval={AXIS_STYLE.interval}
                />
                <YAxis
                  tick={AXIS_STYLE.tick}
                  tickFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toLocaleString()}`}
                  domain={['dataMin - 100', 'dataMax + 100']}
                  label={{
                    value: '増減（k）',
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
                  dataKey="mom"
                  fill={DEFAULT_COLOR}
                  name="ADP雇用者数（前月比）"
                />
              </ComposedChart>
            </ResponsiveContainer>
          </>
        )}

        {/* 前月比テーブル */}
        {viewMode === 'mom_table' && <ChangeTable />}
      </ChartContainer>
    </div>
  )
}
