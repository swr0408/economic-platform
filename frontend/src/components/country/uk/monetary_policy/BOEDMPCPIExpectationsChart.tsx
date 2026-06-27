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
import type { BOEDMPSurveyData } from '../../../../hooks/useDashboardData'
import { DARK_THEME, TOOLTIP_STYLE, CARTESIAN_GRID_PROPS } from '../../usa/common/chartConstants'

interface BOEDMPCPIExpectationsChartProps {
  data: BOEDMPSurveyData | null
}

interface ChartDataPoint {
  date: string
  oneYearAhead: number | null
  threeYearAhead: number | null
}

// Format date label (YYYY-MM to YYYY/MM)
const formatDateLabel = (dateStr: string): string => {
  if (!dateStr) return ''

  if (dateStr.match(/^\d{4}-\d{2}$/)) {
    const [year, month] = dateStr.split('-')
    return `${year}/${parseInt(month)}`
  }

  return dateStr
}

export default function BOEDMPCPIExpectationsChart({ data }: BOEDMPCPIExpectationsChartProps) {
  const chartData = useMemo(() => {
    const cpiData = data?.survey_data?.cpi_expectations

    if (!cpiData?.date?.length) {
      return []
    }

    const result: ChartDataPoint[] = cpiData.date.map((date, idx) => ({
      date,
      oneYearAhead: cpiData.one_year_ahead?.[idx] ?? null,
      threeYearAhead: cpiData.three_year_ahead?.[idx] ?? null,
    }))

    return result.sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  if (!data || chartData.length === 0) {
    return (
      <ChartContainer
        title="DMP CPIインフレ期待 (3ヶ月平均)"
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
      sourceUrl="https://www.bankofengland.co.uk/search#?cludoquery=Decision%20Maker%20Panel&cludopage=1&cludorefurl=https%3A%2F%2Fwww.bankofengland.co.uk%2F&cludorefpt=Home%20%7C%20Bank%20of%20England&cludoinputtype=standard"
    >
      <div style={{ width: '100%', height: 400 }}>
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
              tick={{ fontSize: 11, fill: DARK_THEME.textSecondary }}
              stroke={DARK_THEME.border}
              tickFormatter={(value: number) => `${value}%`}
              domain={['dataMin - 0.5', 'dataMax + 0.5']}
            />
            <Tooltip
              labelFormatter={formatDateLabel}
              contentStyle={TOOLTIP_STYLE}
              formatter={(value: unknown, name: unknown) => {
                const label = name as string
                if (value === null || value === undefined) return ['n.a.', label]
                const numValue = typeof value === 'number' ? value : null
                if (numValue === null) return ['n.a.', label]
                return [`${numValue.toFixed(2)}%`, label]
              }}
            />
            <Legend wrapperStyle={{ color: DARK_THEME.textPrimary }} />

            {/* BOE Target 2% */}
            <ReferenceLine
              y={2}
              stroke="#ff4d4f"
              strokeDasharray="5 5"
              label={{ value: 'BOE Target (2%)', position: 'right', fill: '#ff4d4f', fontSize: 10 }}
            />

            <Line
              type="monotone"
              dataKey="oneYearAhead"
              stroke="#1890ff"
              strokeWidth={2}
              name="1年先インフレ期待"
              dot={false}
              activeDot={{ r: 5 }}
              connectNulls={true}
            />
            <Line
              type="monotone"
              dataKey="threeYearAhead"
              stroke="#52c41a"
              strokeWidth={2}
              name="3年先インフレ期待"
              dot={false}
              activeDot={{ r: 5 }}
              connectNulls={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartContainer>
  )
}
