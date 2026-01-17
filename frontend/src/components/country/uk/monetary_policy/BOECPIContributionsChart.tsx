import { useMemo } from 'react'
import { Empty } from 'antd'
import {
  ComposedChart,
  Bar,
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
import type { BOECPIContributionsData } from '../../../../hooks/useDashboardData'
import { DARK_THEME, CUSTOM_TOOLTIP_STYLE, CARTESIAN_GRID_PROPS } from '../../usa/common/chartConstants'

interface BOECPIContributionsChartProps {
  data: BOECPIContributionsData | null
}

interface ChartDataPoint {
  date: string
  services: number | null
  food: number | null
  electricity_gas: number | null
  fuels: number | null
  other_goods: number | null
  cpi: number | null
}

// Format date label
const formatDateLabel = (dateStr: string): string => {
  if (!dateStr) return ''

  // Remove "(Bank staff projections)" if present
  const cleanDateStr = dateStr.replace('(Bank staff projections)', '').trim()

  // If it's in YYYY-MM format
  if (cleanDateStr.match(/^\d{4}-\d{2}$/)) {
    const [year, month] = cleanDateStr.split('-')
    return `${year}/${parseInt(month)}`
  }

  return cleanDateStr
}

// Custom Tooltip component
interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{
    payload: ChartDataPoint
    value: number
    name: string
    color: string
    dataKey: string
  }>
  label?: string
}

const CustomTooltip: React.FC<CustomTooltipProps> = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) {
    return null
  }

  // Get the original data point to show actual values
  const dataPoint = payload[0]?.payload as ChartDataPoint
  if (!dataPoint) return null

  return (
    <div style={CUSTOM_TOOLTIP_STYLE}>
      <p style={{ margin: 0, marginBottom: '8px', fontWeight: 'bold', color: DARK_THEME.textPrimary }}>{formatDateLabel(label || '')}</p>
      {dataPoint.services !== null && dataPoint.services !== 0 && (
        <div style={{ marginBottom: '4px' }}>
          <span style={{ color: '#FFD700', fontWeight: 'bold' }}>
            サービス: {dataPoint.services.toFixed(2)}pp
          </span>
        </div>
      )}
      {dataPoint.food !== null && dataPoint.food !== 0 && (
        <div style={{ marginBottom: '4px' }}>
          <span style={{ color: '#9370DB', fontWeight: 'bold' }}>
            食料: {dataPoint.food.toFixed(2)}pp
          </span>
        </div>
      )}
      {dataPoint.electricity_gas !== null && dataPoint.electricity_gas !== 0 && (
        <div style={{ marginBottom: '4px' }}>
          <span style={{ color: '#FF8C00', fontWeight: 'bold' }}>
            電気とガス: {dataPoint.electricity_gas.toFixed(2)}pp
          </span>
        </div>
      )}
      {dataPoint.fuels !== null && dataPoint.fuels !== 0 && (
        <div style={{ marginBottom: '4px' }}>
          <span style={{ color: '#9ACD32', fontWeight: 'bold' }}>
            燃料と潤滑油: {dataPoint.fuels.toFixed(2)}pp
          </span>
        </div>
      )}
      {dataPoint.other_goods !== null && dataPoint.other_goods !== 0 && (
        <div style={{ marginBottom: '2px' }}>
          <span style={{ color: '#00CED1', fontWeight: 'bold' }}>
            その他商品: {dataPoint.other_goods.toFixed(2)}pp
          </span>
        </div>
      )}
      {dataPoint.cpi !== null && (
        <div style={{ marginBottom: '4px' }}>
          <span style={{ color: '#d62728', fontWeight: 'bold' }}>
            CPI: {dataPoint.cpi.toFixed(2)}%
          </span>
        </div>
      )}
    </div>
  )
}

export default function BOECPIContributionsChart({ data }: BOECPIContributionsChartProps) {
  // Prepare chart data
  const chartData = useMemo(() => {
    if (!data?.contributions) {
      return []
    }

    const latestData = data.contributions.latest_data?.data

    if (!latestData || !latestData.date || latestData.date.length === 0) {
      return []
    }

    // Map data to chart format - use original values directly
    const result: ChartDataPoint[] = latestData.date.map((date, idx) => ({
      date,
      services: latestData.services[idx],
      food: latestData.food[idx],
      electricity_gas: latestData.electricity_gas[idx],
      fuels: latestData.fuels[idx],
      other_goods: latestData.other_goods[idx],
      cpi: latestData.cpi[idx]
    }))

    return result.sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  if (!data || chartData.length === 0) {
    return (
      <ChartContainer
        title="CPI寄与度 見通し"
        showDataSource={true}
        dataSource="Bank of England"
      >
        <Empty description="データがありません" />
      </ChartContainer>
    )
  }

  return (
    <ChartContainer
      title="CPI寄与度 見通し"
      showDataSource={true}
      dataSource="Bank of England"
      sourceUrl="https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates"
    >
      <div style={{ width: '100%', height: 500 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={chartData}
            stackOffset="sign"
          >
            <CartesianGrid {...CARTESIAN_GRID_PROPS} />
            <XAxis
              dataKey="date"
              tickFormatter={formatDateLabel}
              tick={{ fontSize: 11, fill: DARK_THEME.textSecondary }}
              stroke={DARK_THEME.border}
            />
            <YAxis
              yAxisId="left"
              label={{ angle: -90, position: 'insideLeft', fill: DARK_THEME.textSecondary }}
              tick={{ fontSize: 11, fill: DARK_THEME.textSecondary }}
              stroke={DARK_THEME.border}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ color: DARK_THEME.textPrimary }} />

            {/* Reference line at 0 */}
            <ReferenceLine yAxisId="left" y={0} stroke={DARK_THEME.textTertiary} strokeWidth={1.5} />

            {/* Stacked bars - Order: Services, Food, Electricity and gas, Fuels, Other goods */}
            <Bar yAxisId="left" dataKey="services" stackId="total" fill="#FFD700" name="サービス" />
            <Bar yAxisId="left" dataKey="food" stackId="total" fill="#9370DB" name="食料" />
            <Bar yAxisId="left" dataKey="electricity_gas" stackId="total" fill="#FF8C00" name="電気とガス" />
            <Bar yAxisId="left" dataKey="fuels" stackId="total" fill="#9ACD32" name="燃料と潤滑油" />
            <Bar yAxisId="left" dataKey="other_goods" stackId="total" fill="#00CED1" name="その他商品" />

            {/* CPI Line */}
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="cpi"
              stroke="#d62728"
              strokeWidth={2}
              name="CPI"
              dot={false}
              connectNulls={true}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </ChartContainer>
  )
}
