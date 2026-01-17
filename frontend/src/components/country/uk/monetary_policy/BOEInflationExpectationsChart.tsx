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
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import type { BOEInflationExpectationsData } from '../../../../hooks/useDashboardData'
import { DARK_THEME, TOOLTIP_STYLE, CARTESIAN_GRID_PROPS } from '../../usa/common/chartConstants'

interface BOEInflationExpectationsChartProps {
  data: BOEInflationExpectationsData | null
}

interface ChartDataPoint {
  date: string
  [key: string]: string | number | null
}

// Series name mapping for display (convert long English names to shorter Japanese names)
const SERIES_NAME_MAP: Record<string, string> = {
  // Nov 2025 MPR format: Households (Citi/YouGov) and Businesses (DMP Survey)
  '家計 - 短期': '家計 短期',
  '家計 - 中期': '家計 中期',
  '家計 - Short-term  expectations  (2010-19 average)': '家計 短期 (2010-19平均)',
  '家計 - Medium-term expectations  (2010-19 average)': '家計 中期 (2010-19平均)',
  '企業 - 短期': '企業 短期',
  '企業 - 中期': '企業 中期',
  // Multi-row header format (Group - Series)
  'Households - One year ahead': '家計 1年先',
  'Households - Two years ahead': '家計 2年先',
  'Households - Five years ahead': '家計 5年先',
  'Firms - One year ahead': '企業 1年先',
  'Firms - Two years ahead': '企業 2年先',
  'Firms - Five years ahead': '企業 5年先',
  'Businesses - One year ahead': '企業 1年先',
  'Businesses - Two years ahead': '企業 2年先',
  'Businesses - Five years ahead': '企業 5年先',
  // Citi/YouGov format
  'Households (Citi/YouGov) (per cent)': '家計 (Citi/YouGov)',
  'Firms (DMP)': '企業 (DMP)',
  'CBI': 'CBI',
  // Alternative formats
  'Households': '家計',
  'Firms': '企業',
  'Household inflation expectations': '家計インフレ期待',
  'Business inflation expectations': '企業インフレ期待',
  'One year ahead': '1年先',
  'Two years ahead': '2年先',
  'Five years ahead': '5年先',
  'One year ahead household inflation expectations': '家計1年先',
  'Two year ahead household inflation expectations': '家計2年先',
  'One year ahead business inflation expectations': '企業1年先',
  'Five to ten years ahead inflation expectations': '5-10年先',
  // Professional forecasters
  'Professional forecasters one year ahead': '予測者 1年先',
  'Professional forecasters two years ahead': '予測者 2年先',
}

// Check if a series is an average (historical reference) series that should be displayed as dashed line
const isAverageSeries = (seriesName: string): boolean => {
  const lowerName = seriesName.toLowerCase()
  return lowerName.includes('average') || lowerName.includes('平均')
}

// Get display name for series
const getSeriesDisplayName = (seriesName: string): string => {
  // First try exact match
  if (SERIES_NAME_MAP[seriesName]) {
    return SERIES_NAME_MAP[seriesName]
  }
  // Then try partial match
  const lowerName = seriesName.toLowerCase()
  for (const [key, value] of Object.entries(SERIES_NAME_MAP)) {
    if (lowerName.includes(key.toLowerCase())) {
      return value
    }
  }
  return seriesName
}

// Color palette for main series (solid lines)
const MAIN_COLORS = [
  '#1890ff', // Blue - 家計 短期
  '#52c41a', // Green - 家計 中期
  '#f5222d', // Red - 企業 短期
  '#faad14', // Orange - 企業 中期
  '#722ed1', // Purple
  '#13c2c2', // Cyan
]

// Color palette for average series (dashed lines) - distinct colors
const AVERAGE_COLORS = [
  '#69c0ff', // Light Blue - 家計 短期 平均
  '#95de64', // Light Green - 家計 中期 平均
]

// Get color for series based on type and order
const getSeriesColor = (seriesName: string, seriesNames: string[]): string => {
  const isAverage = isAverageSeries(seriesName)

  if (isAverage) {
    // Count how many average series came before this one
    const averageIndex = seriesNames
      .filter(isAverageSeries)
      .indexOf(seriesName)
    return AVERAGE_COLORS[averageIndex % AVERAGE_COLORS.length]
  } else {
    // Count how many non-average series came before this one
    const mainIndex = seriesNames
      .filter(name => !isAverageSeries(name))
      .indexOf(seriesName)
    return MAIN_COLORS[mainIndex % MAIN_COLORS.length]
  }
}

// Custom dot renderer - only show dots for isolated points (surrounded by null values)
const createCustomDot = (allData: ChartDataPoint[], seriesName: string, color: string) => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (props: Record<string, any>) => {
    const { cx, cy, index } = props

    // Return empty SVG group if no valid position or index
    if (cx === undefined || cy === undefined || index === undefined) {
      return <svg />
    }

    const currentValue = allData[index]?.[seriesName]
    const prevValue = index > 0 ? allData[index - 1]?.[seriesName] : null
    const nextValue = index < allData.length - 1 ? allData[index + 1]?.[seriesName] : null

    // Show dot only if current value exists but is isolated (prev or next is null)
    if (currentValue !== null && (prevValue === null || nextValue === null)) {
      return (
        <circle
          cx={cx}
          cy={cy}
          r={3}
          fill={color}
          stroke={color}
          strokeWidth={1}
        />
      )
    }

    // Return empty SVG element instead of null
    return <svg />
  }
}

