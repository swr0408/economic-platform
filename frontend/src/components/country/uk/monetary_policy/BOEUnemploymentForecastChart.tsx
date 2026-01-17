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
import type { BOEUnemploymentForecastData } from '../../../../hooks/useDashboardData'
import { DARK_THEME, TOOLTIP_STYLE, CARTESIAN_GRID_PROPS } from '../../usa/common/chartConstants'

interface BOEUnemploymentForecastChartProps {
  data: BOEUnemploymentForecastData | null
}

interface ChartDataPoint {
  quarter: string
  latest: number | null
  previous: number | null
}

// Convert forecast date to readable format (e.g., "November 2025" -> "2025年11月")
const formatForecastDate = (dateStr: string): string => {
  if (!dateStr) return ''

  // If it's in YYYY-MM format
  if (dateStr.match(/^\d{4}-\d{2}$/)) {
    const [year, month] = dateStr.split('-')
    return `${year}年${parseInt(month)}月`
  }

  const monthNames: Record<string, string> = {
    January: '1月',
    February: '2月',
    March: '3月',
    April: '4月',
    May: '5月',
    June: '6月',
    July: '7月',
    August: '8月',
    September: '9月',
    October: '10月',
    November: '11月',
    December: '12月',
  }

  // Handle "Month Year" format (e.g., "November 2025")
  const parts = dateStr.split(' ')
  if (parts.length === 2 && monthNames[parts[0]]) {
    return `${parts[1]}年${monthNames[parts[0]]}`
  }

  return monthNames[dateStr] || dateStr
}

// Format quarter label
const formatQuarterLabel = (quarter: string): string => {
  if (!quarter) return ''

  // Handle format like "2025Q2" -> "2025/Q2"
  if (quarter.match(/^\d{4}Q\d$/)) {
    return quarter.replace(/(\d{4})Q(\d)/, '$1/Q$2')
  }

  return quarter
}

export default function BOEUnemploymentForecastChart({ data }: BOEUnemploymentForecastChartProps) {
  // Prepare chart data from table_data
  const chartData = useMemo(() => {
    if (!data?.table_data || data.table_data.length === 0) {
      return []
    }

    // table_data has format: { quarter, latest, previous }
    return data.table_data
      .map((row) => ({
        quarter: row.quarter,
        latest: row.latest,
        previous: row.previous,
      }))
      .filter((row) => row.latest !== null || row.previous !== null)
      .sort((a, b) => a.quarter.localeCompare(b.quarter)) as ChartDataPoint[]
  }, [data])

  const formatValue = (value: number): string => {
    return `${value.toFixed(1)}%`
  }

  if (!data || chartData.length === 0) {
    return (
      <ChartContainer
        title="失業率 見通し"
        showDataSource={true}
        dataSource="Bank of England"
      >
        <Empty description="データがありません" />
      </ChartContainer>
    )
  }

  const latestForecastDate = (data.metadata?.latest_forecast as string) || ''
  const previousForecastDate = (data.metadata?.previous_forecast as string) || ''

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
              dataKey="quarter"
              tickFormatter={formatQuarterLabel}
              tick={{ fontSize: 11, fill: DARK_THEME.textSecondary }}
              stroke={DARK_THEME.border}
            />
            <YAxis
              domain={['dataMin - 0.2', 'dataMax + 0.2']}
              tickFormatter={formatValue}
              tick={{ fontSize: 11, fill: DARK_THEME.textSecondary }}
              stroke={DARK_THEME.border}
            />
            <Tooltip
              labelFormatter={formatQuarterLabel}
              contentStyle={TOOLTIP_STYLE}
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
              strokeWidth={2}
              name="latest"
              dot={false}
              connectNulls={false}
            />
            <Line
              type="monotone"
              dataKey="previous"
              stroke="#52c41a"
              strokeWidth={2}
              name="previous"
              dot={false}
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartContainer>
  )
}
