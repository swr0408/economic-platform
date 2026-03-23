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
import { LATEST_VALUE_BOX_STYLE, CHART_MARGIN } from '../../country/usa/common/chartConstants'

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

const COLOR_MARKET = '#ef4444'  // red - Market CMDI
const COLOR_IG = '#3b82f6'      // blue - IG CMDI
const COLOR_HY = '#f59e0b'      // amber - HY CMDI

interface CmdiItem {
  date: string
  market?: number | null
  ig?: number | null
  hy?: number | null
}

interface CmdiResponse {
  data: CmdiItem[]
  latest: CmdiItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

function useCmdiData() {
  return useQuery({
    queryKey: ['market', 'cmdi'],
    queryFn: async () => {
      const { data } = await axios.get<CmdiResponse>('/api/market/corporate-bond-market-distress-index')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

type SeriesKey = 'market' | 'ig' | 'hy'

function CmdiTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))

  const tooltipSeries = [
    { key: 'market', label: 'Market CMDI', color: COLOR_MARKET },
    { key: 'ig', label: 'IG CMDI', color: COLOR_IG },
    { key: 'hy', label: 'HY CMDI', color: COLOR_HY },
  ]

  return (
    <div style={{ backgroundColor: DARK_THEME.tooltipBg, border: `1px solid ${DARK_THEME.tooltipBorder}`, borderRadius: 8, padding: '12px 16px', boxShadow: '0 4px 16px rgba(0,0,0,0.3)' }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: '#f1f5f9' }}>{formattedLabel}</div>
      {tooltipSeries.map(({ key, label: seriesLabel, color }) => {
        if (hiddenSeries.has(key)) return null
        const item = payload.find((p: { dataKey: string }) => p.dataKey === key)
        if (!item || typeof item.value !== 'number') return null
        return (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: color, marginRight: 6 }} />
              {seriesLabel}
            </span>
            <span style={{ fontWeight: 500, color }}>{item.value.toFixed(4)}</span>
          </div>
        )
      })}
    </div>
  )
}

export default function CmdiChart() {
  const { data: apiData, isLoading, error } = useCmdiData()
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
      <ChartContainer title="企業債券市場ディストレス指数（CMDI）" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (error || !apiData || chartData.length === 0) {
    return (
      <ChartContainer title="企業債券市場ディストレス指数（CMDI）" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = apiData.latest

  return (
    <ChartContainer
      title="企業債券市場ディストレス指数（CMDI）"
      dataSource="NY Fed"
      sourceUrl="https://www.newyorkfed.org/research/interactives/cmdi"
      showPeriodSelector={false}
      handbookId="cmdi"
    >
      {/* 最新値 */}
      {latest && (
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>Market</Text>
              <Text style={{ color: COLOR_MARKET, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
                {(latest.market ?? 0).toFixed(4)}
              </Text>
            </div>

            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>IG</Text>
              <Text style={{ color: COLOR_IG, fontSize: 13, fontWeight: 600 }} className="tabular-nums">
                {(latest.ig ?? 0).toFixed(4)}
              </Text>
            </div>

            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>HY</Text>
              <Text style={{ color: COLOR_HY, fontSize: 13, fontWeight: 600 }} className="tabular-nums">
                {(latest.hy ?? 0).toFixed(4)}
              </Text>
            </div>

            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>
              ({latest.date})
            </Text>
          </div>
        </div>
      )}

      {/* データ比較ボタン */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            size="small"
            onClick={() => window.open('/compare?s=cmdi_market&s=cmdi_ig&s=cmdi_hy', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 期間選択 */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* チャート */}
      <ResponsiveContainer width="100%" height={450}>
        <ComposedChart
          data={filteredData}
          margin={CHART_MARGIN}
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

          <YAxis
            domain={[0, 'dataMax + 0.05']}
            tickFormatter={(v: number) => v.toFixed(2)}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            tickMargin={8}
          />

          <RechartsTooltip content={<CmdiTooltip hiddenSeries={hiddenSeries.hiddenSeries} />} />

          <Legend
            wrapperStyle={{ paddingTop: 8 }}
            onClick={(e) => hiddenSeries.handleLegendClick(e.dataKey as string)}
            formatter={(value: string, entry) => (
              <span style={{ color: hiddenSeries.hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : DARK_THEME.textPrimary, fontSize: 11 }}>
                {value}
              </span>
            )}
          />

          <Line
            type="monotone"
            dataKey="market"
            stroke={COLOR_MARKET}
            strokeWidth={2}
            dot={false}
            name="Market CMDI"
            connectNulls
            isAnimationActive={false}
            hide={hiddenSeries.isHidden('market')}
          />

          <Line
            type="monotone"
            dataKey="ig"
            stroke={COLOR_IG}
            strokeWidth={1.5}
            dot={false}
            name="IG CMDI"
            connectNulls
            isAnimationActive={false}
            hide={hiddenSeries.isHidden('ig')}
          />

          <Line
            type="monotone"
            dataKey="hy"
            stroke={COLOR_HY}
            strokeWidth={1.5}
            dot={false}
            name="HY CMDI"
            connectNulls
            isAnimationActive={false}
            hide={hiddenSeries.isHidden('hy')}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
