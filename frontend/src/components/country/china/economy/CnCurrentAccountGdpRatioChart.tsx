/**
 * 中国 経常収支対GDP比チャートコンポーネント
 *
 * SAFE経常収支(RMB) / NBS名目GDP(RMB) × 100
 * 四半期データ（%）
 *
 * タブ: 時系列 / マーケットインパクト
 *
 * FMPマッピング: cn_current_account
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import {
  usePeriodFiltering,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import { CHART_COLORS } from '../../usa/common/chartConstants'

import type { CnCurrentAccountGdpRatioData } from '../../../../hooks/useDashboardData'

interface Props {
  data: CnCurrentAccountGdpRatioData | null
}

interface ChartDataPoint {
  date: string
  value: number
  [key: string]: unknown
}

export default function CnCurrentAccountGdpRatioChart({ data }: Props) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(20)

  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []
    return data.data
      .map(item => ({
        date: item.date,
        value: item.value,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  const hasData = chartData.length > 0
  const latestValue = data?.latest

  if (data === null) {
    return (
      <div id="cn-current-account-gdp-ratio">
        <LoadingChart title="経常収支対GDP比" />
      </div>
    )
  }

  if (!hasData) {
    return (
      <div id="cn-current-account-gdp-ratio">
        <ChartContainer title="経常収支対GDP比" showPeriodSelector={false} showDataSource={false}>
          <NoDataMessage />
        </ChartContainer>
      </div>
    )
  }

  return (
    <div id="cn-current-account-gdp-ratio">
      <ChartContainer
        title="経常収支対GDP比"
        showPeriodSelector={false}
        dataSource="SAFE / NBS"
        sourceUrl="https://www.safe.gov.cn/en/SAFENews/index.html"
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
                  {/* データ比較ボタン（右寄せ） */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=cn_current_account_gdp_ratio', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: CHART_COLORS.primary, name: '経常収支対GDP比（%）' },
                    ]}
                    yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                    tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                    showZeroLine={true}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="cn_current_account" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
