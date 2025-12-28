/**
 * 非農業部門雇用者数チャートコンポーネント
 *
 * FRED データを使用して雇用者数を表示
 * - 非農業部門雇用者数（Total Nonfarm Payrolls: PAYEMS）
 * - 民間雇用者数（Civilian Employment: CE16OV）
 *
 * 表示モード:
 * - 現数値（レベル）
 * - 前月増減幅グラフ
 * - 前月増減幅テーブル
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
import type { NonfarmPayrollsData } from '../../../../hooks/useDashboardData'

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
  createUnitFormatter,
  useHiddenSeries,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  StandardLineChart,
  ViewModeButtonGroup,
  DataTypeButtonGroup,
  TableLegend,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface NonfarmPayrollsChartProps {
  data: NonfarmPayrollsData | null
}

type ViewMode = 'value' | 'change_chart' | 'change_table'
type DataType = 'nonfarm' | 'civilian'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'value', label: '現数値' },
  { mode: 'change_table', label: '前月増減幅テーブル' },
  { mode: 'change_chart', label: '前月増減幅グラフ' },
]

// データタイプ設定
const DATA_TYPE_OPTIONS: { type: DataType; label: string }[] = [
  { type: 'nonfarm', label: '非農業部門' },
  { type: 'civilian', label: '民間雇用者' },
]

// カラー設定（サービスから取得したものを優先、フォールバック用）
const DEFAULT_COLORS = {
  nonfarm: '#1890ff',
  civilian: '#52c41a',
}

// 系列名（日本語）
const SERIES_NAMES = {
  nonfarm: '非農業部門雇用者数',
  civilian: '民間雇用者数',
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

export default function NonfarmPayrollsChart({ data }: NonfarmPayrollsChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('value')
  const [dataType, setDataType] = useState<DataType>('nonfarm')
  const { handleLegendClick, isHidden } = useHiddenSeries<'nonfarm' | 'civilian' | 'nonfarm_change' | 'civilian_change'>()

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
        nonfarm_change: prevItem && item.nonfarm !== null && prevItem.nonfarm !== null
          ? Math.round(item.nonfarm - prevItem.nonfarm)
          : null,
        civilian_change: prevItem && item.civilian !== null && prevItem.civilian !== null
          ? Math.round(item.civilian - prevItem.civilian)
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
    if (chartData.length === 0) return { years: [] as number[], monthlyData: {} as Record<number, Record<number, { nonfarm: number | null; civilian: number | null }>> }

    const currentYear = new Date().getFullYear()
    const startYear = currentYear - 9
    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) {
      years.push(y)
    }

    const monthlyData: Record<number, Record<number, { nonfarm: number | null; civilian: number | null }>> = {}

    chartData.forEach((item) => {
      const date = new Date(item.date)
      const year = date.getFullYear()
      const month = date.getMonth()

      if (year >= startYear && year <= currentYear) {
        if (!monthlyData[year]) {
          monthlyData[year] = {}
        }
        monthlyData[year][month] = {
          nonfarm: item.nonfarm_change,
          civilian: item.civilian_change,
        }
      }
    })

    return { years, monthlyData }
  }, [chartData])

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="非農業部門雇用者数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="非農業部門雇用者数" showPeriodSelector={false} showDataSource={false}>
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
        { label: SERIES_NAMES.nonfarm, value: latest.nonfarm, color: getColor('nonfarm'), format: 'number' as const, unit: 'k', decimals: 0 },
        { label: SERIES_NAMES.civilian, value: latest.civilian, color: getColor('civilian'), format: 'number' as const, unit: 'k', decimals: 0 },
      ] : []
    } else {
      // 前月増減幅モード
      if (!latestChange) return []
      const nfChange = latestChange.nonfarm_change
      const cvChange = latestChange.civilian_change
      return [
        {
          label: `${SERIES_NAMES.nonfarm}（増減）`,
          value: nfChange !== null ? `${nfChange >= 0 ? '+' : ''}${nfChange.toLocaleString()}k` : 'N/A',
          color: nfChange !== null && nfChange >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative,
        },
        {
          label: `${SERIES_NAMES.civilian}（増減）`,
          value: cvChange !== null ? `${cvChange >= 0 ? '+' : ''}${cvChange.toLocaleString()}k` : 'N/A',
          color: cvChange !== null && cvChange >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative,
        },
      ]
    }
  }

  // 前月増減幅テーブルコンポーネント
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
                const value = dataType === 'nonfarm' ? cellData?.nonfarm : cellData?.civilian

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
    <div id="nonfarm-payrolls">
      <ChartContainer
        title="非農業部門雇用者数"
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

        {/* 現数値グラフ */}
        {viewMode === 'value' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardLineChart
              data={filteredData}
              lines={[
                {
                  dataKey: 'nonfarm',
                  color: getColor('nonfarm'),
                  name: SERIES_NAMES.nonfarm,
                  hide: isHidden('nonfarm'),
                },
                {
                  dataKey: 'civilian',
                  color: getColor('civilian'),
                  name: SERIES_NAMES.civilian,
                  hide: isHidden('civilian'),
                },
              ]}
              yAxisFormatter={(v) => `${v.toLocaleString()}`}
              yDomain={['dataMin - 1000', 'dataMax + 1000']}
              tooltipLabelFormatter={formatDateLabelJP}
              tooltipFormatter={createUnitFormatter('k', 0)}
              showZeroLine={false}
              onLegendClick={handleLegendClick}
            />
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
                {dataType === 'nonfarm' && (
                  <Bar
                    dataKey="nonfarm_change"
                    fill={getColor('nonfarm')}
                    name={`${SERIES_NAMES.nonfarm}（増減）`}
                  />
                )}
                {dataType === 'civilian' && (
                  <Bar
                    dataKey="civilian_change"
                    fill={getColor('civilian')}
                    name={`${SERIES_NAMES.civilian}（増減）`}
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
