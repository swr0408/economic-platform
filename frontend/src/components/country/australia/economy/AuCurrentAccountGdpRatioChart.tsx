/**
 * オーストラリア経常収支対GDP比チャートコンポーネント
 *
 * ABS経常収支 / ABS名目GDP で算出した比率を表示
 *
 * データソース:
 * - ABS 5302.0 Table 4 (Current Account)
 * - ABS 5206.0 Table 1 (Nominal GDP)
 *
 * 発表スケジュール:
 * - 四半期（GDP発表時に更新）
 *
 * 単位:
 * - %
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  usePeriodFiltering,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
} from '../../usa/common/ChartComponents'
import { CHART_COLORS } from '../../usa/common/chartConstants'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { AuCurrentAccountGdpRatioData } from '../../../../hooks/useDashboardData'

interface AuCurrentAccountGdpRatioChartProps {
  data: AuCurrentAccountGdpRatioData | null
}

interface ChartDataItem {
  date: string
  value: number
  current_account?: number
  gdp?: number
  [key: string]: string | number | boolean | null | undefined
}

export default function AuCurrentAccountGdpRatioChart({ data }: AuCurrentAccountGdpRatioChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(20)

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataItem[]>(() => {
    if (!data?.data || data.data.length === 0) return []

    const formattedData: ChartDataItem[] = data.data.map((item) => ({
      date: item.date,
      value: item.value ?? 0,
      current_account: item.current_account,
      gdp: item.gdp,
    }))

    formattedData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return formattedData
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2000,
  })

  const hasData = chartData.length > 0
  const latestValue = data?.latest

  if (data === null) {
    return <LoadingChart title="経常収支対GDP比（オーストラリア）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="経常収支対GDP比（オーストラリア）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="au-current-account-gdp-ratio-chart">
      <ChartContainer
        title="経常収支対GDP比"
        showPeriodSelector={false}
        dataSource="ABS"
        sourceUrl="https://www.abs.gov.au/statistics/economy/international-trade/balance-payments-and-international-investment-position-australia/latest-release"
        handbookId="current-account"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="経常収支対GDP比"
          value={latestValue?.value}
          valueColor={CHART_COLORS.primary}
          date={latestValue?.date}
          nextRelease={data.next_release ?? undefined}
          format="percent"
          decimals={1}
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
                        onClick={() => window.open('/compare?s=au_current_account_gdp_ratio', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <ZoomableChart
                    data={filteredData}
                    dataKey="value"
                    name="経常収支対GDP比"
                    color={CHART_COLORS.primary}
                    height={450}
                    tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                    tooltipFormatter={(v: number) => `${v.toFixed(1)}%`}
                    showZeroLine={true}
                    zeroLineValue={0}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="au_current_account" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
