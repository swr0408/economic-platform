/**
 * 複数の仕事を持つ人 / 経済的理由によるパートタイムチャートコンポーネント
 *
 * FRED データを使用して表示
 * - 複数の仕事を持つ人（Multiple Jobholders: LNS12026619）- 左Y軸
 * - 経済的理由によるパートタイム（Part-Time for Economic Reasons: LNS12032194）- 右Y軸
 *
 * 表示モード:
 * - 現数値（レベル）- 左右Y軸
 * - 前月増減幅グラフ
 * - 前月増減幅テーブル
 *
 * スケールが異なるため現数値モードでは左右のY軸で表示
 *
 * 共通コンポーネントを使用
 */
import { useState, useMemo } from 'react'
import {
  ComposedChart,
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
import type { MultipleJobsPartTimeData } from '../../../../hooks/useDashboardData'

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
  DataTypeButtonGroup,
  TableLegend,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface MultipleJobsPartTimeChartProps {
  data: MultipleJobsPartTimeData | null
}

type ViewMode = 'value' | 'change_chart' | 'change_table'
type DataType = 'multiple_jobs' | 'parttime_econ'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'value', label: '現数値' },
  { mode: 'change_table', label: '前月増減幅テーブル' },
  { mode: 'change_chart', label: '前月増減幅グラフ' },
]

// データタイプ設定
const DATA_TYPE_OPTIONS: { type: DataType; label: string }[] = [
  { type: 'multiple_jobs', label: '複数の仕事' },
  { type: 'parttime_econ', label: '経済的理由パートタイム' },
]

// カラー設定（サービスから取得したものを優先、フォールバック用）
const DEFAULT_COLORS = {
  multiple_jobs: CHART_COLORS.primary,     // 青（左軸）
  parttime_econ: CHART_COLORS.orange,      // オレンジ（右軸）
}

// 系列名（日本語）
const SERIES_NAMES = {
  multiple_jobs: '複数の仕事を持つ人',
  parttime_econ: '経済的理由によるパートタイム',
}

// 前月増減幅テーブルの凡例
const CHANGE_LEGEND = [
  { color: 'rgba(82, 196, 26, 0.3)', label: '+100k以上' },
  { color: 'rgba(82, 196, 26, 0.15)', label: '0〜+100k' },
  { color: 'rgba(255, 77, 79, 0.15)', label: '0〜-100k' },
  { color: 'rgba(255, 77, 79, 0.3)', label: '-100k以下' },
]

// =============================================================================
// ヘルパー関数
// =============================================================================

/** 前月増減幅用のセル背景色を取得 */
function getChangeCellColor(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'transparent'
  // 閾値: ±100k（この指標は規模が小さめ）
  if (value > 100) return 'rgba(82, 196, 26, 0.3)'
  if (value > 0) return 'rgba(82, 196, 26, 0.15)'
  if (value < -100) return 'rgba(255, 77, 79, 0.3)'
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
}

function ValueTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, padding: '8px 12px' }}>
        {formatDateLabelJP(label || '')}
      </div>
      {payload.map((item, index) => {
        // 千人単位でそのまま表示（FREDは千人単位で提供）
        const valueInThousands = item.value.toLocaleString()
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
            <span style={{ fontWeight: 500 }}>
              {valueInThousands}k
            </span>
          </div>
        )
      })}
    </div>
  )
}

