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
import { formatMonthLabel } from '../../../utils/dateFormatters'
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

const COLOR_M2 = '#3b82f6'      // 中国M2 YoY (12M先行) - blue (参考実装に合わせて)
const COLOR_NIKKEI = '#ef4444'   // 日経平均 YoY - red

interface M2Item {
  date: string
  m2_yoy: number | null
}

interface M2Response {
  data: M2Item[]
  latest: M2Item | null
}

interface NikkeiYoyItem {
  date: string
  nikkei_yoy: number
  nikkei_close: number
}

interface NikkeiYoyResponse {
  data: NikkeiYoyItem[]
  latest: NikkeiYoyItem | null
}

interface ChartItem {
  date: string
  m2_yoy: number | null
  nikkei_yoy: number | null
}

type SeriesKey = 'm2_yoy' | 'nikkei_yoy'

const SERIES_CONFIG: { key: SeriesKey; label: string; color: string }[] = [
  { key: 'm2_yoy', label: '中国M2 YoY (12M先行)', color: COLOR_M2 },
  { key: 'nikkei_yoy', label: '日経平均 YoY', color: COLOR_NIKKEI },
]

function CustomTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null

  const formattedLabel = formatMonthLabel(String(label))

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

        return (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: color, marginRight: 6 }} />
              {seriesLabel}
            </span>
            <span style={{ fontWeight: 500, color }}>
              {item.value > 0 ? '+' : ''}{item.value.toFixed(1)}%
            </span>
          </div>
        )
      })}
    </div>
  )
}


