/**
 * UK ONS実質平均週給チャートコンポーネント
 *
 * データ:
 * - Total Pay (A3WW): 実質平均週給（賞与含む）前年比
 * - Regular Pay (A2FA): 実質平均週給（賞与除く）前年比
 *
 * データソース:
 * - ONS (Office for National Statistics)
 *
 * 発表スケジュール:
 * - ONS公式サイトの「Next release」日程に基づく
 * - 15:00-16:10 ロンドン時間
 */
import { useState, useMemo, useCallback } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { ONSRealWagesData } from '../../../../hooks/useDashboardData'
import type { PeriodType } from '../../usa/common/useChartData'

interface ONSRealWagesChartProps {
  data: ONSRealWagesData | null
}

interface ChartDataPoint {
  date: string
  total_pay: number | null
  regular_pay: number | null
  [key: string]: unknown
}

// グラフの色
const TOTAL_PAY_COLOR = '#3498db'
const REGULAR_PAY_COLOR = '#e74c3c'

export default function ONSRealWagesChart({ data }: ONSRealWagesChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter(point => point.total_pay !== null || point.regular_pay !== null)
      .map(point => ({
        date: point.date,
        total_pay: point.total_pay,
        regular_pay: point.regular_pay,
      }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  // 期間変更ハンドラ
  const handlePeriodChange = useCallback((period: PeriodType) => {
    setSelectedPeriod(period)
  }, [])

  // データ比較ページを開く
  const handleCompare = useCallback(() => {
    window.open('/compare?s=uk_real_wages_total&s=uk_real_wages_regular', '_blank')
  }, [])

  if (data === null) {
    return <LoadingChart title="ONS実質平均週給（前年比）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="ONS実質平均週給（前年比）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値表示用アイテム
  const latestItems = latest ? [
    {
      label: '賞与含む',
      value: latest.total_pay,
      color: TOTAL_PAY_COLOR,
      format: 'percent' as const,
      decimals: 1,
    },
    {
      label: '賞与除く',
      value: latest.regular_pay,
      color: REGULAR_PAY_COLOR,
      format: 'percent' as const,
      decimals: 1,
    },
  ] : []

  return (
    <div id="uk-ons-real-wages-chart">
      <ChartContainer
        title="実質平均週給"
        showPeriodSelector={false}
        dataSource="ONS"
        sourceUrl="https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={latestItems}
          date={latest?.date}
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
                  {/* 期間セレクター */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={handlePeriodChange} selectedPeriod={selectedPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={handleCompare}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* チャート表示 */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      {
                        dataKey: 'total_pay',
                        color: TOTAL_PAY_COLOR,
                        name: '実質平均週給（賞与含む）',
                        hide: hiddenSeries.has('total_pay'),
                      },
                      {
                        dataKey: 'regular_pay',
                        color: REGULAR_PAY_COLOR,
                        name: '実質平均週給（賞与除く）',
                        hide: hiddenSeries.has('regular_pay'),
                      },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
                    onLegendClick={handleLegendClick}
                    yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ons_wages" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
