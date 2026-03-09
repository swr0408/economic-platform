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
import { useState } from 'react'
import { Tabs, Button, Tooltip as AntTooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import MarketImpactTab from '../../../indicator/MarketImpactTab'
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
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  CHANGE_LEGEND_04PCT,
  getChangeCellColor04pct,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMonthlyTableData,
  formatDateLabel,
  useHiddenSeries,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  ViewModeButtonGroup,
  ChangeTooltip,
  ValueTooltip,
} from '../common/ChartComponents'
import { MonthlyTable } from '../common/MonthlyTable'

// =============================================================================
// 型定義
// =============================================================================

interface AverageHourlyEarningsChartProps {
  data: AverageHourlyEarningsData | null
}

// 指標種別
type DataKind = 'yoy' | 'mom'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
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

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function AverageHourlyEarningsChart({ data }: AverageHourlyEarningsChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // 指標種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 10,
    mom: 3,
  })

  // データのソート
  const sortedData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // テーブル用データ（共通フックを使用）
  const changeTableData = useMonthlyTableData(
    sortedData,
    (item) => item.mom,
    10
  )


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

    switch (dataKind) {
      case 'yoy':
        return [
          { label: SERIES_NAMES.yoy, value: latest.yoy, color: COLORS.yoy, format: 'percent' as const, decimals: 2 },
          { label: SERIES_NAMES.quits_rate, value: latest.quits_rate, color: COLORS.quits_rate, format: 'number' as const, unit: '%', decimals: 1 },
        ]
      case 'mom':
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

        {/* タブ切替 */}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* 上段: 指標種別 */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />
                    <AntTooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=average_hourly_earnings_yoy', '_blank')}
                      >
                        データ比較
                      </Button>
                    </AntTooltip>
                  </div>

                  {/* 下段: 表示形式（前月比のときのみ） */}
                  {dataKind === 'mom' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 前年比グラフ（YoYモード） */}
                  {dataKind === 'yoy' && (
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
                              value: '平均時給（%）',
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
                          <Tooltip content={<ValueTooltip unit="%" decimals={2} />} />
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
                            connectNulls={false}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </>
                  )}

                  {/* 前月比チャート */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
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
                              angle: -90,
                              position: 'insideLeft',
                              dy: 20,
                              style: { fontSize: 11, fill: '#666' }
                            }}
                          />
                          <Tooltip content={<ChangeTooltip unit="%" decimals={2} />} />
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

                  {/* 前月比ヒートマップ */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTable
                      data={changeTableData}
                      getCellBgColor={getChangeCellColor04pct}
                      legendItems={CHANGE_LEGEND_04PCT}
                      helperText="※ 直近10年間の前月比データ（単位: %）"
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="average_hourly_earnings_yoy" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
