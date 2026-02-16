/**
 * カナダ小売売上高チャートコンポーネント
 *
 * 小売売上高（前月比・前年比）の推移を表示
 * 系列: 総合, 除く自動車, 除く自動車+ガソリン
 *
 * データソース:
 * - Statistics Canada Table 20-10-0067-01
 *
 * 発表スケジュール:
 * - 月次（対象月の約2ヶ月後）
 * - 発表時刻: 08:30 ET
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// 共通モジュールのインポート
import {
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMultiValueMonthlyTableData,
  useHiddenSeries,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  ViewModeButtonGroup,
  DataTypeButtonGroup,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTableWithDataTypes } from '../../usa/common/MonthlyTable'
import { CHART_COLORS } from '../../usa/common/chartConstants'

// 型定義
import type { CaRetailSalesData } from '../../../../hooks/useDashboardData'

interface CanadaRetailSalesChartProps {
  data: CaRetailSalesData | null
}

type ViewMode = 'yoy' | 'mom_table' | 'mom_chart'
type SeriesType = 'total' | 'ex_auto' | 'ex_auto_gas'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'mom_chart', label: '前月比' },
  { mode: 'mom_table', label: '前月比（テーブル）' },
  { mode: 'yoy', label: '前年比' },
]

// 系列設定（テーブル用）
const SERIES_DATA_TYPE_OPTIONS: { type: SeriesType; label: string }[] = [
  { type: 'total', label: '総合' },
  { type: 'ex_auto', label: '除く自動車' },
  { type: 'ex_auto_gas', label: '除く自動車+ガソリン' },
]

// カラー設定
const COLORS = {
  total: CHART_COLORS.positive,
  ex_auto: CHART_COLORS.purple,
  ex_auto_gas: CHART_COLORS.orange,
}

export default function CanadaRetailSalesChart({ data }: CanadaRetailSalesChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('mom_chart')
  const [seriesType, setSeriesType] = useState<SeriesType>('total')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    mom_table: 'default' as PeriodType,
    mom_chart: 3 as PeriodType,
    yoy: 'default' as PeriodType,
  })

  // propsのデータをチャート用に変換
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        // 前年比
        total_yoy: item.total_yoy,
        ex_auto_yoy: item.ex_auto_yoy,
        ex_auto_gas_yoy: item.ex_auto_gas_yoy,
        // 前月比
        total_mom: item.total_mom,
        ex_auto_mom: item.ex_auto_mom,
        ex_auto_gas_mom: item.ex_auto_gas_mom,
      }))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2017,
  })

  // テーブル用データ
  const momTableData = useMultiValueMonthlyTableData(
    chartData,
    {
      total: (item) => item.total_mom,
      ex_auto: (item) => item.ex_auto_mom,
      ex_auto_gas: (item) => item.ex_auto_gas_mom,
    },
    10
  )

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // 速報値を取得（総合前月比のみ）
  const advanceEstimate = data?.advance_estimate

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="小売売上高" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="小売売上高" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // グラフ用のデータキーを取得
  const getDataKey = () => `${seriesType}_${viewMode === 'yoy' ? 'yoy' : 'mom'}`

  // 系列のラベルを取得
  const getSeriesLabel = (series: SeriesType) => {
    switch (series) {
      case 'total': return '総合'
      case 'ex_auto': return '除く自動車'
      case 'ex_auto_gas': return '除く自動車+ガソリン'
    }
  }

  // 最新値の表示内容（前月比モードの場合）
  const getMomLatestItems = () => {
    const items = [
      {
        label: '総合',
        value: latestValue?.total_mom,
        color: COLORS.total,
        format: 'percent' as const,
      },
      {
        label: '除く自動車',
        value: latestValue?.ex_auto_mom,
        color: COLORS.ex_auto,
        format: 'percent' as const,
      },
      {
        label: '除く自動車+ガソリン',
        value: latestValue?.ex_auto_gas_mom,
        color: COLORS.ex_auto_gas,
        format: 'percent' as const,
      },
    ]
    return items
  }

  // 最新値の表示内容（前年比モードの場合）
  const getYoyLatestItems = () => {
    return [
      {
        label: '総合',
        value: latestValue?.total_yoy,
        color: COLORS.total,
        format: 'percent' as const,
      },
      {
        label: '除く自動車',
        value: latestValue?.ex_auto_yoy,
        color: COLORS.ex_auto,
        format: 'percent' as const,
      },
      {
        label: '除く自動車+ガソリン',
        value: latestValue?.ex_auto_gas_yoy,
        color: COLORS.ex_auto_gas,
        format: 'percent' as const,
      },
    ]
  }

  return (
    <div id="ca-retail-sales-chart">
      <ChartContainer
        title="小売売上高"
        showPeriodSelector={false}
        dataSource="Statistics Canada"
        sourceUrl="https://www.statcan.gc.ca/en/subjects-start/retail_and_wholesale"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={viewMode === 'yoy' ? getYoyLatestItems() : getMomLatestItems()}
          date={latestValue?.date}
          nextRelease={data.next_release}
          advanceEstimate={advanceEstimate && viewMode !== 'yoy' ? {
            value: advanceEstimate.total_mom,
            date: advanceEstimate.date,
            label: '総合（速報値）',
          } : undefined}
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=ca_retail_sales_total_mom', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 前年比グラフ（線グラフ） */}
                  {viewMode === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'total_yoy', color: COLORS.total, name: '小売売上高（前年比）', hide: hiddenSeries.has('total_yoy') },
                          { dataKey: 'ex_auto_yoy', color: COLORS.ex_auto, name: '除く自動車（前年比）', hide: hiddenSeries.has('ex_auto_yoy') },
                          { dataKey: 'ex_auto_gas_yoy', color: COLORS.ex_auto_gas, name: '除く自動車+ガソリン（前年比）', hide: hiddenSeries.has('ex_auto_gas_yoy') },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 2', 'dataMax + 2']}
                        showZeroLine={true}
                        onLegendClick={handleLegendClick}
                      />
                    </>
                  )}

                  {/* 前月比テーブル */}
                  {viewMode === 'mom_table' && (
                    <MonthlyTableWithDataTypes
                      data={momTableData}
                      dataTypes={SERIES_DATA_TYPE_OPTIONS}
                      selectedType={seriesType}
                      onTypeChange={setSeriesType}
                    />
                  )}

                  {/* 前月比グラフ（棒グラフ） */}
                  {viewMode === 'mom_chart' && (
                    <>
                      <DataTypeButtonGroup
                        options={SERIES_DATA_TYPE_OPTIONS.map(s => ({ type: s.type, label: s.label }))}
                        currentType={seriesType}
                        onChange={setSeriesType}
                      />
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          {
                            dataKey: getDataKey(),
                            color: COLORS[seriesType],
                            name: `${getSeriesLabel(seriesType)}（前月比）`,
                          },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                      />
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="ca_retail_sales" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
