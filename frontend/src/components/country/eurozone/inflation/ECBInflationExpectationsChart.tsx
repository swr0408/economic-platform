/**
 * ECB Consumer Expectations Survey - インフレ期待チャートコンポーネント
 *
 * ECB Data APIから消費者期待調査（CES）データを取得し、表示
 *
 * データ:
 * - 12ヶ月先インフレ期待（加重中央値）
 * - 3年先インフレ期待（加重中央値）
 * - 5年先インフレ期待（加重中央値）
 *
 * データソース:
 * - European Central Bank (ECB) - Consumer Expectations Survey
 *
 * 発表スケジュール:
 * - 毎月発表（不定期）
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
  LatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import type { ECBInflationExpectationsData } from '../../../../hooks/useDashboardData'

interface ECBInflationExpectationsChartProps {
  data: ECBInflationExpectationsData | null
}

interface ChartDataPoint {
  date: string
  inflation_12m: number | null
  inflation_3y: number | null
  inflation_5y: number | null
  [key: string]: unknown
}

// 色設定
const COLORS = {
  inflation_12m: '#5DADE2',  // 水色（12ヶ月先）
  inflation_3y: '#E74C3C',   // 赤色（3年先）
  inflation_5y: '#F4D03F',   // 黄色（5年先）
}

export default function ECBInflationExpectationsChart({ data }: ECBInflationExpectationsChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // 期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement('default', {
    default: 10,
  })

  // 3系列のデータをマージ
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const inflation12m = data.inflation_12m || []
    const inflation3y = data.inflation_3y || []
    const inflation5y = data.inflation_5y || []

    // 日付をキーにしたマップを作成
    const dateMap = new Map<string, ChartDataPoint>()

    const initPoint = (date: string): ChartDataPoint => ({
      date,
      inflation_12m: null,
      inflation_3y: null,
      inflation_5y: null,
    })

    // 12ヶ月先データ
    inflation12m.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      dateMap.get(point.date)!.inflation_12m = point.value
    })

    // 3年先データ
    inflation3y.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      dateMap.get(point.date)!.inflation_3y = point.value
    })

    // 5年先データ
    inflation5y.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      dateMap.get(point.date)!.inflation_5y = point.value
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

  // 各系列の最新値を取得
  const latest12m = useMemo(() => {
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].inflation_12m !== null) {
        return { date: chartData[i].date, value: chartData[i].inflation_12m }
      }
    }
    return null
  }, [chartData])

  const latest3y = useMemo(() => {
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].inflation_3y !== null) {
        return { date: chartData[i].date, value: chartData[i].inflation_3y }
      }
    }
    return null
  }, [chartData])

  const latest5y = useMemo(() => {
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].inflation_5y !== null) {
        return { date: chartData[i].date, value: chartData[i].inflation_5y }
      }
    }
    return null
  }, [chartData])

  if (data === null) {
    return <LoadingChart title="インフレ期待（ユーロ圏・CES）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="インフレ期待（ユーロ圏・CES）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ecb-inflation-expectations-chart">
      <ChartContainer
        title="インフレ期待（ユーロ圏・CES）"
        showPeriodSelector={false}
        dataSource="European Central Bank (ECB)"
        sourceUrl="https://www.ecb.europa.eu/press/pubbydate/html/index.en.html?search_term=ECB%20Consumer%20Expectations%20Survey%20results"
      >
        {/* 最新値表示（3系列） */}
        <LatestValueBox
          items={[
            {
              label: '12ヶ月先',
              value: latest12m?.value,
              color: COLORS.inflation_12m,
              format: 'percent',
            },
            {
              label: '3年先',
              value: latest3y?.value,
              color: COLORS.inflation_3y,
              format: 'percent',
            },
            {
              label: '5年先',
              value: latest5y?.value,
              color: COLORS.inflation_5y,
              format: 'percent',
            },
          ]}
          date={latest12m?.date}
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
                  {/* 期間セレクタ + 比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く（インフレ期待・CES）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() =>
                          window.open(
                            '/compare?s=eurozone_ces_inflation_12m&s=eurozone_ces_inflation_3y&s=eurozone_ces_inflation_5y',
                            '_blank'
                          )
                        }
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* インフレ期待グラフ（3系列） */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      {
                        dataKey: 'inflation_12m',
                        color: COLORS.inflation_12m,
                        name: '12ヶ月先',
                      },
                      {
                        dataKey: 'inflation_3y',
                        color: COLORS.inflation_3y,
                        name: '3年先',
                      },
                      {
                        dataKey: 'inflation_5y',
                        color: COLORS.inflation_5y,
                        name: '5年先',
                      },
                    ]}
                    yAxisFormatter={(v) => `${Number(v).toFixed(1)}%`}
                    yDomain={['dataMin - 0.3', 'dataMax + 0.3']}
                    showZeroLine={false}
                  />
                </>
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
