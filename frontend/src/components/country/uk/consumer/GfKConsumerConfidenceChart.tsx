/**
 * UK GfK消費者信頼感指数チャートコンポーネント
 *
 * データ:
 * - GfK Consumer Confidence（原数値）
 *
 * データソース:
 * - GfK / YouGov
 *
 * 発表スケジュール:
 * - 毎月13日〜翌月8日
 * - 8:01-9:11 ロンドン時間
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

import type { GfKConsumerConfidenceData } from '../../../../hooks/useDashboardData'
import type { PeriodType } from '../../usa/common/useChartData'

interface GfKConsumerConfidenceChartProps {
  data: GfKConsumerConfidenceData | null
}

interface ChartDataPoint {
  date: string
  value: number
  [key: string]: unknown
}

// グラフの色
const CHART_COLOR = '#9b59b6'

export default function GfKConsumerConfidenceChart({ data }: GfKConsumerConfidenceChartProps) {
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
    window.open('/compare?s=uk_gfk_consumer_confidence&s=uk_brc_retail_sales_yoy', '_blank')
  }, [])

  if (data === null) {
    return <LoadingChart title="GfK消費者信頼感指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="GfK消費者信頼感指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="uk-gfk-consumer-confidence-chart">
      <ChartContainer
        title="GfK消費者信頼感指数"
        showPeriodSelector={false}
        dataSource="NIQ"
        sourceUrl="https://nielseniq.com/?s=%E2%80%8B%E2%80%8BConsumer%2Bconfidence&market=global&language=en&orderby&order&date_range&date&post_type=news_center&topics&industries&roles&brand_architecture&formats&insight_categories"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={latest?.value}
          valueColor={CHART_COLOR}
          date={latest?.date}
          nextRelease={data.next_release}
          format="number"
          decimals={0}
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
                        name: 'GfK消費者信頼感指数',
                        hide: hiddenSeries.has('value')
                      },
                    ]}
                    yAxisFormatter={(v) => `${v}`}
                    tooltipValueFormatter={(v) => `${v.toFixed(0)}`}
                    onLegendClick={handleLegendClick}
                    yDomain={['dataMin - 5', 'dataMax + 5']}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="uk_gfk_consumer_confidence" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
