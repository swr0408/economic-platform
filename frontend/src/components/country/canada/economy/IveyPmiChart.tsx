/**
 * カナダ Ivey PMI チャートコンポーネント
 *
 * Ivey Business School の購買担当者景気指数（季節調整済）を表示
 *
 * データソース:
 * - Ivey Business School / FMP / DB蓄積
 *
 * 発表スケジュール:
 * - 毎月上旬
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

import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { CaIveyPmiData } from '../../../../hooks/useDashboardData'

interface IveyPmiChartProps {
  data: CaIveyPmiData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

const COLORS = {
  pmi: '#1890ff',
}

type ViewMode = 'chart'

export default function IveyPmiChart({ data }: IveyPmiChartProps) {
  const [viewMode] = useState<ViewMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    chart: 10,
  })

  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((item) => ({
      date: item.date,
      value: item.value,
    }))
  }, [data])

  const chartData = useSortedData(rawChartData)

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0

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
    return <LoadingChart title="Ivey PMI" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="Ivey PMI" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ivey-pmi-chart">
      <ChartContainer
        title="Ivey PMI"
        showPeriodSelector={false}
        dataSource="Ivey Business School"
        sourceUrl="https://iveypmi.uwo.ca/"
      >
        <SimpleLatestValueBox
          label="Ivey PMI（季節調整済）"
          value={latestValue?.value}
          date={latestValue?.date}
          format="number"
          decimals={1}
          valueColor={COLORS.pmi}
          nextRelease={data.next_release ? {
            date: data.next_release.date,
            label: data.next_release.time_jst ? `${data.next_release.time_jst} JST` : undefined
          } : null}
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
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=ca_ivey_pmi', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: COLORS.pmi, name: 'Ivey PMI' },
                    ]}
                    yAxisFormatter={(v) => `${v}`}
                    tooltipValueFormatter={(v) => `${v.toFixed(1)}`}
                    yDomain={['dataMin - 2', 'dataMax + 2']}
                    showZeroLine={false}
                    showFiftyLine={true}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ca_iveypmi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
