/**
 * 平均時給 / 自発的離職率チャートコンポーネント
 *
 * FRED データを使用して平均時給と自発的離職率を表示
 * - 平均時給（前年比）: CES0500000003
 * - 自発的離職率: JTSQUR
 *
 * 表示モード:
 * - 前年比グラフ（平均時給 + 自発的離職率）
 * - 前月比テーブル
 * - 前月比グラフ
 *
 * 共通コンポーネントを使用
 */
import { useState, useMemo } from 'react'
import {
  ComposedChart,
  LineChart,
  Line,
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
import type { AverageHourlyEarningsData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  MONTH_NAMES,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  TOOLTIP_STYLE,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  formatDateLabel,
  formatDateLabelJP,
  useHiddenSeries,
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

interface AverageHourlyEarningsChartProps {
  data: AverageHourlyEarningsData | null
}

type ViewMode = 'yoy' | 'mom_table' | 'mom_chart'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom_table', label: '前月比テーブル' },
  { mode: 'mom_chart', label: '前月比グラフ' },
]

// カラー設定
const COLORS = {
  yoy: '#1890ff',        // 前年比 - 青
  mom: '#52c41a',        // 前月比 - 緑
  quits_rate: '#722ed1', // 自発的離職率 - 紫
}

// 系列名（日本語）
const SERIES_NAMES = {
  yoy: '平均時給（前年比）',
  mom: '平均時給（前月比）',
  quits_rate: '自発的離職率',
}

// 前月比テーブルの凡例（単位：%）
const CHANGE_LEGEND = [
  { color: 'rgba(82, 196, 26, 0.3)', label: '+0.4%以上' },
  { color: 'rgba(82, 196, 26, 0.15)', label: '0〜+0.4%' },
  { color: 'rgba(255, 77, 79, 0.15)', label: '0〜-0.4%' },
  { color: 'rgba(255, 77, 79, 0.3)', label: '-0.4%以下' },
]

// =============================================================================
// ヘルパー関数
// =============================================================================

/** 前月比用のセル背景色を取得 */
function getChangeCellColor(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'transparent'
  // 閾値: ±0.4%
  if (value > 0.4) return 'rgba(82, 196, 26, 0.3)'
  if (value > 0) return 'rgba(82, 196, 26, 0.15)'
  if (value < -0.4) return 'rgba(255, 77, 79, 0.3)'
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

function ChangeTooltip({ active, payload, label, unit = '%' }: CustomTooltipProps) {
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
// メインコンポーネント
// =============================================================================

export default function AverageHourlyEarningsChart({ data }: AverageHourlyEarningsChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
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
    return <LoadingChart title="平均時給 / 自発的離職率" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="平均時給 / 自発的離職率" showPeriodSelector={false} showDataSource={false}>
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
      case 'yoy':
        return [
          { label: SERIES_NAMES.yoy, value: latest.yoy, color: COLORS.yoy, format: 'percent' as const, decimals: 2 },
          { label: SERIES_NAMES.quits_rate, value: latest.quits_rate, color: COLORS.quits_rate, format: 'number' as const, unit: '%', decimals: 1 },
        ]
      case 'mom_chart':
      case 'mom_table':
        return [
          {
            label: SERIES_NAMES.mom,
            value: latest.mom !== null ? `${latest.mom >= 0 ? '+' : ''}${latest.mom.toFixed(2)}%` : 'N/A',
            color: latest.mom !== null && latest.mom >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative,
          },
        ]
      default:
        return []
    }
  }

  // 前月比テーブルコンポーネント
  const ChangeTable = () => (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ fontSize: 11, color: '#888', marginBottom: 12 }}>
        ※ 直近10年間の前月比データ（単位: %）
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, textAlign: 'center' }}>
        <thead>
          <tr style={{ backgroundColor: '#fafafa' }}>
            <th style={{ padding: '8px 4px', borderBottom: '2px solid #d9d9d9', fontWeight: 'bold' }}>年</th>
            {MONTH_NAMES.map((month, idx) => (
              <th key={idx} style={{ padding: '8px 4px', borderBottom: '2px solid #d9d9d9', fontWeight: 'bold', minWidth: 55 }}>
                {month}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {changeTableData.years.map((year: number) => (
            <tr key={year}>
              <td style={{ padding: '6px 4px', borderBottom: '1px solid #e8e8e8', fontWeight: 'bold', backgroundColor: '#fafafa' }}>
                {year}
              </td>
              {Array.from({ length: 12 }, (_, month) => {
                const value = changeTableData.monthlyData[year]?.[month]

                return (
                  <td key={month} style={{ padding: '6px 4px', borderBottom: '1px solid #e8e8e8', backgroundColor: getChangeCellColor(value) }}>
                    {value !== null && value !== undefined ? (
                      <span style={{ color: value >= 0 ? '#389e0d' : '#cf1322' }}>
                        {value >= 0 ? '+' : ''}{value.toFixed(2)}
                      </span>
                    ) : (
                      <span style={{ color: '#bfbfbf' }}>-</span>
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
    <div id="average-hourly-earnings">
      <ChartContainer
        title="平均時給 / 自発的離職率"
        showPeriodSelector={false}
        dataSource="FRED / BLS"
        sourceUrl="https://www.bls.gov/news.release/realer.toc.htm"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latest?.date}
          nextRelease={nextRelease}
        />

        {/* ビューモード切り替え */}
        <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />

        {/* 前年比グラフ（YoYモード） */}
        {viewMode === 'yoy' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <ResponsiveContainer width="100%" height={450}>
              <LineChart data={filteredData} margin={CHART_MARGIN}>
                <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatDateLabel}
                  tick={AXIS_STYLE.tick}
                  interval={AXIS_STYLE.interval}
                />
                <YAxis
                  yAxisId="left"
                  tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                  tick={AXIS_STYLE.tick}
                  domain={['dataMin - 0.2', 'dataMax + 0.2']}
                  label={{
                    value: '前年比（%）',
                    angle: -90,
                    position: 'insideLeft',
                    dy: 30,
                    style: { fontSize: 11, fill: '#666' }
                  }}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                  tick={AXIS_STYLE.tick}
                  domain={['dataMin - 0.05', 'dataMax + 0.05']}
                  label={{
                    value: '離職率（%）',
                    angle: 90,
                    position: 'insideRight',
                    dy: 30,
                    style: { fontSize: 11, fill: '#666' }
                  }}
                />
                <Tooltip
                  labelFormatter={formatDateLabelJP}
                  formatter={(value: number, name: string) => [`${value.toFixed(2)}%`, name]}
                  contentStyle={TOOLTIP_STYLE}
                />
                <Legend onClick={(e) => handleLegendClick(e.dataKey as string)} />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="yoy"
                  name={SERIES_NAMES.yoy}
                  stroke={COLORS.yoy}
                  strokeWidth={2}
                  dot={false}
                  hide={hiddenSeries.has('yoy')}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="quits_rate"
                  name={SERIES_NAMES.quits_rate}
                  stroke={COLORS.quits_rate}
                  strokeWidth={2}
                  dot={false}
                  hide={hiddenSeries.has('quits_rate')}
                />
              </LineChart>
            </ResponsiveContainer>
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
                  tickFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}`}
                  domain={['dataMin - 0.2', 'dataMax + 0.2']}
                  label={{
                    value: '増減（%）',
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
                  fill={COLORS.mom}
                  name={SERIES_NAMES.mom}
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
