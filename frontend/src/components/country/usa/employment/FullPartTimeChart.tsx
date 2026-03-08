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
import type { FullPartTimeEmploymentData } from '../../../../hooks/useDashboardData'

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
  CHANGE_LEGEND_200K,
  getChangeCellColor200k,
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

interface FullPartTimeChartProps {
  data: FullPartTimeEmploymentData | null
}

type DataType = 'fulltime' | 'parttime'

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


// =============================================================================
// メインコンポーネント
// =============================================================================

export default function FullPartTimeChart({ data }: FullPartTimeChartProps) {
  const [dataKind, setDataKind] = useState<ValueChangeDataKind>('value')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [dataType, setDataType] = useState<DataType>('fulltime')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { handleLegendClick, isHidden } = useHiddenSeries<'fulltime' | 'parttime' | 'fulltime_change' | 'parttime_change'>()

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

  // テーブル用データ（共通フックを使用）
  const changeTableData = useMultiValueMonthlyTableData(
    chartData,
    {
      fulltime: (item) => item.fulltime_change,
      parttime: (item) => item.parttime_change,
    },
    10
  )

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
    if (dataKind === 'value') {
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
                            onClick={() => window.open('/compare?s=fulltime_employment', '_blank')}
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
                          <Tooltip content={<ValueTooltip unit="k" />} />
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
                            domain={['dataMin - 100', 'dataMax + 100']}
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
                      getCellBgColor={getChangeCellColor200k}
                      legendItems={CHANGE_LEGEND_200K}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="fulltime_employment" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
