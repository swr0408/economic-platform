import { useState, useMemo } from 'react'
import { Typography } from 'antd'
import ChartContainer from '../common/ChartContainer'
import ZoomableChart from '../common/ZoomableChart'
import type { PeriodValue } from '../common/PeriodSelector'
import type { MarketSymbolData } from '../../hooks/useMarketData'
import { formatMonthLabel } from '../../utils/dateFormatters'

const { Text } = Typography

const DARK_THEME = {
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  accent: '#10b981',
  bgTertiary: '#334155',
}

interface MarketPriceChartProps {
  title: string
  symbolData: MarketSymbolData | null | undefined
  color?: string
  unit?: string
  decimals?: number
}

export default function MarketPriceChart({
  title,
  symbolData,
  color = '#3b82f6',
  unit = '',
  decimals = 2,
}: MarketPriceChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(2)

  const chartData = useMemo(() => {
    if (!symbolData?.data) return []
    return symbolData.data
      .map((d) => ({
        date: d.date,
        value: d.close,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [symbolData])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    if (selectedPeriod === 'default') {
      // デフォルト: 5年
      const cutoff = new Date()
      cutoff.setFullYear(cutoff.getFullYear() - 5)
      const cutoffStr = cutoff.toISOString().slice(0, 10)
      return chartData.filter((d) => d.date >= cutoffStr)
    }
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 5
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  const formatValue = (value: number) => {
    if (value >= 10000) return `${value.toLocaleString(undefined, { maximumFractionDigits: decimals })}${unit}`
    return `${value.toFixed(decimals)}${unit}`
  }

  if (!symbolData) {
    return (
      <ChartContainer title={title} loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (chartData.length === 0) {
    return (
      <ChartContainer title={title} showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = symbolData.latest

  return (
    <ChartContainer
      title={title}
      dataSource="Yahoo Finance"
      onPeriodChange={setSelectedPeriod}
      selectedPeriod={selectedPeriod}
    >
      {latest && (
        <div
          style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: 12,
            marginBottom: 12,
            padding: '8px 12px',
            background: DARK_THEME.bgTertiary,
            borderRadius: 8,
          }}
        >
          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>最新値</Text>
          <Text
            style={{ color, fontSize: 20, fontWeight: 700 }}
            className="tabular-nums"
          >
            {formatValue(latest.close)}
          </Text>
          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>
            ({latest.date})
          </Text>
        </div>
      )}

      <ZoomableChart
        data={filteredData}
        height={350}
        color={color}
        strokeWidth={1.5}
        name={title}
        tickFormatter={formatValue}
        tooltipFormatter={formatValue}
        xAxisTickFormatter={formatMonthLabel}
      />
    </ChartContainer>
  )
}
