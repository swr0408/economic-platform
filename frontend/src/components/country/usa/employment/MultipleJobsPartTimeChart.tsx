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
import { Tabs, Button, Tooltip as AntTooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import MarketImpactTab from '../../../indicator/MarketImpactTab'
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
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  VALUE_CHANGE_DATA_KIND_OPTIONS,
  type ValueChangeDataKind,
  DISPLAY_MODE_OPTIONS,
  type DisplayMode,
  CHANGE_LEGEND_100K,
  getChangeCellColor100k,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMultiValueMonthlyTableData,
  formatDateLabel,
  useHiddenSeries,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  ViewModeButtonGroup,
  DataTypeButtonGroup,
  ChangeTooltip,
  ValueTooltip,
} from '../common/ChartComponents'
import { MonthlyTableWithDataTypes } from '../common/MonthlyTable'

// =============================================================================
// 型定義
// =============================================================================

interface MultipleJobsPartTimeChartProps {
  data: MultipleJobsPartTimeData | null
}

type DataType = 'multiple_jobs' | 'parttime_econ'

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


// =============================================================================
// メインコンポーネント
// =============================================================================

export default function MultipleJobsPartTimeChart({ data }: MultipleJobsPartTimeChartProps) {
  const [dataKind, setDataKind] = useState<ValueChangeDataKind>('value')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [dataType, setDataType] = useState<DataType>('multiple_jobs')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { handleLegendClick, isHidden } = useHiddenSeries<'multiple_jobs' | 'parttime_econ' | 'multiple_jobs_change' | 'parttime_econ_change'>()

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    value: 'default',
    change: 3,
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

  // テーブル用データ（共通フックを使用）
  const changeTableData = useMultiValueMonthlyTableData(
    chartData,
    {
      multiple_jobs: (item) => item.multiple_jobs_change,
      parttime_econ: (item) => item.parttime_econ_change,
    },
    10
  )

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
    if (dataKind === 'value') {
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
                  {/* データ種別切り替え */}
                  <ViewModeButtonGroup options={VALUE_CHANGE_DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />

                  {/* 表示形式切り替え（増減幅のときのみ） */}
                  {dataKind === 'change' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 現数値グラフ（左右Y軸） */}
                  {dataKind === 'value' && (
                    <>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                        <AntTooltip title="比較ページを開く">
                          <Button
                            icon={<AreaChartOutlined />}
                            onClick={() => window.open('/compare?s=multiple_jobs', '_blank')}
                          >
                            データ比較
                          </Button>
                        </AntTooltip>
                      </div>
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
                          <Tooltip content={<ValueTooltip unit="k" />} />
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
                  {dataKind === 'change' && displayMode === 'chart' && (
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
                          <Tooltip content={<ChangeTooltip unit="k" formatValue={(v) => v.toLocaleString()} />} />
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
                  {dataKind === 'change' && displayMode === 'heatmap' && (
                    <MonthlyTableWithDataTypes
                      data={changeTableData}
                      dataTypes={DATA_TYPE_OPTIONS}
                      selectedType={dataType}
                      onTypeChange={setDataType}
                      helperText="※ 直近10年間の前月増減幅データ（単位: 千人）"
                      formatValue={(value) => {
                        if (value === null) return '-'
                        return `${value >= 0 ? '+' : ''}${value.toLocaleString()}`
                      }}
                      getCellBgColor={getChangeCellColor100k}
                      legendItems={CHANGE_LEGEND_100K}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="multiple_jobs" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
