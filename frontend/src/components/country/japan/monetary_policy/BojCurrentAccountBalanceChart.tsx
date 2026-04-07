/**
 * 日銀当座預金残高チャートコンポーネント
 *
 * BOJ Current Account Balance (末残・合計)
 * 月次データ（BOJ時系列統計データ検索サイトAPI経由）
 *
 * データソース: 日本銀行
 *
 * 単位:
 * - 生データ: 億円
 * - 表示: 兆円
 */
import { useState, useMemo } from 'react'
import { Tooltip as RechartsTooltip } from 'recharts'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import { usePeriodFiltering, formatDateLabel, type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, SimpleLatestValueBox } from '../../usa/common/ChartComponents'
import { DARK_THEME } from '../../usa/common/chartConstants'

import type { BojCurrentAccountBalanceData } from '../../../../hooks/useDashboardData'

const CHART_COLOR = '#8b5cf6'

interface Props {
  data: BojCurrentAccountBalanceData | null
}

interface ChartDataItem {
  date: string
  value: number
  value_trillion: number
  [key: string]: string | number | null | undefined
}

export default function BojCurrentAccountBalanceChart({ data }: Props) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)

  const chartData = useMemo<ChartDataItem[]>(() => {
    if (!data?.data || data.data.length === 0) return []

    const result: ChartDataItem[] = data.data.map((item) => ({
      date: item.date,
      value: item.value,
      value_trillion: item.value_trillion,
    }))

    result.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
    return result
  }, [data])

  const formatValue = (value: number) => {
    return `¥${value.toFixed(1)}兆`
  }

  const formatYAxis = (value: number) => {
    const trillions = value / 10000
    return `${trillions.toFixed(0)}兆`
  }

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  const hasData = chartData.length > 0
  const latestValue = data?.latest

  if (data === null) {
    return <LoadingChart title="日銀当座預金残高" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="日銀当座預金残高" showPeriodSelector={false} showDataSource={false} handbookId="boj-current-account-balance">
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="boj-current-account-balance-chart">
      <ChartContainer
        title="日銀当座預金残高"
        showPeriodSelector={false}
        dataSource="日本銀行"
        sourceUrl="https://www.boj.or.jp/statistics/boj/other/cabs/index.htm"
        handbookId="boj-current-account-balance"
      >
        <SimpleLatestValueBox
          label="当座預金残高（末残・合計）"
          value={latestValue ? formatValue(latestValue.value_trillion) : null}
          valueColor={CHART_COLOR}
          date={latestValue?.date}
          nextRelease={data?.next_release ? {
            date: data.next_release.date,
            label: data.next_release.label || `${data.next_release.time || '08:50'} JST`
          } : null}
          format="raw"
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=bank_of_japan_current_account_balance', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color={CHART_COLOR}
          name="日銀当座預金残高"
          height={450}
          tickFormatter={formatYAxis}
          xAxisTickFormatter={formatDateLabel}
          enableDynamicTicks={true}
          showZeroLine={false}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={true}
          showDefaultTooltip={false}
          domain={['dataMin - 100000', 'dataMax + 100000']}
        >
          <RechartsTooltip
            content={({ active, payload, label }) => {
              if (!active || !payload || payload.length === 0) return null
              const item = payload[0]
              const trillionValue = (item.value as number) / 10000
              return (
                <div
                  style={{
                    backgroundColor: DARK_THEME.bgTertiary,
                    border: `1px solid ${DARK_THEME.borderLight}`,
                    borderRadius: 8,
                    padding: '12px 16px',
                    boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
                  }}
                >
                  <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
                    {formatDateLabel(String(label))}
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: 4,
                      fontSize: 13,
                    }}
                  >
                    <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
                      <span
                        style={{
                          display: 'inline-block',
                          width: 10,
                          height: 10,
                          borderRadius: 2,
                          backgroundColor: CHART_COLOR,
                          marginRight: 6,
                        }}
                      />
                      当座預金残高
                    </span>
                    <span style={{ fontWeight: 500, color: CHART_COLOR }}>
                      ¥{trillionValue.toFixed(1)}兆
                    </span>
                  </div>
                </div>
              )
            }}
          />
        </ZoomableChart>
      </ChartContainer>
    </div>
  )
}