// Format date label
const formatDateLabel = (dateStr: string): string => {
  if (!dateStr) return ''

  // If it's in YYYY-MM format
  if (dateStr.match(/^\d{4}-\d{2}$/)) {
    const [year, month] = dateStr.split('-')
    return `${year}/${parseInt(month)}`
  }

  // If it's in YYYY-QX format (quarterly)
  if (dateStr.match(/^\d{4}-Q\d$/)) {
    const [year, quarter] = dateStr.split('-')
    return `${year}/${quarter}`
  }

  // If it's in YYYYQX format (quarterly without hyphen)
  if (dateStr.match(/^\d{4}Q\d$/)) {
    const year = dateStr.substring(0, 4)
    const quarter = dateStr.substring(4)
    return `${year}/${quarter}`
  }

  return dateStr
}

// Convert MPR date to Japanese format (e.g., "November 2025" -> "2025年11月")
const formatMPRDate = (dateStr: string): string => {
  if (!dateStr) return ''

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

  return dateStr
}

export default function BOEInflationExpectationsChart({ data }: BOEInflationExpectationsChartProps) {
  // Prepare chart data
  const { chartData, seriesNames, mprLabel } = useMemo(() => {
    const expectationsData = data?.inflation_expectations?.data

    if (!expectationsData?.date?.length) {
      return { chartData: [], seriesNames: [], mprLabel: '' }
    }

    // Get MPR date label
    const mprDate = formatMPRDate((data?.metadata?.mpr_date as string) || '')

    // Get series names
    const names = expectationsData.series ? Object.keys(expectationsData.series) : []

    // Build chart data points, filtering out header row if present
    const result: ChartDataPoint[] = expectationsData.date
      .map((date, idx) => {
        // Skip "Date" header row
        if (date.toLowerCase() === 'date') {
          return null
        }

        const point: ChartDataPoint = { date }

        names.forEach(name => {
          point[name] = expectationsData.series[name][idx]
        })

        return point
      })
      .filter((point): point is ChartDataPoint => point !== null)

    return {
      chartData: result,
      seriesNames: names,
      mprLabel: mprDate
    }
  }, [data])

  if (!data || chartData.length === 0) {
    return (
      <ChartContainer
        title="インフレ期待（家計/企業）"
        showDataSource={true}
        dataSource="Bank of England"
      >
        <Empty description="データがありません" />
      </ChartContainer>
    )
  }

  return (
    <ChartContainer
      title=""
      showDataSource={true}
      dataSource="Bank of England"
      sourceUrl="https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates"
    >
      <div style={{ width: '100%', height: 500 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid {...CARTESIAN_GRID_PROPS} />
            <XAxis
              dataKey="date"
              tickFormatter={formatDateLabel}
              tick={{ fontSize: 11, fill: DARK_THEME.textSecondary }}
              stroke={DARK_THEME.border}
            />
            <YAxis
              label={{ angle: -90, position: 'insideLeft', fill: DARK_THEME.textSecondary }}
              tick={{ fontSize: 11, fill: DARK_THEME.textSecondary }}
              stroke={DARK_THEME.border}
            />
            <Tooltip
              labelFormatter={formatDateLabel}
              contentStyle={TOOLTIP_STYLE}
              formatter={(value: unknown, name: unknown) => {
                const numValue = typeof value === 'number' ? value : null
                const rawName = typeof name === 'string' ? name : ''
                const shortName = getSeriesDisplayName(rawName)

                const displayName = mprLabel ? `${shortName} (${mprLabel})` : shortName

                if (numValue === null) {
                  return ['n.a.', displayName]
                }
                return [numValue.toFixed(1) + '%', displayName]
              }}
            />
            <Legend
              wrapperStyle={{ color: DARK_THEME.textPrimary }}
              formatter={(value: string) => {
                const shortName = getSeriesDisplayName(value)
                return mprLabel ? `${shortName} (${mprLabel})` : shortName
              }}
            />

            {/* Reference line at 2% target */}
            <ReferenceLine y={2} stroke={DARK_THEME.textTertiary} strokeWidth={1} strokeDasharray="5 5" />

            {/* Lines for series */}
            {seriesNames.map((seriesName) => {
              const color = getSeriesColor(seriesName, seriesNames)
              const isDashed = isAverageSeries(seriesName)
              return (
                <Line
                  key={seriesName}
                  type="monotone"
                  dataKey={seriesName}
                  stroke={color}
                  strokeWidth={isDashed ? 1.5 : 2}
                  strokeDasharray={isDashed ? '5 5' : undefined}
                  name={seriesName}
                  dot={createCustomDot(chartData, seriesName, color)}
                  activeDot={{ r: 5 }}
                  connectNulls={false}
                />
              )
            })}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartContainer>
  )
}
