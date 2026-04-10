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
} from 'recharts'
import ChartContainer from '../../common/ChartContainer'
import PeriodSelector, { type PeriodValue } from '../../common/PeriodSelector'
import { formatMonthLabel, formatDayLabel } from '../../../utils/dateFormatters'
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

const COLOR_RATIO = '#f59e0b'    // amber - レシオ
const COLOR_MA = '#ffffff'        // white - 移動平均
const COLOR_R2000 = '#3b82f6'    // blue - Russell 2000

interface Russell2000Russell1000Item {
  date: string
  russell2000: number | null
  russell1000: number | null
  ratio: number | null
}

interface Russell2000Russell1000Response {
  data: Russell2000Russell1000Item[]
  latest: Russell2000Russell1000Item | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

function useRussell2000Russell1000Data() {
  return useQuery({
    queryKey: ['market', 'russell2000-russell1000'],
    queryFn: async () => {
      const { data } = await axios.get<Russell2000Russell1000Response>('/api/market/russell2000-russell1000')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

type SeriesKey = 'ratio' | 'ma' | 'russell2000'

function computeMA(data: { ratio: number | null }[], window: number): (number | null)[] {
  if (window <= 0) return data.map(() => null)
  const result: (number | null)[] = []
  for (let i = 0; i < data.length; i++) {
    if (i < window - 1) { result.push(null); continue }
    let sum = 0; let count = 0
    for (let j = i - window + 1; j <= i; j++) {
      if (data[j].ratio != null) { sum += data[j].ratio!; count++ }
    }
    result.push(count === window ? sum / count : null)
  }
  return result
}

const MA_WINDOW = 20

function RatioTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))

  const tooltipSeries = [
    { key: 'ratio', label: 'R2000/R1000', color: COLOR_RATIO, fmt: (v: number) => v.toFixed(4) },
    { key: 'ma', label: `${MA_WINDOW}MA`, color: COLOR_MA, fmt: (v: number) => v.toFixed(4) },
    { key: 'russell2000', label: 'Russell 2000', color: COLOR_R2000, fmt: (v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 0 }) },
  ]

  return (
    <div style={{ backgroundColor: DARK_THEME.tooltipBg, border: `1px solid ${DARK_THEME.tooltipBorder}`, borderRadius: 8, padding: '12px 16px', boxShadow: '0 4px 16px rgba(0,0,0,0.3)' }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: '#f1f5f9' }}>{formattedLabel}</div>
      {tooltipSeries.map(({ key, label: seriesLabel, color, fmt }) => {
        if (hiddenSeries.has(key)) return null
        const item = payload.find((p: { dataKey: string }) => p.dataKey === key)
        if (!item || typeof item.value !== 'number') return null
        return (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: color, marginRight: 6 }} />
              {seriesLabel}
            </span>
            <span style={{ fontWeight: 500, color }}>{fmt(item.value)}</span>
          </div>
        )
      })}
    </div>
  )
}

