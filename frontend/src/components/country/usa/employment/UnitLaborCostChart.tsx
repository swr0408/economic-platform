/**
 * 単位労働コスト / 労働生産性チャートコンポーネント
 *
 * FRED データを使用:
 * - PRS85006112: 単位労働コスト（前期比）
 * - PRS85006092: 労働生産性（前期比）
 *
 * 表示モード:
 * - 前期比テーブル（タブ切り替え）
 * - 前期比グラフ（両方棒グラフ）
 *
 * 四半期ごと発表（2月、3月、5月、6月、8月、9月、11月、12月）8:30 ET
 *
 * 共通コンポーネントを使用
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip as AntTooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import MarketImpactTab from '../../../indicator/MarketImpactTab'
import {
  BarChart,
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
import type { UnitLaborCostData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  CHANGE_LEGEND_10PCT,
  getChangeCellColor10pct,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  formatQuarterLabel,
  formatQuarterLabelJP,
  useHiddenSeries,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  ViewModeButtonGroup,
  ChangeTooltip,
} from '../common/ChartComponents'
import { QuarterlyTableWithDataTypes } from '../common/QuarterlyTable'

// =============================================================================
// 型定義
// =============================================================================

interface UnitLaborCostChartProps {
  data: UnitLaborCostData | null
}

type TableType = 'ulc' | 'productivity'

// 表示形式
type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// カラー設定
const COLORS = {
  ulc: '#ff4d4f',         // 単位労働コスト - 赤
  productivity: '#1890ff', // 労働生産性 - 青
}

// 系列名（日本語）
const SERIES_NAMES = {
  ulc: '単位労働コスト',
  productivity: '労働生産性',
}


// データタイプ設定（共通コンポーネント用）
const DATA_TYPE_OPTIONS = [
  { type: 'ulc' as const, label: '単位労働コスト', color: COLORS.ulc, bgColor: '#fff1f0' },
  { type: 'productivity' as const, label: '労働生産性', color: COLORS.productivity, bgColor: '#e6f7ff' },
]

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function UnitLaborCostChart({ data }: UnitLaborCostChartProps) {
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [tableType, setTableType] = useState<TableType>('ulc')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // 期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(displayMode, {
    chart: 20,
    heatmap: 20,
  })

  // データのソート
  const sortedData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // 四半期テーブルデータの生成
  const tableData = useMemo(() => {
    if (sortedData.length === 0) return { years: [], quarterlyData: {} }

    const currentYear = new Date().getFullYear()
    const startYear = currentYear - 9

    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) {
      years.push(y)
    }

    const quarterlyData: Record<number, Record<number, { ulc: number | null; productivity: number | null }>> = {}

    sortedData.forEach((item) => {
      const date = new Date(item.date)
      const year = date.getFullYear()
      const quarter = Math.floor(date.getMonth() / 3)

      if (year >= startYear && year <= currentYear) {
        if (!quarterlyData[year]) {
          quarterlyData[year] = {}
        }
        quarterlyData[year][quarter] = {
          ulc: item.ulc_pch ?? null,
          productivity: item.productivity_pch ?? null,
        }
      }
    })

    return { years, quarterlyData }
  }, [sortedData])

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="単位労働コスト / 労働生産性" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="単位労働コスト / 労働生産性" showPeriodSelector={false} showDataSource={false}>
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
        label: SERIES_NAMES.ulc,
        value: latest.ulc_pch !== null ? `${latest.ulc_pch >= 0 ? '+' : ''}${latest.ulc_pch.toFixed(1)}%` : 'N/A',
        color: latest.ulc_pch !== null && latest.ulc_pch >= 0 ? CHART_COLORS.negative : CHART_COLORS.positive,
      },
      {
        label: SERIES_NAMES.productivity,
        value: latest.productivity_pch !== null ? `${latest.productivity_pch >= 0 ? '+' : ''}${latest.productivity_pch.toFixed(1)}%` : 'N/A',
        color: latest.productivity_pch !== null && latest.productivity_pch >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative,
      },
    ]
  }

  return (
    <div id="unit-labor-cost">
      <ChartContainer
        title="単位労働コスト / 労働生産性"
        showPeriodSelector={false}
        dataSource="FRED - BLS"
        sourceUrl="https://www.bls.gov/news.release/prod2.toc.htm"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latest?.date}
          nextRelease={nextRelease}
          dateFormatter={formatQuarterLabel}
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
                  {/* 表示形式 */}
                  <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />

                  {/* 前期比グラフ（両方棒グラフ） */}
                  {displayMode === 'chart' && (
                    <>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                        <AntTooltip title="比較ページを開く">
                          <Button
                            icon={<AreaChartOutlined />}
                            onClick={() => window.open('/compare?s=unit_labor_cost', '_blank')}
                          >
                            データ比較
                          </Button>
                        </AntTooltip>
                      </div>
                      <ResponsiveContainer width="100%" height={450}>
                        <BarChart data={filteredData} margin={CHART_MARGIN} barCategoryGap="20%">
                          <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                          <XAxis
                            dataKey="date"
                            tickFormatter={formatQuarterLabel}
                            tick={AXIS_STYLE.tick}
                            interval={AXIS_STYLE.interval}
                          />
                          <YAxis
                            tick={AXIS_STYLE.tick}
                            tickFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}`}
                            domain={['dataMin - 1', 'dataMax + 1']}
                            label={{
                              angle: -90,
                              position: 'insideLeft',
                              dy: 20,
                              style: { fontSize: 11, fill: '#666' }
                            }}
                          />
                          <Tooltip content={<ChangeTooltip unit="%" decimals={1} labelFormatter={formatQuarterLabelJP} />} />
                          <Legend onClick={(e) => handleLegendClick(e.dataKey as string)} />
                          <ReferenceLine y={0} stroke="#000" strokeWidth={1} />

                          <Bar
                            dataKey="ulc_pch"
                            fill={COLORS.ulc}
                            name={SERIES_NAMES.ulc}
                            hide={hiddenSeries.has('ulc_pch')}
                          />
                          <Bar
                            dataKey="productivity_pch"
                            fill={COLORS.productivity}
                            name={SERIES_NAMES.productivity}
                            hide={hiddenSeries.has('productivity_pch')}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </>
                  )}

                  {/* 前期比ヒートマップ（タブ切り替え） */}
                  {displayMode === 'heatmap' && (
                    <QuarterlyTableWithDataTypes
                      data={tableData}
                      dataTypes={DATA_TYPE_OPTIONS}
                      selectedType={tableType}
                      onTypeChange={setTableType}
                      getCellBgColor={getChangeCellColor10pct}
                      legendItems={CHANGE_LEGEND_10PCT}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="unit_labor_cost" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
