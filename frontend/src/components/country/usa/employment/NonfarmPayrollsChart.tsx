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
import { Tabs, Button, Tooltip as AntTooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import MarketImpactTab from '../../../indicator/MarketImpactTab'
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
  ChangeTooltip,
} from '../common/ChartComponents'
import { MonthlyTableWithDataTypes } from '../common/MonthlyTable'

// =============================================================================
// 型定義
// =============================================================================

interface NonfarmPayrollsChartProps {
  data: NonfarmPayrollsData | null
}

type DataType = 'nonfarm' | 'civilian'

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

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function NonfarmPayrollsChart({ data }: NonfarmPayrollsChartProps) {
  const [dataKind, setDataKind] = useState<ValueChangeDataKind>('value')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [dataType, setDataType] = useState<DataType>('nonfarm')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { handleLegendClick, isHidden } = useHiddenSeries<'nonfarm' | 'civilian' | 'nonfarm_change' | 'civilian_change'>()

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    value: 10,
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

  // テーブル用データ（共通フックを使用）
  const changeTableData = useMultiValueMonthlyTableData(
    chartData,
    {
      nonfarm: (item) => item.nonfarm_change,
      civilian: (item) => item.civilian_change,
    },
    10
  )

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
    if (dataKind === 'value') {
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

                  {/* 現数値グラフ */}
                  {dataKind === 'value' && (
                    <>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                        <AntTooltip title="比較ページを開く">
                          <Button
                            icon={<AreaChartOutlined />}
                            onClick={() => window.open('/compare?s=nonfarm_payrolls', '_blank')}
                          >
                            データ比較
                          </Button>
                        </AntTooltip>
                      </div>
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
                <MarketImpactTab indicatorId="nonfarm_payrolls" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
