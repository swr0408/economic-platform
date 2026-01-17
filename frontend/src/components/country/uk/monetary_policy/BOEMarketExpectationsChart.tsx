import { useMemo } from 'react'
import { Empty } from 'antd'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import type { BOEMarketExpectationsData } from '../../../../hooks/useDashboardData'
import { DARK_THEME, TOOLTIP_STYLE, CARTESIAN_GRID_PROPS } from '../../usa/common/chartConstants'

interface BOEMarketExpectationsChartProps {
  data: BOEMarketExpectationsData | null
}

interface ChartDataPoint {
  date: string
  latest: number | null
  previous: number | null
}

// Convert forecast date to readable format (e.g., "2025-08" -> "2025年8月")
const formatForecastDate = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}年${parseInt(month)}月`
}

// Format quarter label
const formatQuarterLabel = (quarterStr: string): string => {
  return quarterStr
}

export default function BOEMarketExpectationsChart({ data }: BOEMarketExpectationsChartProps) {
  // Prepare chart data
  const chartData = useMemo(() => {
    if (!data?.latest && !data?.previous) {
      return []
    }

    const latestData = data?.latest?.data || []
    const previousData = data?.previous?.data || []

    // Get all unique dates (quarters) from both datasets
    const allDates = new Set<string>()
    latestData.forEach((p) => allDates.add(p.date))
    previousData.forEach((p) => allDates.add(p.date))

    // Create data map
    const dataMap: Record<string, ChartDataPoint> = {}
    Array.from(allDates)
      .sort()
      .forEach((date) => {
        dataMap[date] = {
          date,
          previous: null,
          latest: null,
        }
      })

    // Fill in previous forecast data
    previousData.forEach((p) => {
      if (dataMap[p.date]) {
        dataMap[p.date].previous = p.value
      }
    })

    // Fill in latest forecast data
    latestData.forEach((p) => {
      if (dataMap[p.date]) {
        dataMap[p.date].latest = p.value
      }
    })

    // Sort by date and filter to show range from first previous date to last latest date
    const allPoints = Object.values(dataMap).sort((a, b) => a.date.localeCompare(b.date))

    // Find the date range
    const firstPreviousDate = previousData.length > 0 ? previousData[0].date : ''
    const lastLatestDate = latestData.length > 0 ? latestData[latestData.length - 1].date : ''

    if (!firstPreviousDate || !lastLatestDate) {
      return allPoints
    }

    // Filter to show only the requested range
    return allPoints.filter((point) => point.date >= firstPreviousDate && point.date <= lastLatestDate)
  }, [data])

  const formatValue = (value: number): string => {
    return `${value.toFixed(2)}%`
  }

  if (!data || chartData.length === 0) {
    return (
      <ChartContainer 
      title="政策金利 見通し" 
      showDataSource={true} 
      dataSource="Bank of England"
      >
        <Empty description="データがありません" />
      </ChartContainer>
    )
  }

  const latestForecastDate = data?.latest?.forecast_date || data?.latest?.date || ''
  const previousForecastDate = data?.previous?.forecast_date || data?.previous?.date || ''

  const latestLabel = formatForecastDate(latestForecastDate)
  const previousLabel = formatForecastDate(previousForecastDate)

  return (
    <ChartContainer 
    title="" 
    showDataSource={true} 
    dataSource="Bank of England"
    sourceUrl="https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates"
    >
      <div style={{ width: '100%', height: 400 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid {...CARTESIAN_GRID_PROPS} />
            <XAxis
              dataKey="date"
              tickFormatter={formatQuarterLabel}
              tick={{ fontSize: 11, fill: DARK_THEME.textSecondary }}
              stroke={DARK_THEME.border}
            />
            <YAxis
              domain={['dataMin - 0.1', 'dataMax + 0.1']}
              tickFormatter={formatValue}
              tick={{ fontSize: 11, fill: DARK_THEME.textSecondary }}
              stroke={DARK_THEME.border}
            />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              labelStyle={{ color: DARK_THEME.textPrimary }}
              formatter={(value: number, name: string) => {
                const displayName = name === 'latest' ? `最新 ${latestLabel}` : `前回 ${previousLabel}`
                return [formatValue(value), displayName]
              }}
            />
            <Legend
              wrapperStyle={{ color: DARK_THEME.textPrimary }}
              formatter={(value: string) => {
                if (value === 'latest') return `最新 ${latestLabel}`
                if (value === 'previous') return `前回 ${previousLabel}`
                return value
              }}
            />
            <Line
              type="monotone"
              dataKey="latest"
              stroke="#1890ff"
              strokeWidth={3}
              name="latest"
              dot={false}
              connectNulls={true}
            />
            <Line
              type="monotone"
              dataKey="previous"
              stroke="#ff7875"
              strokeWidth={2}
              name="previous"
              dot={false}
              connectNulls={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartContainer>
  )
}
