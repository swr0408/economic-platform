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
import type { BOEUnitWageCostsData } from '../../../../hooks/useDashboardData'
import { DARK_THEME, TOOLTIP_STYLE, CARTESIAN_GRID_PROPS } from '../../usa/common/chartConstants'

interface BOEUnitWageCostsChartProps {
  data: BOEUnitWageCostsData | null
}

interface ChartDataPoint {
  quarter: string
  latest: number | null
  previous: number | null
}

// Convert forecast date to readable format (e.g., "2025-11-01 00:00:00" -> "2025年11月")
const formatForecastDate = (dateStr: string): string => {
  if (!dateStr) return ''

  // Handle ISO date format (e.g., "2025-11-01 00:00:00" or "2025-11-01")
  const isoMatch = dateStr.match(/^(\d{4})-(\d{2})-\d{2}/)
  if (isoMatch) {
    const year = isoMatch[1]
    const month = parseInt(isoMatch[2], 10)
    return `${year}年${month}月`
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
  if (parts.length === 2) {
    if (monthNames[parts[0]]) {
      return `${parts[1]}年${monthNames[parts[0]]}`
    } else if (monthNames[parts[1]]) {
      return `${parts[0]}年${monthNames[parts[1]]}`
    }
  }

  return dateStr
}

// Format quarter label
const formatQuarterLabel = (quarter: string): string => {
  if (!quarter) return ''

  // Handle format like "2025Q2" -> "2025/Q2"
  if (quarter.match(/^\d{4}Q\d$/)) {
    return quarter.replace(/(\d{4})Q(\d)/, '$1/Q$2')
  }

  // Handle format like "2025 Q2" -> "2025/Q2"
  if (quarter.match(/^\d{4}\s+Q\d$/)) {
    return quarter.replace(/(\d{4})\s+Q(\d)/, '$1/Q$2')
  }

  return quarter
}

// Extract year from quarter string (e.g., "2025Q2" -> 2025, "2025 Q2" -> 2025, "2025" -> 2025)
const extractYearFromQuarter = (quarter: string): number | null => {
  if (!quarter) return null
  // Handle pure year format (e.g., "2025")
  if (/^\d{4}$/.test(quarter)) {
    return parseInt(quarter, 10)
  }
  // Handle quarter format (e.g., "2025Q2", "2025 Q2")
  const match = quarter.match(/^(\d{4})/)
  return match ? parseInt(match[1], 10) : null
}

// Filter data to show only recent years (default: 10 years from latest data)
const filterRecentYears = (data: ChartDataPoint[], yearsToShow: number = 10): ChartDataPoint[] => {
  if (data.length === 0) return data

  // Find the latest year in the data
  let latestYear = 0
  for (const point of data) {
    const year = extractYearFromQuarter(point.quarter)
    if (year && year > latestYear) {
      latestYear = year
    }
  }

  if (latestYear === 0) return data

  const cutoffYear = latestYear - yearsToShow
  return data.filter((point) => {
    const year = extractYearFromQuarter(point.quarter)
    return year !== null && year >= cutoffYear
  })
}

export default function BOEUnitWageCostsChart({ data }: BOEUnitWageCostsChartProps) {
  // Prepare chart data
  const { chartData, latestDate, previousDate } = useMemo(() => {
    const uwcData = data?.unit_wage_costs

    if (!uwcData?.latest?.data || uwcData.latest.data.length === 0) {
      return { chartData: [], latestDate: '', previousDate: '' }
    }

    const latestLabel = uwcData.latest?.date || ''
    const previousLabel = uwcData.previous?.date || ''

    // Build chart data points
    const result: ChartDataPoint[] = uwcData.latest.data.map((item, idx) => {
      const point: ChartDataPoint = {
        quarter: item.quarter,
        latest: item.value,
        previous: uwcData.previous?.data?.[idx]?.value ?? null,
      }
      return point
    })

    // Filter to only valid data and recent 10 years
    const validData = result.filter((row) => row.latest !== null || row.previous !== null)
    const recentData = filterRecentYears(validData, 10)

    return {
      chartData: recentData,
      latestDate: latestLabel,
      previousDate: previousLabel,
    }
  }, [data])

  const formatValue = (value: number): string => {
    return `${value.toFixed(1)}%`
  }

  if (!data || chartData.length === 0) {
    return (
      <ChartContainer
        title="単位賃金コスト（UWC）見通し"
        showDataSource={true}
        dataSource="Bank of England"
      >
        <Empty description="データがありません" />
      </ChartContainer>
    )
  }

  const latestLabel = formatForecastDate(latestDate)
  const previousLabel = formatForecastDate(previousDate)

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
              domain={['dataMin - 0.5', 'dataMax + 0.5']}
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
              strokeWidth={3}
              name="latest"
              dot={false}
              connectNulls={true}
            />
            {previousDate && (
              <Line
                type="monotone"
                dataKey="previous"
                stroke="#ff7875"
                strokeWidth={2}
                name="previous"
                dot={false}
                connectNulls={true}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartContainer>
  )
}