export default function ChinaM2NikkeiYoyChart() {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(5)
  const { hiddenSeries, handleLegendClick, isHidden } = useHiddenSeries<SeriesKey>()

  // Fetch China M2
  const { data: m2Data, isLoading: m2Loading } = useQuery({
    queryKey: ['china', 'pboc', 'm1-m2'],
    queryFn: async () => {
      const { data } = await axios.get<M2Response>('/api/china/pboc/m1-m2')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })

  // Fetch Nikkei YoY (monthly)
  const { data: nikkeiData, isLoading: nikkeiLoading } = useQuery({
    queryKey: ['market', 'nikkei-yoy'],
    queryFn: async () => {
      const { data } = await axios.get<NikkeiYoyResponse>('/api/market/nikkei-yoy')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })

  const isLoading = m2Loading || nikkeiLoading

  // Merge: M2 (monthly, shifted 12 months forward) + Nikkei YoY (monthly)
  const chartData = useMemo(() => {
    if (!m2Data?.data || !nikkeiData?.data) return []

    // M2: shift 12 months forward (先行指標)
    // Original date "2020-01-31" → shifted to "2021-01" (YYYY-MM key)
    const m2ShiftedMap = new Map<string, number>()
    for (const item of m2Data.data) {
      if (item.m2_yoy == null) continue
      const dt = new Date(item.date)
      dt.setMonth(dt.getMonth() + 12) // 12ヶ月先にシフト
      const shiftedYm = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}`
      m2ShiftedMap.set(shiftedYm, item.m2_yoy)
    }

    // Nikkei: YYYY-MM → value map
    const nikkeiMap = new Map<string, number>()
    for (const item of nikkeiData.data) {
      const ym = item.date.slice(0, 7)
      nikkeiMap.set(ym, item.nikkei_yoy)
    }

    // Collect all unique YYYY-MM keys
    const allMonths = new Set<string>()
    m2ShiftedMap.forEach((_, k) => allMonths.add(k))
    nikkeiMap.forEach((_, k) => allMonths.add(k))

    const result: ChartItem[] = Array.from(allMonths)
      .sort()
      .map((ym) => ({
        date: `${ym}-01`, // YYYY-MM-01 for display
        m2_yoy: m2ShiftedMap.get(ym) ?? null,
        nikkei_yoy: nikkeiMap.get(ym) ?? null,
      }))
      // At least one series should have data
      .filter((d) => d.m2_yoy !== null || d.nikkei_yoy !== null)

    return result
  }, [m2Data, nikkeiData])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 5
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  // Latest values
  const latestM2 = m2Data?.latest?.m2_yoy ?? null
  const latestM2Date = m2Data?.latest?.date ?? null
  const latestNikkei = nikkeiData?.latest?.nikkei_yoy ?? null
  const latestNikkeiDate = nikkeiData?.latest?.date ?? null

  if (isLoading) {
    return (
      <ChartContainer title="中国M2前年比 / 日経平均前年比" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (chartData.length === 0) {
    return (
      <ChartContainer title="中国M2前年比 / 日経平均前年比" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  return (
    <ChartContainer
      title="中国M2前年比 / 日経平均前年比"
      dataSource="PBOC / yfinance"
      showPeriodSelector={false}
    >
      {/* 1. Latest values */}
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
        {latestM2 != null && (
          <div
            style={{
              display: 'flex',
              alignItems: 'baseline',
              gap: 6,
              opacity: isHidden('m2_yoy') ? 0.3 : 1,
              cursor: 'pointer',
            }}
            onClick={() => handleLegendClick('m2_yoy')}
          >
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>中国M2 YoY</Text>
            <Text style={{ color: COLOR_M2, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
              {latestM2 > 0 ? '+' : ''}{latestM2.toFixed(1)}%
            </Text>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>
              ({latestM2Date})
            </Text>
          </div>
        )}

        {latestNikkei != null && (
          <div
            style={{
              display: 'flex',
              alignItems: 'baseline',
              gap: 6,
              opacity: isHidden('nikkei_yoy') ? 0.3 : 1,
              cursor: 'pointer',
            }}
            onClick={() => handleLegendClick('nikkei_yoy')}
          >
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>日経平均 YoY</Text>
            <Text style={{ color: COLOR_NIKKEI, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
              {latestNikkei > 0 ? '+' : ''}{latestNikkei.toFixed(1)}%
            </Text>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>
              ({latestNikkeiDate})
            </Text>
          </div>
        )}
      </div>

      {/* 2. Compare button (right-aligned) */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            size="small"
            onClick={() => window.open('/compare?s=ch_m2_yoy&s=nikkei_yoy', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 3. Period selector */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* 4. Chart - 2 Y-axes */}
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart
          data={filteredData}
          margin={{ top: 16, right: 50, bottom: 0, left: 0 }}
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

          {/* Left Y-axis: 中国M2 YoY (12M先行) */}
          <YAxis
            yAxisId="left"
            domain={['dataMin - 0.5', 'dataMax + 0.5']}
            tickFormatter={(v: number) => `${v.toFixed(0)}%`}
            axisLine={{ stroke: COLOR_M2 }}
            tickLine={{ stroke: COLOR_M2 }}
            tick={{ fill: COLOR_M2, fontSize: 11 }}
            tickMargin={8}
          />

          {/* Right Y-axis: 日経平均 YoY */}
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={['dataMin - 1', 'dataMax + 1']}
            tickFormatter={(v: number) => `${v.toFixed(0)}%`}
            axisLine={{ stroke: COLOR_NIKKEI }}
            tickLine={{ stroke: COLOR_NIKKEI }}
            tick={{ fill: COLOR_NIKKEI, fontSize: 11 }}
            tickMargin={4}
            width={50}
          />

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
            dataKey="m2_yoy"
            stroke={COLOR_M2}
            strokeWidth={2}
            dot={false}
            name="中国M2 (12M先行)"
            yAxisId="left"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('m2_yoy')}
          />
          <Line
            type="monotone"
            dataKey="nikkei_yoy"
            stroke={COLOR_NIKKEI}
            strokeWidth={2}
            dot={false}
            name="日経平均"
            yAxisId="right"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('nikkei_yoy')}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
