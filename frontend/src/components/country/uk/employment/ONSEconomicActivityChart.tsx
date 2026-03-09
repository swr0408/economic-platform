/**
 * UK ONS経済活動率チャートコンポーネント
 *
 * データ:
 * - LF22: Economic Activity Rate (16-64歳、季節調整済)
 *
 * データソース:
 * - ONS (Office for National Statistics)
 *
 * 発表スケジュール:
 * - 失業率と同じスケジュール（FMPカレンダー）
 */
import { useState, useMemo, useCallback } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { ONSEconomicActivityData } from '../../../../hooks/useDashboardData'
import type { PeriodType } from '../../usa/common/useChartData'

interface ONSEconomicActivityChartProps {
  data: ONSEconomicActivityData | null
}

interface ChartDataPoint {
  date: string
  value: number
  [key: string]: unknown
}

// グラフの色
const CHART_COLOR = '#22c55e'

export default function ONSEconomicActivityChart({ data }: ONSEconomicActivityChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter(point => point.value !== null)
      .map(point => ({
        date: point.date,
        value: point.value as number,
      }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  // 期間変更ハンドラ
  const handlePeriodChange = useCallback((period: PeriodType) => {
    setSelectedPeriod(period)
  }, [])

  // データ比較ページを開く
  const handleCompare = useCallback(() => {
    window.open('/compare?s=uk_economic_activity&s=uk_unemployment_rate', '_blank')
  }, [])

  if (data === null) {
    return <LoadingChart title="ONS経済活動率" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="ONS経済活動率" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="uk-ons-economic-activity-chart">
      <ChartContainer
        title="経済活動率"
        showPeriodSelector={false}
        dataSource="ONS"
        sourceUrl="https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={latest?.value}
          valueColor={CHART_COLOR}
          date={latest?.date}
          nextRelease={data.next_release}
          format="percent"
          decimals={1}
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
                  {/* 期間セレクター */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={handlePeriodChange} selectedPeriod={selectedPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={handleCompare}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* チャート表示 */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      {
                        dataKey: 'value',
                        color: CHART_COLOR,
                        name: '経済活動率',
                        hide: hiddenSeries.has('value')
                      },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
                    onLegendClick={handleLegendClick}
                    yDomain={['dataMin - 0.3', 'dataMax + 0.3']}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ons_economic_activity" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
