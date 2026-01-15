/**
 * ドイツ失業率チャートコンポーネント
 *
 * Deutsche Bundesbank APIからドイツ失業率データを取得し、表示
 *
 * データ:
 * - Unemployment Rate (季節調整済み)
 *
 * データソース:
 * - Deutsche Bundesbank
 *
 * 発表スケジュール:
 * - 毎月27日〜翌月6日 17:55-18:05 CET
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

import type { GermanyUnemploymentData } from '../../../../hooks/useDashboardData'

interface GermanyUnemploymentChartProps {
  data: GermanyUnemploymentData | null
}

interface ChartDataPoint {
  date: string
  value: number
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  value: '#ff6b6b',
}

export default function GermanyUnemploymentChart({ data }: GermanyUnemploymentChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<number | 'all' | 'default'>('default')

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data || !data.unemployment_rate) return []

    return data.unemployment_rate
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
    return <LoadingChart title="失業率（ドイツ）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="失業率（ドイツ）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="germany-unemployment-chart">
      <ChartContainer
        title="失業率（ドイツ）"
        showPeriodSelector={false}
        dataSource="Deutsche Bundesbank"
        sourceUrl="https://www.destatis.de/SiteGlobals/Forms/Suche/Presse/DE/Pressesuche_Formular_2.html?templateQueryString=Erwerbst%C3%A4tigkeit&cl2Taxonomies_Themen_0=arbeitsmarkt#searchresults"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={latest?.value}
          valueColor={COLORS.value}
          date={latest?.date}
          nextRelease={data.next_release}
          format="percent"
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
                        onClick={() => window.open('/compare?s=germany_unemployment', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* チャート表示 */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: COLORS.value, name: '失業率' },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    yDomain={['dataMin - 0.1', 'dataMax + 0.1']}
                    showZeroLine={false}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="germany_unemployment" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
