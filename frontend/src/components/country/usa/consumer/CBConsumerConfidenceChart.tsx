/**
 * CB消費者信頼感指数チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { CBConsumerConfidenceData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { CHART_COLORS } from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabelJP,
  createNumberFormatter,
  type PeriodType,
} from '../common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../common/ChartComponents'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// =============================================================================
// 型定義
// =============================================================================

interface CBConsumerConfidenceChartProps {
  data: CBConsumerConfidenceData | null
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CBConsumerConfidenceChart({ data }: CBConsumerConfidenceChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // データを日付昇順にソート
  const chartData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="CB消費者信頼感指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="CB消費者信頼感指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="cb-consumer-confidence">
      <ChartContainer
        title="CB消費者信頼感指数"
        showPeriodSelector={false}
        dataSource="ConferenceBoard"
        sourceUrl="https://www.conference-board.org/topics/consumer-confidence/"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={latest?.value}
          valueColor={CHART_COLORS.primary}
          date={latest?.date}
          format="number"
          decimals={1}
          dateFormatter={formatDateLabelJP}
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=cb_consumer_confidence', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: CHART_COLORS.primary, name: 'CB消費者信頼感指数' },
                    ]}
                    yDomain={['dataMin - 5', 'dataMax + 5']}
                    tooltipLabelFormatter={formatDateLabelJP}
                    tooltipFormatter={createNumberFormatter(1)}
                    showZeroLine={false}
                    showLegend={false}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="cb_consumer_confidence" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
