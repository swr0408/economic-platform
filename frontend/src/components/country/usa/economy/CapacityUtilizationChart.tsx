import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { CapacityUtilizationData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { usePeriodFiltering, formatDateLabel, type PeriodType } from '../common/useChartData'
import { NoDataMessage, SimpleLatestValueBox } from '../common/ChartComponents'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

interface CapacityUtilizationChartProps {
  data: CapacityUtilizationData | null
}

export default function CapacityUtilizationChart({ data }: CapacityUtilizationChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    )
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="設備稼働率（Capacity Utilization）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="設備稼働率（Capacity Utilization）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値
  const latest = data.latest

  const formatValue = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'N/A'
    return `${value.toFixed(1)}%`
  }

  return (
    <div id="capacity-utilization-chart">
      <ChartContainer
        title="設備稼働率"
        showPeriodSelector={false}
        dataSource="FRED (FRB)"
        sourceUrl="https://www.federalreserve.gov/releases/G17/default.htm"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={latest?.value}
          valueColor="#1890ff"
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=capacity_utilization', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <ZoomableChart
                    data={filteredData}
                    dataKey="value"
                    color="#1890ff"
                    name="設備稼働率"
                    height={450}
                    tickFormatter={formatValue}
                    tooltipFormatter={formatValue}
                    tooltipLabelFormatter={formatDateLabel}
                    xAxisTickFormatter={formatDateLabel}
                    enableDynamicTicks={true}
                    showZeroLine={false}
                    showFiftyLine={false}
                    connectNulls={true}
                    hideLegend={true}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="capacity_utilization" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
