/**
 * ECB HICP 内訳チャートコンポーネント
 *
 * ECB Data APIからユーロ圏消費者物価調和指数(HICP)内訳データを取得し、表示
 *
 * データ:
 * - 商品 (Goods)
 * - 食品 (Food)
 * - エネルギー (Energy)
 * - サービス (Services)
 *
 * データソース:
 * - European Central Bank (ECB)
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
  LatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { ECBHICPData } from '../../../../hooks/useDashboardData'

interface ECBHICPBreakdownChartProps {
  data: ECBHICPData | null
}

interface ChartDataPoint {
  date: string
  goods: number | null
  food: number | null
  energy: number | null
  services: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  goods: '#1890ff',
  food: '#52c41a',
  energy: '#ff7875',
  services: '#faad14',
}

export default function ECBHICPBreakdownChart({ data }: ECBHICPBreakdownChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<number | 'all' | 'default'>(10)

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data || !data.breakdown_annual_rates) return []

    const goodsData = data.breakdown_annual_rates.goods || []
    const foodData = data.breakdown_annual_rates.food || []
    const energyData = data.breakdown_annual_rates.energy || []
    const servicesData = data.breakdown_annual_rates.services || []

    // 日付をキーにしたマップを作成
    const dateMap = new Map<string, ChartDataPoint>()

    goodsData.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, {
          date: point.date,
          goods: null,
          food: null,
          energy: null,
          services: null,
        })
      }
      dateMap.get(point.date)!.goods = point.value
    })

    foodData.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, {
          date: point.date,
          goods: null,
          food: null,
          energy: null,
          services: null,
        })
      }
      dateMap.get(point.date)!.food = point.value
    })

    energyData.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, {
          date: point.date,
          goods: null,
          food: null,
          energy: null,
          services: null,
        })
      }
      dateMap.get(point.date)!.energy = point.value
    })

    servicesData.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, {
          date: point.date,
          goods: null,
          food: null,
          energy: null,
          services: null,
        })
      }
      dateMap.get(point.date)!.services = point.value
    })

    return Array.from(dateMap.values())
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
    return <LoadingChart title="HICP内訳（ユーロ圏・前年比）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="HICP内訳（ユーロ圏・前年比）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ecb-hicp-breakdown-chart">
      <ChartContainer
        title="HICP 項目別（ユーロ圏・前年比）"
        showPeriodSelector={false}
        dataSource="European Central Bank (ECB)"
        sourceUrl="https://ec.europa.eu/eurostat/en/web/main/news/euro-indicators?p_p_id=estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageNumber=1&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_action=search&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageSize=11&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_text=Unemployment&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_collection=CAT_PREREL&p_auth=ZIoPsCO4&text=inflation"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '商品',
              value: latest?.goods,
              color: COLORS.goods,
              format: 'percent',
            },
            {
              label: '食品',
              value: latest?.food,
              color: COLORS.food,
              format: 'percent',
            },
            {
              label: 'エネルギー',
              value: latest?.energy,
              color: COLORS.energy,
              format: 'percent',
            },
            {
              label: 'サービス',
              value: latest?.services,
              color: COLORS.services,
              format: 'percent',
            },
          ]}
          date={latest?.date}
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
                    <Tooltip title="比較ページを開く（HICP内訳）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=eurozone_hicp_goods&s=eurozone_hicp_services&s=eurozone_hicp_energy', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* チャート表示（エネルギーは右Y軸） */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'goods', color: COLORS.goods, name: '商品', yAxisId: 'left' },
                      { dataKey: 'food', color: COLORS.food, name: '食品', yAxisId: 'left' },
                      { dataKey: 'services', color: COLORS.services, name: 'サービス', yAxisId: 'left' },
                      { dataKey: 'energy', color: COLORS.energy, name: 'エネルギー（右軸）', yAxisId: 'right' },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    yDomain={['dataMin - 1', 'dataMax + 1']}
                    showZeroLine={true}
                    showRightYAxis={true}
                    rightYAxisFormatter={(v) => `${v}%`}
                    rightYDomain={['dataMin - 5', 'dataMax + 5']}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ecb_hicp" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
