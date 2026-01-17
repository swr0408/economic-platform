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
import type { BOEWageGrowthData } from '../../../../hooks/useDashboardData'
import { DARK_THEME, TOOLTIP_STYLE, CARTESIAN_GRID_PROPS } from '../../usa/common/chartConstants'

interface BOEWageGrowthChartProps {
  data: BOEWageGrowthData | null
}

interface ChartDataPoint {
  date: string
  [key: string]: string | number | null
}

// Series name mapping for display (convert long English names to shorter Japanese names)
const SERIES_NAME_MAP: Record<string, string> = {
  // Composite/average measure
  'Measures of private sector wage growth (percentage changes on a year earlier)': '民間賃金上昇率（平均）',
  // Individual wage indicators
  'Private sector regular pay': 'AWE民間正規賃金',
  'Private sector regular pay (AWE)': 'AWE民間正規賃金',
  'AWE private sector regular pay': 'AWE民間正規賃金',
  "Agents' Pay survey": 'エージェント賃金調査',
  "Agents' pay survey": 'エージェント賃金調査',
  'DMP': 'DMP',
  'Decision Maker Panel': 'DMP',
  'Indeed wage tracker': 'Indeed賃金トラッカー',
  'Indeed Wage Tracker': 'Indeed賃金トラッカー',
  'HMRC RTI median (private sector proxy)': 'HMRC RTI中央値',
  'HMRC RTI median': 'HMRC RTI中央値',
  'HMRC median': 'HMRC中央値',
  // Alternative names for regular pay growth
  'Measures of annual private sector regular pay growth (percentage changes on a year earlier)': '民間正規賃金上昇率（年率）',
}

// Get display name for series
const getSeriesDisplayName = (seriesName: string): string => {
  return SERIES_NAME_MAP[seriesName] || seriesName
}

// Color palette for series
const LATEST_COLORS = [
  '#1890ff', // Blue
  '#52c41a', // Green
  '#faad14', // Orange
  '#f5222d', // Red
  '#b16fdf', // Purple
  '#13c2c2', // Cyan
  '#eb2f96', // Magenta
  '#fa8c16'  // Gold
]

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

export default function BOEWageGrowthChart({ data }: BOEWageGrowthChartProps) {
  // Prepare chart data - now only using single data source (latest MPR only)
  const { chartData, seriesNames, mprLabel } = useMemo(() => {
    // New format: data.wage_growth.data (single data, not latest_data/previous_data)
    const wageData = data?.wage_growth?.data

    if (!wageData?.date?.length) {
      return { chartData: [], seriesNames: [], mprLabel: '' }
    }

    // Get MPR date label (new format: mpr_date, old format: latest_mpr_date)
    const mprDate = formatMPRDate((data?.metadata?.mpr_date as string) || (data?.metadata?.latest_mpr_date as string) || '')

    // Get series names
    const names = wageData.series ? Object.keys(wageData.series) : []

    // Build chart data points
    const result: ChartDataPoint[] = wageData.date.map((date, idx) => {
      const point: ChartDataPoint = { date }

      names.forEach(name => {
        point[name] = wageData.series[name][idx]
      })

      return point
    })

    return {
      chartData: result,
      seriesNames: names,
      mprLabel: mprDate
    }
  }, [data])

  if (!data || chartData.length === 0) {
    return (
      <ChartContainer
        title="民間セクター賃金上昇率 見通し"
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

            {/* Reference line at 0 */}
            <ReferenceLine y={0} stroke={DARK_THEME.textTertiary} strokeWidth={1} />

            {/* Lines for series (only latest MPR data now) */}
            {seriesNames.map((seriesName, index) => {
              const color = LATEST_COLORS[index % LATEST_COLORS.length]
              return (
                <Line
                  key={seriesName}
                  type="monotone"
                  dataKey={seriesName}
                  stroke={color}
                  strokeWidth={2}
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
