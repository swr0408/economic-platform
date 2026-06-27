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

interface BOEDMPWageGrowthChartProps {
  data: BOEDMPSurveyData | null
}

interface ChartDataPoint {
  date: string
  realised: number | null
  expected: number | null
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

export default function BOEDMPWageGrowthChart({ data }: BOEDMPWageGrowthChartProps) {
  const chartData = useMemo(() => {
    const wageData = data?.survey_data?.wage_growth

    if (!wageData?.date?.length) {
      return []
    }

    const result: ChartDataPoint[] = wageData.date.map((date, idx) => ({
      date,
      realised: wageData.realised_3mo_avg?.[idx] ?? null,
      expected: wageData.expected_3mo_avg?.[idx] ?? null,
    }))

    return result.sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  if (!data || chartData.length === 0) {
    return (
      <ChartContainer
        title="DMP 賃金上昇率 (3ヶ月平均)"
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

            {/* Reference line at 0 */}
            <ReferenceLine y={0} stroke={DARK_THEME.textTertiary} strokeWidth={1} />

            <Line
              type="monotone"
              dataKey="realised"
              stroke="#1890ff"
              strokeWidth={2}
              name="実績"
              dot={false}
              activeDot={{ r: 5 }}
              connectNulls={true}
            />
            <Line
              type="monotone"
              dataKey="expected"
              stroke="#52c41a"
              strokeWidth={2}
              name="予想"
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
