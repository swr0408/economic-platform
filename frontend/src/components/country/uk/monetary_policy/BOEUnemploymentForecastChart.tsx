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
  [seriesKey: string]: string | number | null | undefined
}

// 系列キー → 色 (previous=赤破線、最新/シナリオ=寒色系)
const SERIES_COLORS: Record<string, string> = {
  latest: '#1890ff',
  previous: '#ff7875',
  scenario_a: '#1890ff',
  scenario_b: '#52c41a',
  scenario_c: '#b37feb',
}
const FALLBACK_COLORS = ['#13c2c2', '#faad14', '#eb2f96']

// table_data の行から quarter 以外の系列キーを抽出 (シナリオ→latest→previous の順)
const extractSeriesKeys = (rows: { quarter: string;[k: string]: unknown }[]): string[] => {
  const keys = new Set<string>()
  for (const row of rows) {
    for (const k of Object.keys(row)) {
      if (k !== 'quarter') keys.add(k)
    }
  }
  const scenarios = [...keys].filter((k) => k.startsWith('scenario_')).sort()
  const ordered = [...scenarios]
  if (keys.has('latest')) ordered.push('latest')
  if (keys.has('previous')) ordered.push('previous')
  return ordered
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
  const { chartData, seriesKeys } = useMemo(() => {
    if (!data?.table_data || data.table_data.length === 0) {
      return { chartData: [] as ChartDataPoint[], seriesKeys: [] as string[] }
    }

    // 旧来: { quarter, latest, previous } / 2026年4月MPR以降: { quarter, scenario_a.., previous }
    const keys = extractSeriesKeys(data.table_data)
    const rows = data.table_data
      .filter((row) => keys.some((k) => row[k] !== null && row[k] !== undefined))
      .sort((a, b) => a.quarter.localeCompare(b.quarter)) as ChartDataPoint[]
    return { chartData: rows, seriesKeys: keys }
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

  // 系列キー → 表示名 ("scenario_a" → "シナリオA (2026年4月)")
  const seriesDisplayName = (key: string): string => {
    if (key === 'latest') return `最新 ${latestLabel}`
    if (key === 'previous') return `前回 ${previousLabel}`
    const raw = data.scenario_labels?.[key]
    const m = raw?.match(/Scenario\s+(\w+)\s*$/i)
    const sc = m ? `シナリオ${m[1].toUpperCase()}` : raw || key
    return latestLabel ? `${sc} (${latestLabel})` : sc
  }

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
                return [formatValue(value), seriesDisplayName(name)]
              }}
            />
            <Legend
              wrapperStyle={{ color: DARK_THEME.textPrimary }}
              formatter={(value: string) => seriesDisplayName(value)}
            />
            {seriesKeys.map((key, i) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={SERIES_COLORS[key] ?? FALLBACK_COLORS[i % FALLBACK_COLORS.length]}
                strokeWidth={key === 'previous' ? 2 : 3}
                strokeDasharray={key === 'previous' ? '6 3' : undefined}
                name={key}
                dot={false}
                connectNulls={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartContainer>
  )
}
