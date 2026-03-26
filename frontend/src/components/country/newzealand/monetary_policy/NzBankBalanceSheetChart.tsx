/**
 * NZ銀行バランスシート（総資産）チャートコンポーネント
 *
 * データソース:
 * - RBNZ Statistical Tables S10 (Banks: Balance sheet)
 * - https://www.rbnz.govt.nz/statistics/series/registered-banks/banks-balance-sheet
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

import type { NzBankBalanceSheetData } from '../../../../hooks/useDashboardData'

interface NzBankBalanceSheetChartProps {
  data: NzBankBalanceSheetData | null
}

interface ChartDataPoint {
  date: string
  value: number
  [key: string]: string | number | null | undefined
}

const CHART_COLOR = '#10b981'

export default function NzBankBalanceSheetChart({ data }: NzBankBalanceSheetChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)

  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data || data.data.length === 0) return []

    return data.data
      .map((item) => ({
        date: item.date,
        value: item.value,
      }))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  }, [data])

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2017,
  })

  const hasData = chartData.length > 0
  const latestValue = filteredData.length > 0 ? filteredData[filteredData.length - 1] : null

  // NZDm → 表示フォーマット（十億NZD）
  const formatValue = (value: number) => {
    const billions = value / 1000
    return `${billions.toFixed(1)}B NZD`
  }

  const formatYAxis = (value: number) => {
    const billions = value / 1000
    return `${billions.toFixed(0)}B`
  }

  if (data === null) {
    return <LoadingChart title="銀行バランスシート" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="銀行バランスシート" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="bank-balance-sheet">
      <ChartContainer
        title="銀行バランスシート（総資産）"
        showPeriodSelector={false}
        dataSource="RBNZ"
        sourceUrl="https://www.rbnz.govt.nz/statistics/series/registered-banks/banks-balance-sheet"
        handbookId="bank-balance-sheet"
      >
        <SimpleLatestValueBox
          label="Total Assets"
          value={latestValue ? formatValue(latestValue.value) : null}
          valueColor={CHART_COLOR}
          date={latestValue?.date}
          format="raw"
          nextRelease={data.next_release ?? null}
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=nz_bank_balance_sheet', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color={CHART_COLOR}
          name="Total Assets"
          height={450}
          tickFormatter={formatYAxis}
          xAxisTickFormatter={formatDateLabel}
          enableDynamicTicks={true}
          showZeroLine={false}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={true}
          showDefaultTooltip={false}
          domain={['dataMin - 20000', 'dataMax + 20000']}
        >
          <RechartsTooltip
            content={({ active, payload, label }) => {
              if (!active || !payload || payload.length === 0) return null
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
                  {payload.map((item, index) => (
                    <div
                      key={index}
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
                            backgroundColor: item.color || CHART_COLOR,
                            marginRight: 6,
                          }}
                        />
                        {item.name}
                      </span>
                      <span style={{ fontWeight: 500, color: item.color || CHART_COLOR }}>
                        {formatValue(item.value as number)}
                      </span>
                    </div>
                  ))}
                </div>
              )
            }}
          />
        </ZoomableChart>
      </ChartContainer>
    </div>
  )
}
