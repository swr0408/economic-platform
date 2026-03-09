/**
 * Eurostat消費者信頼感指数チャートコンポーネント
 *
 * Eurostat APIからユーロ圏消費者信頼感指数データを取得し、表示
 *
 * データ:
 * - Consumer Confidence Indicator (EA20, Seasonally Adjusted)
 *
 * データソース:
 * - Eurostat - Business and Consumer Surveys
 *
 * 発表スケジュール:
 * - 毎月25日〜翌月8日 18:00-18:10 CET
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { EurostatConsumerConfidenceData } from '../../../../hooks/useDashboardData'

interface EurostatConsumerConfidenceChartProps {
  data: EurostatConsumerConfidenceData | null
}

interface ChartDataPoint {
  date: string
  value: number
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  value: '#1890ff',
}

export default function EurostatConsumerConfidenceChart({ data }: EurostatConsumerConfidenceChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<number | 'all' | 'default'>(10)

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data || !data.data) return []

    return data.data
      .filter(point => point.value !== null)
      .map(point => ({
        date: point.date,
        value: point.value,
      }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  if (data === null) {
    return <LoadingChart title="消費者信頼感指数（ユーロ圏）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="消費者信頼感指数（ユーロ圏）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="eurostat-consumer-confidence-chart">
      <ChartContainer
        title="消費者信頼感指数（ユーロ圏）"
        showPeriodSelector={false}
        dataSource="Eurostat"
        sourceUrl="https://economy-finance.ec.europa.eu/economic-forecast-and-surveys/business-and-consumer-surveys/latest-business-and-consumer-surveys_en"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={latest?.value}
          valueColor={COLORS.value}
          date={latest?.date}
          nextRelease={data.next_release}
          format="number"
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
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=eurostat_consumer_confidence', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* チャート表示 */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: COLORS.value, name: '消費者信頼感指数' },
                    ]}
                    yAxisFormatter={(v) => `${v}`}
                    showZeroLine={true}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="eurostat_consumer_confidence" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
