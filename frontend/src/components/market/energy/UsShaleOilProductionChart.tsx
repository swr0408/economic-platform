import { useState, useMemo } from 'react'
import { Tabs, Tooltip, Button } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import {
  ComposedChart,
  Line,
  Bar,
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
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS, CHART_MARGIN } from '../../country/usa/common/chartConstants'
import MarketImpactTab from '../../indicator/MarketImpactTab'

const DARK_THEME = {
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  gridLine: '#475569',
  axisLine: '#64748b',
  tooltipBg: '#334155',
  tooltipBorder: '#475569',
  chartBg: '#1e293b',
}

// Formation colors (similar to MacroMicro reference image)
const COLORS = {
  permian: '#3b82f6',       // Blue (largest)
  eagle_ford: '#ef4444',    // Red
  bakken: '#f59e0b',        // Amber
  niobrara: '#10b981',      // Green
  austin_chalk: '#06b6d4',  // Cyan
  mississippian: '#8b5cf6', // Purple
  woodford: '#ec4899',      // Pink
  other: '#94a3b8',         // Gray
  total: '#ffffff',         // White (line)
}

interface ShaleItem {
  date: string
  total: number | null
  permian: number | null
  bakken: number | null
  eagle_ford: number | null
  niobrara: number | null
  austin_chalk: number | null
  mississippian: number | null
  woodford: number | null
  other: number | null
}

interface ShaleResponse {
  data: ShaleItem[]
  latest: ShaleItem | null
  next_release: { date: string; label?: string; time_jst?: string } | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

type ActiveTab = 'timeseries' | 'market_impact'

type FormationKey = 'permian' | 'bakken' | 'eagle_ford' | 'niobrara' | 'austin_chalk' | 'mississippian' | 'woodford' | 'other'
type SeriesKey = FormationKey | 'total'

interface FormationConfig {
  key: FormationKey
  label: string
  color: string
}

const FORMATIONS: FormationConfig[] = [
  { key: 'permian', label: 'Permian', color: COLORS.permian },
  { key: 'eagle_ford', label: 'Eagle Ford', color: COLORS.eagle_ford },
  { key: 'bakken', label: 'Bakken', color: COLORS.bakken },
  { key: 'niobrara', label: 'Niobrara', color: COLORS.niobrara },
  { key: 'austin_chalk', label: 'Austin Chalk', color: COLORS.austin_chalk },
  { key: 'mississippian', label: 'Mississippian', color: COLORS.mississippian },
  { key: 'woodford', label: 'Woodford', color: COLORS.woodford },
  { key: 'other', label: 'Other', color: COLORS.other },
]

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ChartTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatMonthLabel(String(label))
  const dp = payload[0]?.payload as ShaleItem | undefined
  if (!dp) return null

  return (
    <div style={{
      backgroundColor: DARK_THEME.tooltipBg,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>{formattedLabel}</div>
      {!hiddenSeries.has('total') && dp.total != null && (
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, marginBottom: 4, fontSize: 13, borderBottom: '1px solid #475569', paddingBottom: 4 }}>
          <span style={{ color: COLORS.total }}>Total</span>
          <span style={{ fontWeight: 600, color: COLORS.total }}>{dp.total.toFixed(2)} mb/d</span>
        </div>
      )}
      {FORMATIONS.map(({ key, label: fLabel, color }) => {
        if (hiddenSeries.has(key)) return null
        const val = dp[key]
        if (val == null) return null
        return (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, marginBottom: 2, fontSize: 12 }}>
            <span style={{ display: 'flex', alignItems: 'center' }}>
              <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, backgroundColor: color, marginRight: 6 }} />
              <span style={{ color: DARK_THEME.textPrimary }}>{fLabel}</span>
            </span>
            <span style={{ color, fontWeight: 500 }}>{val.toFixed(3)}</span>
          </div>
        )
      })}
    </div>
  )
}


