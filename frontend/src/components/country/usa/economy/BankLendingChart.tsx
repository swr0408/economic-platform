import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { BankLendingData } from '../../../../hooks/useDashboardData'

interface BankLendingChartProps {
  data: BankLendingData | null
}

export default function BankLendingChart({ data }: BankLendingChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    )
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all' || chartData.length === 0) {
      return chartData
    }

    const cutoffDate = new Date()

    if (selectedPeriod === 'default') {
      // デフォルトは2000年から
      cutoffDate.setFullYear(2000, 0, 1)
    } else {
      // 指定年数前から
      cutoffDate.setFullYear(cutoffDate.getFullYear() - selectedPeriod)
    }

    return chartData.filter((item) => {
      const itemDate = new Date(item.date)
      return itemDate >= cutoffDate
    })
  }, [chartData, selectedPeriod])

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="銀行貸し出し態度（SLOOS）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="銀行貸し出し態度（SLOOS）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  const formatPercentage = (value: number) => {
    const sign = value >= 0 ? '+' : ''
    return `${sign}${value.toFixed(1)}%`
  }

  const formatQuarterLabel = (dateStr: string): string => {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    const year = date.getFullYear()
    const quarter = Math.floor(date.getMonth() / 3) + 1
    return `${year}Q${quarter}`
  }

  return (
    <div id="bank-lending-chart">
      <ChartContainer
        title="銀行貸し出し態度"
        showPeriodSelector={false}
        dataSource="FRED (Federal Reserve)"
      >
        {/* 最新値表示 */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 12,
            padding: '12px 16px',
            background: '#f5f5f5',
            borderRadius: 8,
          }}
        >
          <div>
            <span style={{ fontSize: 12, color: '#666' }}>最新値: </span>
            {data.latest && (
              <>
                <span
                  style={{
                    fontSize: 20,
                    fontWeight: 'bold',
                    color: '#8b0000',
                  }}
                >
                  {formatPercentage(data.latest.value)}
                </span>
                <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>
                  ({formatQuarterLabel(data.latest.date)})
                </span>
              </>
            )}
          </div>
        </div>

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color="#8b0000"
          name="銀行貸し出し態度"
          height={450}
          tickFormatter={formatPercentage}
          tooltipFormatter={formatPercentage}
          tooltipLabelFormatter={formatQuarterLabel}
          xAxisTickFormatter={formatQuarterLabel}
          enableDynamicTicks={true}
          showZeroLine={true}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={true}
        />
      </ChartContainer>
    </div>
  )
}
