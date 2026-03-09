import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { NFIBData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../common/chartConstants'
import { usePeriodFiltering, formatDateLabel, type PeriodType } from '../common/useChartData'
import { NoDataMessage } from '../common/ChartComponents'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

interface NFIBOptimismChartProps {
  data: NFIBData | null
}

export default function NFIBOptimismChart({ data }: NFIBOptimismChartProps) {
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
    return <LoadingChart title="NFIB中小企業楽観指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="NFIB中小企業楽観指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const formatValue = (value: number) => {
    return value.toFixed(1)
  }

  // グラフの色
  const CHART_COLOR = '#722ed1'

  return (
    <div id="nfib-chart">
      <ChartContainer
        title="NFIB中小企業楽観指数"
        showPeriodSelector={false}
        dataSource="NFIB"
        sourceUrl="https://www.nfib.com/surveys/small-business-economic-trends/"
      >
        {/* 最新値表示 */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>最新値: </span>
            {data.latest && (
              <>
                <span
                  style={{
                    fontSize: 20,
                    fontWeight: 'bold',
                    color: CHART_COLOR,
                  }}
                >
                  {formatValue(data.latest.value)}
                </span>
                <span style={{ fontSize: 12, color: TEXT_COLORS.tertiary, marginLeft: 8 }}>
                  ({formatDateLabel(data.latest.date)})
                </span>
              </>
            )}
          </div>
          <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, textAlign: 'right' }}>
            {data.next_release && (
              <div>次回発表: {data.next_release.date}</div>
            )}
            <div>毎月第2火曜日発表</div>
          </div>
        </div>

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
                        onClick={() => window.open('/compare?s=nfib', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <ZoomableChart
                    data={filteredData}
                    dataKey="value"
                    color={CHART_COLOR}
                    name="NFIB楽観指数"
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
                <MarketImpactTab indicatorId="nfib" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
