import { useState, useMemo } from 'react'
import { Typography, Tooltip, Button } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../common/ChartContainer'
import PeriodSelector, { type PeriodValue } from '../../common/PeriodSelector'
import { formatMonthLabel, formatDayLabel } from '../../../utils/dateFormatters'

const { Text } = Typography

// ダークテーマ
const DARK_THEME = {
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  bgTertiary: '#334155',
  gridLine: '#475569',
  axisLine: '#64748b',
  tooltipBg: '#334155',
  tooltipBorder: '#475569',
  chartBg: '#1e293b',
}

// チャートカラー
const NAAIM_COLOR = '#10b981'
const SP500_COLOR = '#3b82f6'

// API レスポンス型
interface NaaimItem {
  date: string
  naaim_number: number
  sp500?: number | null
}

interface NaaimResponse {
  data: NaaimItem[]
  latest: NaaimItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

function useNaaimData() {
  return useQuery({
    queryKey: ['market', 'naaim'],
    queryFn: async () => {
      const { data } = await axios.get<NaaimResponse>('/api/market/naaim')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

// カスタムツールチップ
function CustomTooltip({ active, payload, label }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
}) {
  if (!active || !payload || payload.length === 0) return null

  const formattedLabel = formatDayLabel(String(label))
  const naaimItem = payload.find((p: { dataKey: string }) => p.dataKey === 'naaim_number')
  const spItem = payload.find((p: { dataKey: string }) => p.dataKey === 'sp500')

  return (
    <div
      style={{
        backgroundColor: DARK_THEME.tooltipBg,
        border: `1px solid ${DARK_THEME.tooltipBorder}`,
        borderRadius: 8,
        padding: '12px 16px',
        boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
      }}
    >
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: '#f1f5f9' }}>
        {formattedLabel}
      </div>

      {naaimItem && typeof naaimItem.value === 'number' && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
          <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
            <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: NAAIM_COLOR, marginRight: 6 }} />
            NAAIM
          </span>
          <span style={{ fontWeight: 500, color: NAAIM_COLOR }}>
            {naaimItem.value.toFixed(2)}
          </span>
        </div>
      )}

      {spItem && typeof spItem.value === 'number' && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
          <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
            <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: SP500_COLOR, marginRight: 6 }} />
            S&P 500
          </span>
          <span style={{ fontWeight: 500, color: SP500_COLOR }}>
            {spItem.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </span>
        </div>
      )}
    </div>
  )
}

export default function NaaimChart() {
  const { data: apiData, isLoading } = useNaaimData()
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(2)

  const chartData = useMemo(() => {
    if (!apiData?.data) return []
    return apiData.data
      .map((d) => ({
        date: d.date,
        naaim_number: d.naaim_number,
        sp500: d.sp500 ?? null,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [apiData])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    if (selectedPeriod === 'default') {
      // デフォルト: 3年
      const cutoff = new Date()
      cutoff.setFullYear(cutoff.getFullYear() - 3)
      const cutoffStr = cutoff.toISOString().slice(0, 10)
      return chartData.filter((d) => d.date >= cutoffStr)
    }
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 3
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  if (isLoading) {
    return (
      <ChartContainer title="NAAIM Exposure Index" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (!apiData || chartData.length === 0) {
    return (
      <ChartContainer title="NAAIM Exposure Index" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = apiData.latest

  return (
    <ChartContainer
      title="NAAIM Exposure Index"
      dataSource="NAAIM"
      sourceUrl="https://naaim.org/programs/naaim-exposure-index/"
      showPeriodSelector={false}
    >
      {/* 最新値表示 */}
      {latest && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            marginBottom: 12,
            padding: '10px 14px',
            background: DARK_THEME.bgTertiary,
            borderRadius: 8,
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>最新値</Text>
            <Text
              style={{ color: NAAIM_COLOR, fontSize: 22, fontWeight: 700 }}
              className="tabular-nums"
            >
              {latest.naaim_number.toFixed(2)}
            </Text>
          </div>

          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>
            ({latest.date})
          </Text>
        </div>
      )}

      {/* データ比較ボタン */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            size="small"
            onClick={() => window.open('/compare?s=naaim_exposure', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 期間選択 */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* チャート */}
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart
          data={filteredData}
          margin={{ top: 16, right: 8, bottom: 0, left: 0 }}
          style={{ backgroundColor: DARK_THEME.chartBg }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />

          {/* 基準線 */}
          <ReferenceLine yAxisId="left" y={100} stroke="#94a3b8" strokeDasharray="6 3" strokeWidth={1} />
          <ReferenceLine yAxisId="left" y={50} stroke="#475569" strokeDasharray="3 3" strokeWidth={0.5} />

          <XAxis
            type="category"
            dataKey="date"
            tickFormatter={formatMonthLabel}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            tickMargin={16}
            height={60}
            interval="preserveStartEnd"
          />
          <YAxis
            yAxisId="left"
            domain={[0, 125]}
            ticks={[0, 25, 50, 75, 100, 125]}
            tickFormatter={(v: number) => `${v}`}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: NAAIM_COLOR, fontSize: 11 }}
            tickMargin={8}
            label={{ value: 'NAAIM', angle: -90, position: 'insideLeft', offset: -8, fill: NAAIM_COLOR, fontSize: 11 }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={['dataMin', 'dataMax']}
            tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}K` : `${v}`}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: SP500_COLOR, fontSize: 11 }}
            tickMargin={8}
            label={{ value: 'S&P 500', angle: 90, position: 'insideRight', offset: -4, fill: SP500_COLOR, fontSize: 11 }}
          />

          <RechartsTooltip content={<CustomTooltip />} />

          <Legend
            wrapperStyle={{ paddingTop: 8 }}
          />

          <Line
            type="monotone"
            dataKey="naaim_number"
            stroke={NAAIM_COLOR}
            strokeWidth={1.5}
            dot={false}
            name="NAAIM Exposure Index"
            yAxisId="left"
            connectNulls
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="sp500"
            stroke={SP500_COLOR}
            strokeWidth={1.5}
            dot={false}
            name="S&P 500"
            yAxisId="right"
            connectNulls
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
