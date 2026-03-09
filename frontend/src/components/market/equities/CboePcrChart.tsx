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
import { formatDayLabel } from '../../../utils/dateFormatters'
import { useHiddenSeries } from '../../country/usa/common/useChartData'

const { Text } = Typography

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

const COLOR_PCR = '#f59e0b'
const COLOR_PCR_10MA = '#ef4444'
const COLOR_SP500 = '#3b82f6'

interface PcrItem {
  date: string
  pcr: number | null
  pcr_10ma: number | null
  sp500: number | null
}

interface PcrResponse {
  data: PcrItem[]
  latest: PcrItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

function usePcrData() {
  return useQuery({
    queryKey: ['market', 'cboe-pcr'],
    queryFn: async () => {
      const { data } = await axios.get<PcrResponse>('/api/market/cboe-pcr')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

type SeriesKey = 'pcr' | 'pcr_10ma' | 'sp500'

const SERIES_CONFIG: { key: SeriesKey; label: string; color: string }[] = [
  { key: 'pcr', label: 'Put/Call Ratio', color: COLOR_PCR },
  { key: 'pcr_10ma', label: '10日移動平均', color: COLOR_PCR_10MA },
  { key: 'sp500', label: 'S&P 500', color: COLOR_SP500 },
]

function CustomTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null

  const formattedLabel = formatDayLabel(String(label))

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

      {SERIES_CONFIG.map(({ key, label: seriesLabel, color }) => {
        if (hiddenSeries.has(key)) return null
        const item = payload.find((p: { dataKey: string }) => p.dataKey === key)
        if (!item || typeof item.value !== 'number') return null

        const formatted = key === 'sp500'
          ? item.value.toLocaleString(undefined, { maximumFractionDigits: 0 })
          : item.value.toFixed(2)

        return (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: color, marginRight: 6 }} />
              {seriesLabel}
            </span>
            <span style={{ fontWeight: 500, color }}>
              {formatted}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export default function CboePcrChart() {
  const { data: apiData, isLoading, error } = usePcrData()
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(2)
  const { hiddenSeries, handleLegendClick, isHidden } = useHiddenSeries<SeriesKey>()

  const chartData = useMemo(() => {
    if (!apiData?.data) return []
    return apiData.data
      .map((d) => ({
        date: d.date,
        pcr: d.pcr,
        pcr_10ma: d.pcr_10ma,
        sp500: d.sp500,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [apiData])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 2
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  if (isLoading) {
    return (
      <ChartContainer title="CBOE Total Put/Call Ratio" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (error || !apiData || chartData.length === 0) {
    return (
      <ChartContainer title="CBOE Total Put/Call Ratio" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = apiData.latest

  return (
    <ChartContainer
      title="CBOE Total Put/Call Ratio"
      dataSource="CBOE / yfinance"
      sourceUrl="https://www.cboe.com/us/options/market_statistics/daily/"
      showPeriodSelector={false}
    >
      {/* 最新値 */}
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
          {SERIES_CONFIG.map(({ key, label, color }) => {
            const val = latest[key]
            if (val == null) return null
            const formatted = key === 'sp500'
              ? val.toLocaleString(undefined, { maximumFractionDigits: 0 })
              : val.toFixed(2)

            return (
              <div
                key={key}
                style={{
                  display: 'flex',
                  alignItems: 'baseline',
                  gap: 6,
                  opacity: isHidden(key) ? 0.3 : 1,
                  cursor: 'pointer',
                }}
                onClick={() => handleLegendClick(key)}
              >
                <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>{label}</Text>
                <Text
                  style={{ color, fontSize: 16, fontWeight: 700 }}
                  className="tabular-nums"
                >
                  {formatted}
                </Text>
              </div>
            )
          })}

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
            onClick={() => window.open('/compare?s=cboe_total_put_call_ratios', '_blank')}
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
          margin={{ top: 16, right: 16, bottom: 0, left: 0 }}
          style={{ backgroundColor: DARK_THEME.chartBg }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />

          <XAxis
            type="category"
            dataKey="date"
            tickFormatter={formatDayLabel}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            tickMargin={16}
            height={60}
            interval="preserveStartEnd"
          />

          {/* 左Y軸: Put/Call Ratio */}
          <YAxis
            yAxisId="left"
            domain={['dataMin - 0.1', 'dataMax + 0.1']}
            tickFormatter={(v: number) => v.toFixed(1)}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            tickMargin={8}
          />

          {/* 右Y軸: S&P 500 */}
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={['dataMin - 200', 'dataMax + 200']}
            tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}K` : `${v}`}
            axisLine={{ stroke: COLOR_SP500 }}
            tickLine={{ stroke: COLOR_SP500 }}
            tick={{ fill: COLOR_SP500, fontSize: 11 }}
            tickMargin={4}
            width={45}
          />

          {/* 基準線: 1.1（高水準） */}
          <ReferenceLine yAxisId="left" y={1.1} stroke="#ef4444" strokeDasharray="6 3" strokeWidth={1.5} label={{ value: '1.1', position: 'left', fill: '#ef4444', fontSize: 11 }} />
          {/* 基準線: 0.8（低水準） */}
          <ReferenceLine yAxisId="left" y={0.8} stroke="#22c55e" strokeDasharray="6 3" strokeWidth={1.5} label={{ value: '0.8', position: 'left', fill: '#22c55e', fontSize: 11 }} />

          <RechartsTooltip content={<CustomTooltip hiddenSeries={hiddenSeries} />} />

          <Legend
            wrapperStyle={{ paddingTop: 8 }}
            onClick={(e) => handleLegendClick(e.dataKey as string)}
            formatter={(value: string, entry) => (
              <span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : DARK_THEME.textPrimary }}>
                {value}
              </span>
            )}
          />

          <Line
            type="monotone"
            dataKey="pcr"
            stroke={COLOR_PCR}
            strokeWidth={1}
            dot={false}
            name="Put/Call Ratio"
            yAxisId="left"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('pcr')}
          />
          <Line
            type="monotone"
            dataKey="pcr_10ma"
            stroke={COLOR_PCR_10MA}
            strokeWidth={2}
            dot={false}
            name="10日移動平均"
            yAxisId="left"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('pcr_10ma')}
          />
          <Line
            type="monotone"
            dataKey="sp500"
            stroke={COLOR_SP500}
            strokeWidth={1.5}
            dot={false}
            name="S&P 500"
            yAxisId="right"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('sp500')}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
