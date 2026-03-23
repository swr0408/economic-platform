import { useState, useMemo } from 'react'
import { Typography, Tooltip, Button } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import {
  ComposedChart,
  Line,
  Area,
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

const COLOR_STRESS = '#ef4444'    // red - ストレス指数
const COLOR_SP500 = '#3b82f6'     // blue - S&P 500

interface FinancialStressIndexItem {
  date: string
  value: number | null
  sp500?: number | null
}

interface FinancialStressIndexResponse {
  data: FinancialStressIndexItem[]
  latest: FinancialStressIndexItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

function useFinancialStressIndexData() {
  return useQuery({
    queryKey: ['market', 'financial-stress-index'],
    queryFn: async () => {
      const { data } = await axios.get<FinancialStressIndexResponse>('/api/market/financial-stress-index')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

type SeriesKey = 'value' | 'sp500'

function StressTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))

  const tooltipSeries = [
    { key: 'value', label: 'STLFSI4', color: COLOR_STRESS, fmt: (v: number) => v.toFixed(4) },
    { key: 'sp500', label: 'S&P 500', color: COLOR_SP500, fmt: (v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 0 }) },
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

export default function FinancialStressIndexChart() {
  const { data: apiData, isLoading, error } = useFinancialStressIndexData()
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(5)
  const hiddenSeries = useHiddenSeries<SeriesKey>()

  const chartData = useMemo(() => {
    if (!apiData?.data) return []
    return apiData.data.sort((a, b) => a.date.localeCompare(b.date))
  }, [apiData])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 5
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  if (isLoading) {
    return (
      <ChartContainer title="金融ストレス指数（STLFSI4）" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (error || !apiData || chartData.length === 0) {
    return (
      <ChartContainer title="金融ストレス指数（STLFSI4）" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = apiData.latest

  return (
    <ChartContainer
      title="金融ストレス指数（STLFSI4）"
      dataSource="FRED"
      sourceUrl="https://fred.stlouisfed.org/series/STLFSI4"
      showPeriodSelector={false}
      handbookId="financial-stress-index"
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
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>STLFSI4</Text>
            <Text
              style={{
                color: (latest.value ?? 0) > 0 ? COLOR_STRESS : '#10b981',
                fontSize: 16,
                fontWeight: 700,
              }}
              className="tabular-nums"
            >
              {(latest.value ?? 0).toFixed(4)}
            </Text>
          </div>

          {latest.sp500 != null && (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>S&P 500</Text>
              <Text style={{ color: COLOR_SP500, fontSize: 13, fontWeight: 600 }} className="tabular-nums">
                {latest.sp500.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </Text>
            </div>
          )}

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
            onClick={() => window.open('/compare?s=financial_stress_index', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 期間選択 */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* 注釈 */}
      <div style={{ marginBottom: 8, padding: '6px 10px', background: 'rgba(239,68,68,0.08)', borderRadius: 6, fontSize: 11, color: DARK_THEME.textSecondary }}>
        0 = 歴史的平均水準。正値 = 金融ストレス増大（市場にとってネガティブ）、負値 = 平均以下のストレス（市場にとってポジティブ）
      </div>

      {/* チャート */}
      <ResponsiveContainer width="100%" height={450}>
        <ComposedChart
          data={filteredData}
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

          {/* 左Y軸: ストレス指数 */}
          <YAxis
            yAxisId="left"
            domain={['dataMin - 0.5', 'dataMax + 0.5']}
            tickFormatter={(v: number) => v.toFixed(1)}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: COLOR_STRESS, fontSize: 11 }}
            tickMargin={8}
            label={{ value: 'STLFSI4', angle: -90, position: 'insideLeft', offset: -8, fill: COLOR_STRESS, fontSize: 11 }}
          />

          {/* 右Y軸: S&P 500（反転）— ストレス上昇 ≒ 株価下落 */}
          <YAxis
            yAxisId="right"
            orientation="right"
            reversed
            domain={['dataMin * 0.9', 'dataMax * 1.1']}
            tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}K` : `${v}`}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: COLOR_SP500, fontSize: 11 }}
            tickMargin={8}
          />

          {/* ゼロライン */}
          <ReferenceLine yAxisId="left" y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />

          <RechartsTooltip content={<StressTooltip hiddenSeries={hiddenSeries.hiddenSeries} />} />

          <Legend
            wrapperStyle={{ paddingTop: 8 }}
            onClick={(e) => hiddenSeries.handleLegendClick(e.dataKey as string)}
            formatter={(value: string, entry) => (
              <span style={{ color: hiddenSeries.hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : DARK_THEME.textPrimary, fontSize: 11 }}>
                {value}
              </span>
            )}
          />

          {/* ストレス指数エリア（正値=赤、基準線付き） */}
          <Area
            type="monotone"
            dataKey="value"
            stroke={COLOR_STRESS}
            strokeWidth={2}
            fill={COLOR_STRESS}
            fillOpacity={0.1}
            dot={false}
            name="STLFSI4"
            yAxisId="left"
            connectNulls
            isAnimationActive={false}
            hide={hiddenSeries.isHidden('value')}
          />

          {/* S&P 500（右Y軸・反転） */}
          <Line
            type="monotone"
            dataKey="sp500"
            stroke={COLOR_SP500}
            strokeWidth={1.5}
            strokeDasharray="4 2"
            dot={false}
            name="S&P 500 (反転)"
            yAxisId="right"
            connectNulls
            isAnimationActive={false}
            hide={hiddenSeries.isHidden('sp500')}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
