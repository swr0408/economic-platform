/**
 * ドイツGfK消費者信頼感指数チャートコンポーネント
 *
 * GfK消費者信頼感指数（翌月予測）データを表示
 *
 * データ:
 * - GfK Consumer Confidence Index (翌月予測)
 *
 * データソース:
 * - GfK (Gesellschaft für Konsumforschung)
 *
 * 発表スケジュール:
 * - 毎月下旬（不定期）
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

import type { GermanyConsumerConfidenceGfKData } from '../../../../hooks/useDashboardData'

interface GermanyConsumerConfidenceGfKChartProps {
  data: GermanyConsumerConfidenceGfKData | null
}

interface ChartDataPoint {
  date: string
  value: number
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  value: '#faad14', // 金色（ドイツを象徴）
}

export default function GermanyConsumerConfidenceGfKChart({ data }: GermanyConsumerConfidenceGfKChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<number | 'all' | 'default'>('default')

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
    return <LoadingChart title="消費者信頼感指数（ドイツ・GfK）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="消費者信頼感指数（ドイツ・GfK）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="germany-consumer-confidence-gfk-chart">
      <ChartContainer
        title="消費者信頼感指数（ドイツ・GfK）"
        showPeriodSelector={false}
        dataSource="GfK"
        sourceUrl="https://nielseniq.com/?s=Konsumklima&market=global&language=de&orderby=date&order=DESC&date_range&date&post_type=news_center&topics&industries&roles&brand_architecture&formats&insight_categories"
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
                        onClick={() => window.open('/compare?s=germany_consumer_confidence_gfk&s=eurostat_consumer_confidence', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* チャート表示 */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: COLORS.value, name: 'GfK消費者信頼感指数' },
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
                <MarketImpactTab indicatorId="germany_consumer_confidence_gfk" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
