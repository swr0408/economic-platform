import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { Line } from 'recharts'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { NFIBPricePlansData } from '../../../../hooks/useDashboardData'

import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../common/chartConstants'
import { usePeriodFiltering, formatDateLabel, type PeriodType } from '../common/useChartData'
import { NoDataMessage } from '../common/ChartComponents'

import MarketImpactTab from '../../../indicator/MarketImpactTab'

interface NFIBPricePlansChartProps {
  data: NFIBPricePlansData | null
}

interface ChartDataPoint {
  date: string
  value: number
  price3MA: number | null
  [key: string]: string | number | null | undefined
}

const calculate3MA = (data: ChartDataPoint[]): ChartDataPoint[] => {
  return data.map((point, index) => {
    if (index < 2) {
      return {
        ...point,
        price3MA: null,
      }
    }
    const price3MA = (data[index - 2].value + data[index - 1].value + point.value) / 3
    return {
      ...point,
      price3MA,
    }
  })
}

export default function NFIBPricePlansChart({ data }: NFIBPricePlansChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    const sorted = [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        value: item.value,
        price3MA: null as number | null,
      }))

    return calculate3MA(sorted)
  }, [data])

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: new Date().getFullYear() - 5,
  })

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="NFIB中小企業価格引き上げ計画" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="NFIB中小企業価格引き上げ計画" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const formatValue = (value: number) => {
    return value.toFixed(1)
  }

  const RAW_COLOR = '#fdba74'
  const MA_COLOR = '#ea580c'

  return (
    <div id="nfib-price-plans">
      <ChartContainer
        title="NFIB中小企業価格引き上げ計画"
        showPeriodSelector={false}
        dataSource="NFIB"
        sourceUrl="https://www.nfib.com/surveys/small-business-economic-trends/"
      >
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>最新値: </span>
            {data.latest && (
              <>
                <span
                  style={{
                    fontSize: 20,
                    fontWeight: 'bold',
                    color: MA_COLOR,
                  }}
                >
                  {formatValue(data.latest.value)}%
                </span>
                <span style={{ fontSize: 12, color: TEXT_COLORS.tertiary, marginLeft: 8 }}>
                  ({formatDateLabel(data.latest.date)})
                </span>
              </>
            )}
          </div>
          <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, textAlign: 'right' }}>
            {data.next_release && <div>次回発表: {data.next_release.date}</div>}
            <div>毎月第2火曜日発表</div>
          </div>
        </div>

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
                        onClick={() => window.open('/compare?s=nfib_price_plans', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <ZoomableChart
                    data={filteredData}
                    dataKey="value"
                    color={RAW_COLOR}
                    name="価格引き上げ計画"
                    height={450}
                    tickFormatter={formatValue}
                    tooltipFormatter={formatValue}
                    tooltipLabelFormatter={formatDateLabel}
                    xAxisTickFormatter={formatDateLabel}
                    enableDynamicTicks={true}
                    showZeroLine={false}
                    showFiftyLine={false}
                    connectNulls={true}
                    hideLegend={false}
                    strokeWidth={1.5}
                  >
                    <Line
                      type="monotone"
                      dataKey="price3MA"
                      stroke={MA_COLOR}
                      name="価格引き上げ計画(3か月平均)"
                      dot={false}
                      strokeWidth={2}
                      yAxisId="left"
                      isAnimationActive={false}
                    />
                  </ZoomableChart>
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
