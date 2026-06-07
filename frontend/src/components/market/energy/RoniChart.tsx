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
  ReferenceArea,
} from 'recharts'
import ChartContainer from '../../common/ChartContainer'
import PeriodSelector, { type PeriodValue } from '../../common/PeriodSelector'
import { formatMonthLabel } from '../../../utils/dateFormatters'
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS, CHART_MARGIN } from '../../country/usa/common/chartConstants'

const { Text } = Typography

const DARK_THEME = {
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  gridLine: '#475569',
  axisLine: '#64748b',
  tooltipBg: '#334155',
  tooltipBorder: '#475569',
  chartBg: '#1e293b',
}

const COLOR_RONI = '#06b6d4'  // Cyan

interface RoniItem {
  date: string
  value: number
  season: string
}

interface RoniResponse {
  data: RoniItem[]
  latest: RoniItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ChartTooltip({ active, payload, label }: {
  active?: boolean
  payload?: any[]
  label?: string
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatMonthLabel(String(label))
  const dp = payload[0]?.payload as RoniItem | undefined
  if (!dp) return null

  // El Niño / La Niña 判定
  let phase = '中立 (ENSO Neutral)'
  let phaseColor = DARK_THEME.textSecondary
  if (dp.value >= 0.5) { phase = 'エルニーニョ (El Niño)'; phaseColor = '#ef4444' }
  else if (dp.value <= -0.5) { phase = 'ラニーニャ (La Niña)'; phaseColor = '#3b82f6' }

  return (
    <div style={{
      backgroundColor: DARK_THEME.tooltipBg,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
        {formattedLabel} ({dp.season})
      </div>
      <div style={{ color: COLOR_RONI, fontSize: 13, marginBottom: 4 }}>
        RONI: {dp.value > 0 ? '+' : ''}{dp.value.toFixed(2)} °C
      </div>
      <div style={{ color: phaseColor, fontSize: 12 }}>
        {phase}
      </div>
    </div>
  )
}

export default function RoniChart() {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)

  const { data: response, isLoading } = useQuery<RoniResponse>({
    queryKey: ['market', 'roni'],
    queryFn: async () => {
      const res = await axios.get('/api/market/roni')
      return res.data
    },
    staleTime: 1000 * 60 * 30,
  })

  const filteredData = useMemo(() => {
    if (!response?.data?.length) return []
    if (currentPeriod === 'all') return response.data
    const years = typeof currentPeriod === 'number' ? currentPeriod : 10
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return response.data.filter(d => d.date >= cutoffStr)
  }, [response, currentPeriod])

  // Y軸ドメイン計算
  const yDomain = useMemo(() => {
    if (!filteredData.length) return [-2, 2]
    const vals = filteredData.map(d => d.value)
    const min = Math.min(...vals)
    const max = Math.max(...vals)
    return [Math.floor(min - 0.5), Math.ceil(max + 0.5)]
  }, [filteredData])

  if (isLoading) {
    return (
      <ChartContainer title="RONI (Relative Oceanic Niño Index)" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (!response || !response.data?.length) {
    return (
      <ChartContainer title="RONI (Relative Oceanic Niño Index)" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = response.latest

  // フェーズ判定
  let phaseLabel = '中立'
  let phaseColor = DARK_THEME.textSecondary
  if (latest && latest.value >= 0.5) { phaseLabel = 'エルニーニョ'; phaseColor = '#ef4444' }
  else if (latest && latest.value <= -0.5) { phaseLabel = 'ラニーニャ'; phaseColor = '#3b82f6' }

  return (
    <ChartContainer
      title="RONI (Relative Oceanic Niño Index)"
      dataSource="NOAA CPC"
      sourceUrl="https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/"
      showPeriodSelector={false}
      handbookId="roni"
    >
      {/* 最新値表示 */}
      <div style={LATEST_VALUE_BOX_STYLE}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          {latest?.date && (
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
              {latest.date.replace(/-/g, '/')} ({latest.season})
            </span>
          )}
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>RONI: </span>
            <span style={{ fontSize: 20, fontWeight: 'bold', color: COLOR_RONI }}>
              {latest ? `${latest.value > 0 ? '+' : ''}${latest.value.toFixed(2)}` : '—'} °C
            </span>
          </div>
          <Text style={{ fontSize: 13, fontWeight: 600, color: phaseColor }}>
            {phaseLabel}
          </Text>
        </div>
      </div>

      {/* データ比較ボタン */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            onClick={() => window.open('/compare?s=roni', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 期間選択 */}
      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

      {/* チャート */}
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart data={filteredData} margin={CHART_MARGIN}>
          <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />

          {/* El Niño / La Niña 帯域 */}
          <ReferenceArea yAxisId="left" y1={0.5} y2={yDomain[1]} fill="#ef4444" fillOpacity={0.06} />
          <ReferenceArea yAxisId="left" y1={yDomain[0]} y2={-0.5} fill="#3b82f6" fillOpacity={0.06} />

          {/* 閾値ライン */}
          <ReferenceLine yAxisId="left" y={0.5} stroke="#ef4444" strokeDasharray="4 4" strokeWidth={0.8} />
          <ReferenceLine yAxisId="left" y={-0.5} stroke="#3b82f6" strokeDasharray="4 4" strokeWidth={0.8} />
          <ReferenceLine yAxisId="left" y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />

          <XAxis
            dataKey="date"
            tickFormatter={formatMonthLabel}
            stroke={DARK_THEME.axisLine}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            minTickGap={40}
          />
          <YAxis
            yAxisId="left"
            domain={yDomain}
            tickFormatter={(v: number) => `${v > 0 ? '+' : ''}${v.toFixed(1)}`}
            stroke={DARK_THEME.axisLine}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            width={45}
          />

          <RechartsTooltip content={<ChartTooltip />} />

          <Legend
            wrapperStyle={{ paddingTop: 8 }}
            formatter={(value: string) => (
              <span style={{ color: DARK_THEME.textPrimary, fontSize: 12 }}>{value}</span>
            )}
          />

          <Line
            yAxisId="left"
            type="monotone"
            dataKey="value"
            name="RONI (°C)"
            stroke={COLOR_RONI}
            strokeWidth={1.5}
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* 凡例説明 */}
      <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 11, color: DARK_THEME.textSecondary }}>
        <span>
          <span style={{ color: '#ef4444' }}>+0.5以上</span> = エルニーニョ
        </span>
        <span>
          <span style={{ color: '#3b82f6' }}>-0.5以下</span> = ラニーニャ
        </span>
        <span>
          -0.5〜+0.5 = 中立
        </span>
      </div>
    </ChartContainer>
  )
}