export default function UsShaleOilProductionChart() {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)
  const [activeTab, setActiveTab] = useState<ActiveTab>('timeseries')
  const { hiddenSeries, handleLegendClick, isHidden } = useHiddenSeries<SeriesKey>()

  const { data: response } = useQuery<ShaleResponse>({
    queryKey: ['shale-oil-production'],
    queryFn: async () => {
      const res = await axios.get('/api/market/shale-oil-production')
      return res.data
    },
    staleTime: 1000 * 60 * 30,
  })

  const filteredData = useMemo(() => {
    if (!response?.data) return []
    if (currentPeriod === 'all') return response.data
    const years = typeof currentPeriod === 'number' ? currentPeriod : 5
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return response.data.filter(d => d.date >= cutoffStr)
  }, [response, currentPeriod])

  const latest = response?.latest
  const nextRelease = response?.next_release

  return (
    <ChartContainer
      title="米国シェールオイル生産量"
      dataSource="EIA STEO"
      sourceUrl="https://www.eia.gov/outlooks/steo/"
      showPeriodSelector={false}
    >
      {/* Latest value box */}
      <div style={LATEST_VALUE_BOX_STYLE}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          {latest?.date && (
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
              {latest.date.slice(0, 7).replace('-', '/')}
            </span>
          )}
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>Total: </span>
            <span style={{ fontSize: 20, fontWeight: 'bold', color: COLORS.total }}>
              {latest?.total != null ? `${latest.total.toFixed(2)} mb/d` : '—'}
            </span>
          </div>
          {FORMATIONS.slice(0, 4).map(({ key, label, color }) => {
            const val = latest?.[key]
            if (val == null) return null
            return (
              <div key={key}>
                <span style={{ fontSize: 11, color: TEXT_COLORS.secondary }}>{label}: </span>
                <span style={{ fontSize: 14, fontWeight: 'bold', color }}>{val.toFixed(2)}</span>
              </div>
            )
          })}
        </div>
        {nextRelease && (
          <span style={{ fontSize: 11, color: TEXT_COLORS.secondary, whiteSpace: 'nowrap' }}>
            次回: {nextRelease.date}{nextRelease.time_jst && ` ${nextRelease.time_jst} JST`}
          </span>
        )}
      </div>

      {/* Tabs */}
      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as ActiveTab)}
        style={{ marginTop: 8 }}
        items={[
          {
            key: 'timeseries',
            label: '時系列',
            children: (
              <>
                {/* データ比較ボタン */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
                  <Tooltip title="比較ページを開く">
                    <Button
                      icon={<AreaChartOutlined />}
                      onClick={() => window.open('/compare?s=us_shale_oil_production', '_blank')}
                    >
                      データ比較
                    </Button>
                  </Tooltip>
                </div>

                <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                <ResponsiveContainer width="100%" height={450}>
                  <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                    <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
                    <XAxis
                      dataKey="date"
                      tickFormatter={formatMonthLabel}
                      stroke={DARK_THEME.axisLine}
                      tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
                      minTickGap={40}
                    />
                    <YAxis
                      yAxisId="left"
                      domain={['dataMin - 0', 'dataMax + 0.3']}
                      tickFormatter={(v: number) => `${v.toFixed(0)}`}
                      stroke={DARK_THEME.textSecondary}
                      tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
                      width={40}
                      // label={{ value: 'mb/d', position: 'top', offset: 8, style: { fill: DARK_THEME.textSecondary, fontSize: 10 } }}
                    />

                    <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} />} />

                    <Legend
                      wrapperStyle={{ paddingTop: 8 }}
                      onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)}
                      formatter={(value: string, entry: any) => (
                        <span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : DARK_THEME.textPrimary, fontSize: 12 }}>
                          {value}
                        </span>
                      )}
                    />

                    {/* Stacked bars for formations */}
                    {FORMATIONS.map(({ key, label, color }) => (
                      <Bar
                        key={key}
                        dataKey={key}
                        fill={color}
                        fillOpacity={0.85}
                        name={label}
                        yAxisId="left"
                        stackId="production"
                        isAnimationActive={false}
                        hide={isHidden(key)}
                      />
                    ))}

                    {/* Total line */}
                    <Line
                      type="monotone"
                      dataKey="total"
                      stroke={COLORS.total}
                      strokeWidth={2}
                      dot={false}
                      name="Total"
                      yAxisId="left"
                      connectNulls
                      isAnimationActive={false}
                      hide={isHidden('total')}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </>
            ),
          },
          {
            key: 'market_impact',
            label: 'マーケットインパクト',
            children: (
              <MarketImpactTab indicatorId="weekly_crude_oil_inventories" />
            ),
          },
        ]}
      />
    </ChartContainer>
  )
}
