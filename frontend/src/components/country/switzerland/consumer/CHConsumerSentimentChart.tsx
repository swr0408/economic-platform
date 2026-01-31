/**
 * SECO消費者景況感 チャートコンポーネント
 *
 * SECOから消費者景況感データを取得し、表示
 *
 * データ:
 * - Consumer Climate（消費者景況感指数）
 *
 * データソース:
 * - SECO (State Secretariat for Economic Affairs)
 *
 * 発表スケジュール:
 * - 不定期（FMPカレンダーから取得）
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
  useViewModePeriodManagement,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { CHConsumerSentimentData } from '../../../../hooks/useDashboardData'

interface CHConsumerSentimentChartProps {
  data: CHConsumerSentimentData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  sentiment: '#DC143C', // スイス赤
}

export default function CHConsumerSentimentChart({ data }: CHConsumerSentimentChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement('default', {
    default: 'default',
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((item) => ({
      date: item.date,
      value: item.value,
    }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = useMemo(() => {
    if (!chartData.length) return null
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].value !== null) {
        return chartData[i]
      }
    }
    return null
  }, [chartData])

  if (data === null) {
    return <LoadingChart title="SECO消費者景況感" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="SECO消費者景況感" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ch-consumer-sentiment-chart">
      <ChartContainer
        title="SECO消費者景況感"
        showPeriodSelector={false}
        dataSource="SECO (State Secretariat for Economic Affairs)"
        sourceUrl="https://www.seco.admin.ch/seco/en/home/wirtschaftslage---wirtschaftspolitik/Wirtschaftslage/Konsumentenstimmung.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="SECO消費者景況感"
          value={latestValue?.value}
          date={latestValue?.date}
          format="number"
          decimals={1}
          valueColor={COLORS.sentiment}
          nextRelease={data.next_release}
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
                  {/* コントロールバー */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
                    <Tooltip title="比較ページを開く（SECO消費者景況感）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=ch_consumer_sentiment', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 期間選択 */}
                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                  {/* グラフ */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: COLORS.sentiment, name: 'SECO消費者景況感' },
                    ]}
                    yAxisFormatter={(v) => `${v}`}
                    tooltipValueFormatter={(v) => `${v.toFixed(1)}`}
                    yDomain={['dataMin - 5', 'dataMax + 5']}
                    showZeroLine={true}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ch_consumer_sentiment" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
