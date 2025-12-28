/**
 * フルタイム/パートタイム雇用者数チャートコンポーネント
 *
 * FRED データを使用して雇用形態別雇用者数を表示
 * - フルタイム雇用者数（Employed Full Time: LNS12500000）- 左Y軸
 * - パートタイム雇用者数（Employed Part Time: LNS12600000）- 右Y軸
 *
 * 表示モード:
 * - 現数値（レベル）- 左右Y軸
 * - 前月増減幅グラフ
 * - 前月増減幅テーブル
 *
 * フルタイムとパートタイムはスケールが大きく異なるため
 * 現数値モードでは左右のY軸で表示
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
import type { FullPartTimeEmploymentData } from '../../../../hooks/useDashboardData'

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

interface FullPartTimeChartProps {
  data: FullPartTimeEmploymentData | null
}

type ViewMode = 'value' | 'change_chart' | 'change_table'
type DataType = 'fulltime' | 'parttime'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'value', label: '現数値' },
  { mode: 'change_table', label: '前月増減幅テーブル' },
  { mode: 'change_chart', label: '前月増減幅グラフ' },
]

// データタイプ設定
const DATA_TYPE_OPTIONS: { type: DataType; label: string }[] = [
  { type: 'fulltime', label: 'フルタイム' },
  { type: 'parttime', label: 'パートタイム' },
]

// カラー設定（サービスから取得したものを優先、フォールバック用）
const DEFAULT_COLORS = {
  fulltime: CHART_COLORS.primary,     // 青（左軸）
  parttime: CHART_COLORS.orange,      // オレンジ（右軸）
}

// 系列名（日本語）
const SERIES_NAMES = {
  fulltime: 'フルタイム',
  parttime: 'パートタイム',
}

// 前月増減幅テーブルの凡例
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

export default function FullPartTimeChart({ data }: FullPartTimeChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('value')
  const [dataType, setDataType] = useState<DataType>('fulltime')
  const { handleLegendClick, isHidden } = useHiddenSeries<'fulltime' | 'parttime' | 'fulltime_change' | 'parttime_change'>()

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
        fulltime_change: prevItem && item.fulltime !== null && prevItem.fulltime !== null
          ? Math.round(item.fulltime - prevItem.fulltime)
          : null,
        parttime_change: prevItem && item.parttime !== null && prevItem.parttime !== null
          ? Math.round(item.parttime - prevItem.parttime)
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
    if (chartData.length === 0) return { years: [] as number[], monthlyData: {} as Record<number, Record<number, { fulltime: number | null; parttime: number | null }>> }

    const currentYear = new Date().getFullYear()
    const startYear = currentYear - 9
    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) {
      years.push(y)
    }

    const monthlyData: Record<number, Record<number, { fulltime: number | null; parttime: number | null }>> = {}

    chartData.forEach((item) => {
      const date = new Date(item.date)
      const year = date.getFullYear()
      const month = date.getMonth()

      if (year >= startYear && year <= currentYear) {
        if (!monthlyData[year]) {
          monthlyData[year] = {}
        }
        monthlyData[year][month] = {
          fulltime: item.fulltime_change,
          parttime: item.parttime_change,
        }
      }
    })

    return { years, monthlyData }
  }, [chartData])

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="フルタイム / パートタイム雇用者数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="フルタイム / パートタイム雇用者数" showPeriodSelector={false} showDataSource={false}>
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
        { label: SERIES_NAMES.fulltime, value: latest.fulltime, color: getColor('fulltime'), format: 'number' as const, unit: 'k', decimals: 0 },
        { label: SERIES_NAMES.parttime, value: latest.parttime, color: getColor('parttime'), format: 'number' as const, unit: 'k', decimals: 0 },
      ] : []
    } else {
      // 前月増減幅モード
      if (!latestChange) return []
      const ftChange = latestChange.fulltime_change
      const ptChange = latestChange.parttime_change
      return [
        {
          label: `${SERIES_NAMES.fulltime}（増減）`,
          value: ftChange !== null ? `${ftChange >= 0 ? '+' : ''}${ftChange.toLocaleString()}k` : 'N/A',
          color: ftChange !== null && ftChange >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative,
        },
        {
          label: `${SERIES_NAMES.parttime}（増減）`,
          value: ptChange !== null ? `${ptChange >= 0 ? '+' : ''}${ptChange.toLocaleString()}k` : 'N/A',
          color: ptChange !== null && ptChange >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative,
        },
      ]
    }
  }

  // 前月増減幅テーブルコンポーネント（ダークテーマ）
  const ChangeTable = () => (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, marginBottom: 12 }}>
        ※ 直近10年間の前月増減幅データ（単位: 千人）
      </div>
      <DataTypeButtonGroup
        options={DATA_TYPE_OPTIONS}
        currentType={dataType}
        onChange={setDataType}
      />
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
                const cellData = changeTableData.monthlyData[year]?.[month]
                const value = dataType === 'fulltime' ? cellData?.fulltime : cellData?.parttime

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
    <div id="fullpart-time">
      <ChartContainer
        title="フルタイム / パートタイム雇用者数"
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
                {/* 左Y軸: フルタイム（千人単位でそのまま表示） */}
                <YAxis
                  yAxisId="left"
                  domain={['dataMin - 1000', 'dataMax + 1000']}
                  tick={AXIS_STYLE.tick}
                  tickFormatter={(v) => `${v.toLocaleString()}`}
                  label={{
                    value: 'フルタイム（k）',
                    angle: -90,
                    position: 'insideLeft',
                    style: { fontSize: 11, fill: getColor('fulltime') }
                  }}
                />
                {/* 右Y軸: パートタイム（千人単位でそのまま表示） */}
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  domain={['dataMin - 500', 'dataMax + 500']}
                  tick={AXIS_STYLE.tick}
                  tickFormatter={(v) => `${v.toLocaleString()}`}
                  label={{
                    value: 'パートタイム（k）',
                    angle: 90,
                    position: 'insideRight',
                    style: { fontSize: 11, fill: getColor('parttime') }
                  }}
                />
                <Tooltip content={<ValueTooltip />} />
                <Legend
                  onClick={(e) => handleLegendClick(e.dataKey as string)}
                  wrapperStyle={{ cursor: 'pointer' }}
                />

                {/* フルタイム（左軸） */}
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="fulltime"
                  stroke={getColor('fulltime')}
                  strokeWidth={2}
                  dot={false}
                  name={SERIES_NAMES.fulltime}
                  hide={isHidden('fulltime')}
                  isAnimationActive={false}
                  connectNulls={true}
                />

                {/* パートタイム（右軸） */}
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="parttime"
                  stroke={getColor('parttime')}
                  strokeWidth={2}
                  dot={false}
                  name={SERIES_NAMES.parttime}
                  hide={isHidden('parttime')}
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

                {/* 選択されたデータタイプのみ表示 */}
                {dataType === 'fulltime' && (
                  <Bar
                    dataKey="fulltime_change"
                    fill={getColor('fulltime')}
                    name={`${SERIES_NAMES.fulltime}（増減）`}
                  />
                )}
                {dataType === 'parttime' && (
                  <Bar
                    dataKey="parttime_change"
                    fill={getColor('parttime')}
                    name={`${SERIES_NAMES.parttime}（増減）`}
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