export default function Russell2000Russell1000Chart() {
  const { data: apiData, isLoading, error } = useRussell2000Russell1000Data()
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(2)
  const hiddenSeries = useHiddenSeries<SeriesKey>()

  const chartData = useMemo(() => {
    if (!apiData?.data) return []
    return apiData.data.sort((a, b) => a.date.localeCompare(b.date))
  }, [apiData])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 2
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  const viewData = useMemo(() => {
    const fullRatioData = chartData.map((d) => ({ ratio: d.ratio ?? null }))
    const maValues = computeMA(fullRatioData, MA_WINDOW)
    const startIdx = chartData.length - filteredData.length

    return filteredData.map((d, i) => ({
      date: d.date,
      ratio: d.ratio ?? null,
      ma: maValues[startIdx + i] ?? null,
      russell2000: d.russell2000 ?? null,
    }))
  }, [chartData, filteredData])

  if (isLoading) {
    return (
      <ChartContainer title="Russell 2000 / Russell 1000 レシオ" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (error || !apiData || chartData.length === 0) {
    return (
      <ChartContainer title="Russell 2000 / Russell 1000 レシオ" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = apiData.latest

  return (
    <ChartContainer
      title="Russell 2000 / Russell 1000 レシオ"
      dataSource="cboe"
      sourceUrl="https://www.cboe.com/"
      showPeriodSelector={false}
      handbookId="russell2000-russell1000"
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
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>R2000/R1000</Text>
            <Text style={{ color: COLOR_RATIO, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
              {(latest.ratio ?? 0).toFixed(4)}
            </Text>
          </div>

          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>Russell 2000</Text>
            <Text style={{ color: COLOR_R2000, fontSize: 13, fontWeight: 600 }} className="tabular-nums">
              {(latest.russell2000 ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </Text>
          </div>

          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>Russell 1000</Text>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 13, fontWeight: 600 }} className="tabular-nums">
              {(latest.russell1000 ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </Text>
          </div>

          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>
            ({latest.date})
          </Text>
        </div>
      )}

      {/* データ比較ボタン */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            size="small"
            onClick={() => window.open('/compare?s=russell2000_russell1000', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 期間選択 */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* 注釈 */}
      <div style={{ marginBottom: 8, padding: '6px 10px', background: 'rgba(245,158,11,0.08)', borderRadius: 6, fontSize: 11, color: DARK_THEME.textSecondary }}>
        小型株 / 大型株 レシオ — レシオ上昇 = 小型株優位 (リスクオン), 下降 = 大型株優位 (リスクオフ)
      </div>

      {/* チャート */}
      <ResponsiveContainer width="100%" height={450}>
        <ComposedChart
          data={viewData}
          margin={{ top: 16, right: 8, bottom: 0, left: 0 }}
          style={{ backgroundColor: DARK_THEME.chartBg }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />

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

          {/* 左Y軸: レシオ */}
          <YAxis
            yAxisId="left"
            domain={['dataMin * 0.95', 'dataMax * 1.05']}
            tickFormatter={(v: number) => v.toFixed(2)}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: COLOR_RATIO, fontSize: 11 }}
            tickMargin={8}
            label={{ value: 'R2000/R1000', angle: -90, position: 'insideLeft', offset: -8, fill: COLOR_RATIO, fontSize: 11 }}
          />

          {/* 右Y軸: Russell 2000 */}
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={['dataMin', 'dataMax']}
            tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}K` : `${v}`}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: COLOR_R2000, fontSize: 11 }}
            tickMargin={8}
          />

          <RechartsTooltip content={<RatioTooltip hiddenSeries={hiddenSeries.hiddenSeries} />} />

          <Legend
            wrapperStyle={{ paddingTop: 8 }}
            onClick={(e) => hiddenSeries.handleLegendClick(e.dataKey as string)}
            formatter={(value: string, entry) => (
              <span style={{ color: hiddenSeries.hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : DARK_THEME.textPrimary, fontSize: 11 }}>
                {value}
              </span>
            )}
          />

          {/* レシオ線 */}
          <Line type="monotone" dataKey="ratio" stroke={COLOR_RATIO} strokeWidth={2} dot={false} name="R2000/R1000" yAxisId="left" connectNulls isAnimationActive={false} hide={hiddenSeries.isHidden('ratio')} />

          {/* MA線 */}
          <Line type="monotone" dataKey="ma" stroke={COLOR_MA} strokeWidth={1.5} strokeDasharray="4 2" dot={false} name={`${MA_WINDOW}MA`} yAxisId="left" connectNulls isAnimationActive={false} hide={hiddenSeries.isHidden('ma')} />

          {/* Russell 2000（右Y軸） */}
          <Line type="monotone" dataKey="russell2000" stroke={COLOR_R2000} strokeWidth={1.5} strokeDasharray="4 2" dot={false} name="Russell 2000" yAxisId="right" connectNulls isAnimationActive={false} hide={hiddenSeries.isHidden('russell2000')} />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