function ChangeTooltip({ active, payload, label }: CustomTooltipProps) {
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
              {sign}{value.toLocaleString()}k
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

export default function MultipleJobsPartTimeChart({ data }: MultipleJobsPartTimeChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('value')
  const [dataType, setDataType] = useState<DataType>('multiple_jobs')
  const { handleLegendClick, isHidden } = useHiddenSeries<'multiple_jobs' | 'parttime_econ' | 'multiple_jobs_change' | 'parttime_econ_change'>()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    value: 'default',
    change_chart: 3,
    change_table: 'default',
  })

  // データのソート
  const sortedData = useSortedData(data?.data)

  // 前月増減幅を計算
  const chartData = useMemo(() => {
    if (sortedData.length === 0) return []

    return sortedData.map((item, index) => {
      const prevItem = index > 0 ? sortedData[index - 1] : null
      return {
        ...item,
        multiple_jobs_change: prevItem && item.multiple_jobs !== null && prevItem.multiple_jobs !== null
          ? Math.round(item.multiple_jobs - prevItem.multiple_jobs)
          : null,
        parttime_econ_change: prevItem && item.parttime_econ !== null && prevItem.parttime_econ !== null
          ? Math.round(item.parttime_econ - prevItem.parttime_econ)
          : null,
      }
    })
  }, [sortedData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // テーブル用データ（年別×月別のマトリックス）
  const changeTableData = useMemo(() => {
    if (chartData.length === 0) return { years: [] as number[], monthlyData: {} as Record<number, Record<number, { multiple_jobs: number | null; parttime_econ: number | null }>> }

    const currentYear = new Date().getFullYear()
    const startYear = currentYear - 9
    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) {
      years.push(y)
    }

    const monthlyData: Record<number, Record<number, { multiple_jobs: number | null; parttime_econ: number | null }>> = {}

    chartData.forEach((item) => {
      const date = new Date(item.date)
      const year = date.getFullYear()
      const month = date.getMonth()

      if (year >= startYear && year <= currentYear) {
        if (!monthlyData[year]) {
          monthlyData[year] = {}
        }
        monthlyData[year][month] = {
          multiple_jobs: item.multiple_jobs_change,
          parttime_econ: item.parttime_econ_change,
        }
      }
    })

    return { years, monthlyData }
  }, [chartData])

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="複数の仕事を持つ人 / 経済的理由によるパートタイム" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="複数の仕事を持つ人 / 経済的理由によるパートタイム" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release
  const seriesConfig = data.series_config || {}

  // 色を取得（サービス設定 > デフォルト）
  const getColor = (key: string): string => {
    return seriesConfig[key]?.color || DEFAULT_COLORS[key as keyof typeof DEFAULT_COLORS] || '#1890ff'
  }

  // 最新の前月増減幅を計算
  const latestChange = chartData.length >= 2 ? chartData[chartData.length - 1] : null

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (viewMode === 'value') {
      return latest ? [
        { label: SERIES_NAMES.multiple_jobs, value: latest.multiple_jobs, color: getColor('multiple_jobs'), format: 'number' as const, unit: 'k', decimals: 0 },
        { label: SERIES_NAMES.parttime_econ, value: latest.parttime_econ, color: getColor('parttime_econ'), format: 'number' as const, unit: 'k', decimals: 0 },
      ] : []
    } else {
      // 前月増減幅モード
      if (!latestChange) return []
      const mjChange = latestChange.multiple_jobs_change
      const peChange = latestChange.parttime_econ_change
      return [
        {
          label: `${SERIES_NAMES.multiple_jobs}（増減）`,
          value: mjChange !== null ? `${mjChange >= 0 ? '+' : ''}${mjChange.toLocaleString()}k` : 'N/A',
          color: mjChange !== null && mjChange >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative,
        },
        {
          label: `${SERIES_NAMES.parttime_econ}（増減）`,
          value: peChange !== null ? `${peChange >= 0 ? '+' : ''}${peChange.toLocaleString()}k` : 'N/A',
          color: peChange !== null && peChange >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative,
        },
      ]
    }
  }

  // 前月増減幅テーブルコンポーネント
  const ChangeTable = () => (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ fontSize: 11, color: '#888', marginBottom: 12 }}>
        ※ 直近10年間の前月増減幅データ（単位: 千人）
      </div>
      <DataTypeButtonGroup
        options={DATA_TYPE_OPTIONS}
        currentType={dataType}
        onChange={setDataType}
      />
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
                const cellData = changeTableData.monthlyData[year]?.[month]
                const value = dataType === 'multiple_jobs' ? cellData?.multiple_jobs : cellData?.parttime_econ

                return (
                  <td key={month} style={{ padding: '6px 4px', borderBottom: '1px solid #e8e8e8', backgroundColor: getChangeCellColor(value) }}>
                    {value !== null && value !== undefined ? (
                      <span style={{ color: value >= 0 ? '#389e0d' : '#cf1322' }}>
                        {value >= 0 ? '+' : ''}{value.toLocaleString()}
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
    <div id="multiple-jobs-parttime">
      <ChartContainer
        title="複数の仕事を持つ人 / 経済的理由によるパートタイム"
        showPeriodSelector={false}
        dataSource="FRED / BLS"
        sourceUrl="https://www.bls.gov/news.release/empsit.toc.htm"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latestChange?.date || latest?.date}
          nextRelease={nextRelease}
        />

        {/* ビューモード切り替え */}
        <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />

        {/* 現数値グラフ（左右Y軸） */}
        {viewMode === 'value' && (
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
                {/* 左Y軸: 複数の仕事を持つ人（千人単位でそのまま表示） */}
                <YAxis
                  yAxisId="left"
                  domain={['dataMin - 500', 'dataMax + 500']}
                  tick={AXIS_STYLE.tick}
                  tickFormatter={(v) => `${v.toLocaleString()}`}
                  label={{
                    value: '複数の仕事を持つ人（k）',
                    angle: -90,
                    position: 'insideLeft',
                    dy: 60,
                    style: { fontSize: 11, fill: getColor('multiple_jobs') }
                  }}
                />
                {/* 右Y軸: 経済的理由によるパートタイム（千人単位でそのまま表示） */}
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  domain={['dataMin - 500', 'dataMax + 500']}
                  tick={AXIS_STYLE.tick}
                  tickFormatter={(v) => `${v.toLocaleString()}`}
                  label={{
                    value: '経済的理由によるパートタイム（k）',
                    angle: 90,
                    position: 'insideRight',
                    dy: 90,
                    style: { fontSize: 11, fill: getColor('parttime_econ') }
                  }}
                />
                <Tooltip content={<ValueTooltip />} />
                <Legend
                  onClick={(e) => handleLegendClick(e.dataKey as string)}
                  wrapperStyle={{ cursor: 'pointer' }}
                />

                {/* 複数の仕事を持つ人（左軸） */}
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="multiple_jobs"
                  stroke={getColor('multiple_jobs')}
                  strokeWidth={2}
                  dot={false}
                  name={SERIES_NAMES.multiple_jobs}
                  hide={isHidden('multiple_jobs')}
                  isAnimationActive={false}
                  connectNulls={true}
                />

                {/* 経済的理由によるパートタイム（右軸） */}
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="parttime_econ"
                  stroke={getColor('parttime_econ')}
                  strokeWidth={2}
                  dot={false}
                  name={SERIES_NAMES.parttime_econ}
                  hide={isHidden('parttime_econ')}
                  isAnimationActive={false}
                  connectNulls={true}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </>
        )}

        {/* 前月増減幅グラフ */}
        {viewMode === 'change_chart' && (
          <>
            <DataTypeButtonGroup
              options={DATA_TYPE_OPTIONS}
              currentType={dataType}
              onChange={setDataType}
            />
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
                  domain={['dataMin - 50', 'dataMax + 50']}
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

                {/* 選択されたデータタイプのみ表示 */}
                {dataType === 'multiple_jobs' && (
                  <Bar
                    dataKey="multiple_jobs_change"
                    fill={getColor('multiple_jobs')}
                    name={`${SERIES_NAMES.multiple_jobs}（増減）`}
                  />
                )}
                {dataType === 'parttime_econ' && (
                  <Bar
                    dataKey="parttime_econ_change"
                    fill={getColor('parttime_econ')}
                    name={`${SERIES_NAMES.parttime_econ}（増減）`}
                  />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </>
        )}

        {/* 前月増減幅テーブル */}
        {viewMode === 'change_table' && <ChangeTable />}
      </ChartContainer>
    </div>
  )
}
