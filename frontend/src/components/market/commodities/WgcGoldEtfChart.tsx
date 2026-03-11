import { useState, useMemo } from 'react'
import { Typography, Tooltip, Button } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import {
  ComposedChart,
  Line,
  Bar,
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
import { formatMonthLabel } from '../../../utils/dateFormatters'
import { useHiddenSeries } from '../../country/usa/common/useChartData'
import { ViewModeButtonGroup } from '../../country/usa/common/ChartComponents'

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

// 11カ国カラーパレット
const COUNTRY_CONFIG: { key: CountryKey; label: string; color: string }[] = [
  { key: 'us', label: '米国', color: '#215785' },
  { key: 'uk', label: '英国', color: '#64c8ff' },
  { key: 'germany', label: 'ドイツ', color: '#00d296' },
  { key: 'switzerland', label: 'スイス', color: '#ff6b6b' },
  { key: 'japan', label: '日本', color: '#fbbf24' },
  { key: 'china', label: '中国', color: '#f97316' },
  { key: 'india', label: 'インド', color: '#a78bfa' },
  { key: 'australia', label: '豪州', color: '#34d399' },
  { key: 'canada', label: 'カナダ', color: '#f472b6' },
  { key: 'south_africa', label: '南アフリカ', color: '#704287' },
  { key: 'hong_kong', label: '香港', color: '#06b6d4' },
]

const COLOR_GOLD = '#d8ab4c'

type CountryKey = 'us' | 'uk' | 'germany' | 'switzerland' | 'japan' | 'china' | 'india' | 'australia' | 'canada' | 'south_africa' | 'hong_kong'
type SeriesKey = CountryKey | 'gold_price_usd'

interface WgcDataItem {
  date: string
  us: number | null
  uk: number | null
  germany: number | null
  switzerland: number | null
  japan: number | null
  china: number | null
  india: number | null
  australia: number | null
  canada: number | null
  south_africa: number | null
  hong_kong: number | null
  total: number | null
  gold_price_usd: number | null
}

interface WgcResponse {
  data: WgcDataItem[]
  data_type: string
  latest: WgcDataItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

type ViewMode = 'holdings' | 'flows'
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'holdings', label: '保有残高' },
  { mode: 'flows', label: 'フロー' },
]

const COUNTRY_LABELS: Record<CountryKey, string> = {} as Record<CountryKey, string>
const COUNTRY_COLORS: Record<CountryKey, string> = {} as Record<CountryKey, string>
const COUNTRY_KEYS: CountryKey[] = []
for (const c of COUNTRY_CONFIG) {
  COUNTRY_LABELS[c.key] = c.label
  COUNTRY_COLORS[c.key] = c.color
  COUNTRY_KEYS.push(c.key)
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function WgcTooltip({ active, payload, label, hiddenSeries, viewMode }: {
  active?: boolean
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
  viewMode: ViewMode
}) {
  if (!active || !payload || payload.length === 0) return null
  const dateStr = String(label)
  // 月末日付（月次）→ YYYY/MM、それ以外（週次暫定）→ YYYY/MM/DD
  const day = parseInt(dateStr.slice(8, 10), 10)
  const month = parseInt(dateStr.slice(5, 7), 10)
  const isMonthEnd = (day >= 28 && month !== 2) || (day >= 27)
  const formattedLabel = isMonthEnd ? formatMonthLabel(dateStr) : dateStr.replace(/-/g, '/')
  const dataPoint = payload[0]?.payload as WgcDataItem | undefined

  const unit = viewMode === 'holdings' ? ' トン' : ' US$mn'

  // ソート: 値の大きい順（holdingsは降順、flowsは絶対値降順）
  const visibleCountries = COUNTRY_KEYS
    .filter(c => !hiddenSeries.has(c))
    .filter(c => {
      const val = dataPoint?.[c]
      return typeof val === 'number'
    })
    .sort((a, b) => {
      const va = dataPoint?.[a] ?? 0
      const vb = dataPoint?.[b] ?? 0
      if (viewMode === 'flows') return Math.abs(vb) - Math.abs(va)
      return vb - va
    })

  return (
    <div style={{
      backgroundColor: DARK_THEME.tooltipBg,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
      maxHeight: 400,
      overflowY: 'auto',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: '#f1f5f9' }}>{formattedLabel}</div>
      {visibleCountries.map(country => {
        const val = dataPoint?.[country]
        if (typeof val !== 'number') return null
        return (
          <div key={country} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3, fontSize: 12 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, backgroundColor: COUNTRY_COLORS[country], marginRight: 5 }} />
              {COUNTRY_LABELS[country]}
            </span>
            <span style={{ fontWeight: 500, color: COUNTRY_COLORS[country], fontVariantNumeric: 'tabular-nums' }}>
              {viewMode === 'flows' ? `${val >= 0 ? '+' : ''}${val.toLocaleString(undefined, { maximumFractionDigits: 1 })}` : val.toLocaleString(undefined, { maximumFractionDigits: 1 })}{unit}
            </span>
          </div>
        )
      })}
      {!hiddenSeries.has('gold_price_usd') && (() => {
        const val = dataPoint?.gold_price_usd
        if (typeof val !== 'number') return null
        return (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3, fontSize: 12 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, backgroundColor: COLOR_GOLD, marginRight: 5 }} />
              金価格
            </span>
            <span style={{ fontWeight: 500, color: COLOR_GOLD }}>${val.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
          </div>
        )
      })()}
      {/* Total */}
      {(() => {
        const total = dataPoint?.total
        if (typeof total !== 'number') return null
        const visible = COUNTRY_KEYS.filter(c => !hiddenSeries.has(c))
        if (visible.length < 2) return null
        return (
          <div style={{ borderTop: '1px solid #475569', marginTop: 4, paddingTop: 4, display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
            <span style={{ color: '#f1f5f9' }}>合計</span>
            <span style={{ fontWeight: 600, color: '#f1f5f9' }}>
              {viewMode === 'flows' ? `${total >= 0 ? '+' : ''}${total.toLocaleString(undefined, { maximumFractionDigits: 1 })}` : total.toLocaleString(undefined, { maximumFractionDigits: 1 })}{unit}
            </span>
          </div>
        )
      })()}
    </div>
  )
}


export default function WgcGoldEtfChart() {
  const [viewMode, setViewMode] = useState<ViewMode>('holdings')
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(5)
  const { hiddenSeries, handleLegendClick, isHidden } = useHiddenSeries<SeriesKey>()

  const dataType = viewMode === 'holdings' ? 'holdings_ton' : 'flows_usd'

  const { data: wgcData, isLoading } = useQuery({
    queryKey: ['market', 'wgc-gold-etf', dataType],
    queryFn: async () => {
      const { data } = await axios.get<WgcResponse>(`/api/market/wgc-gold-etf?data_type=${dataType}`)
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })

  const chartData = useMemo(() => {
    if (!wgcData?.data) return []
    return wgcData.data
  }, [wgcData])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 5
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  const latest = wgcData?.latest ?? null

  if (isLoading) {
    return (
      <ChartContainer title="金ETFフロー/保有残高（WGC）" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (chartData.length === 0) {
    return (
      <ChartContainer title="金ETFフロー/保有残高（WGC）" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const unit = viewMode === 'holdings' ? 'トン' : 'US$mn'

  // 最新値でソートして上位5カ国を表示
  const topCountries = [...COUNTRY_KEYS]
    .filter(c => latest?.[c] != null)
    .sort((a, b) => {
      const va = Math.abs(latest?.[a] ?? 0)
      const vb = Math.abs(latest?.[b] ?? 0)
      return vb - va
    })
    .slice(0, 5)

  return (
    <ChartContainer
      title="金ETFフロー/保有残高（WGC）"
      dataSource="World Gold Council"
      showPeriodSelector={false}
      sourceUrl="https://www.gold.org/goldhub/data/global-gold-backed-etf-holdings-and-flows"
    >
      {/* 1. Latest values (top 5 + total + gold price) */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        marginBottom: 12,
        padding: '10px 14px',
        background: DARK_THEME.bgTertiary,
        borderRadius: 8,
        flexWrap: 'wrap',
      }}>
        {topCountries.map(country => {
          const val = latest?.[country]
          if (typeof val !== 'number') return null
          return (
            <div
              key={country}
              style={{ display: 'flex', alignItems: 'baseline', gap: 4, opacity: isHidden(country) ? 0.3 : 1, cursor: 'pointer' }}
              onClick={() => handleLegendClick(country)}
            >
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>{COUNTRY_LABELS[country]}</Text>
              <Text style={{ color: COUNTRY_COLORS[country], fontSize: 13, fontWeight: 700 }} className="tabular-nums">
                {viewMode === 'flows'
                  ? `${val >= 0 ? '+' : ''}${val.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
                  : val.toLocaleString(undefined, { maximumFractionDigits: 1 })
                }
              </Text>
            </div>
          )
        })}
        {latest?.total != null && (
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>合計</Text>
            <Text style={{ color: DARK_THEME.textPrimary, fontSize: 13, fontWeight: 700 }} className="tabular-nums">
              {viewMode === 'flows'
                ? `${latest.total >= 0 ? '+' : ''}${latest.total.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
                : latest.total.toLocaleString(undefined, { maximumFractionDigits: 1 })
              }
              {' '}{unit}
            </Text>
          </div>
        )}
        {latest?.gold_price_usd != null && (
          <div
            style={{ display: 'flex', alignItems: 'baseline', gap: 4, opacity: isHidden('gold_price_usd') ? 0.3 : 1, cursor: 'pointer' }}
            onClick={() => handleLegendClick('gold_price_usd')}
          >
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>金価格</Text>
            <Text style={{ color: COLOR_GOLD, fontSize: 13, fontWeight: 700 }} className="tabular-nums">
              ${latest.gold_price_usd.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </Text>
          </div>
        )}
        {latest?.date && (
          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>({latest.date})</Text>
        )}
      </div>

      {/* 2. ViewMode + Compare button */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <ViewModeButtonGroup
          options={VIEW_MODE_OPTIONS.map(o => ({ mode: o.mode, label: o.label }))}
          currentMode={viewMode}
          onChange={(m) => setViewMode(m as ViewMode)}
        />
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            size="small"
            onClick={() => window.open('/compare?s=wgc_gold_etf_holdings_total', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 3. Period selector */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* 4. Chart */}
      <ResponsiveContainer width="100%" height={450}>
        <ComposedChart
          data={filteredData}
          margin={{ top: 16, right: 60, bottom: 0, left: 0 }}
          style={{ backgroundColor: DARK_THEME.chartBg }}
          stackOffset={viewMode === 'flows' ? 'sign' : undefined}
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

          {/* Left Y: トン or US$mn */}
          <YAxis
            yAxisId="left"
            domain={viewMode === 'holdings' ? ['dataMin 0', 'dataMax + 100'] : ['auto', 'auto']}
            tickFormatter={(v: number) => {
              if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(1)}K`
              return `${v.toFixed(0)}`
            }}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            tickMargin={8}
            label={{ value: unit, position: 'top', offset: 8, style: { fill: DARK_THEME.textSecondary, fontSize: 10 } }}
          />

          {/* Right Y: Gold Price USD/oz */}
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={['dataMin - 50', 'dataMax + 50']}
            tickFormatter={(v: number) => v >= 1000 ? `$${(v / 1000).toFixed(1)}K` : `$${v}`}
            axisLine={{ stroke: COLOR_GOLD }}
            tickLine={{ stroke: COLOR_GOLD }}
            tick={{ fill: COLOR_GOLD, fontSize: 11 }}
            tickMargin={4}
            width={55}
          />

          <RechartsTooltip content={<WgcTooltip hiddenSeries={hiddenSeries} viewMode={viewMode} />} />

          <Legend
            wrapperStyle={{ paddingTop: 8, fontSize: 11 }}
            onClick={(e) => handleLegendClick(e.dataKey as string)}
            formatter={(value: string, entry) => (
              <span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : DARK_THEME.textPrimary, fontSize: 11 }}>
                {value}
              </span>
            )}
          />

          {viewMode === 'flows' && (
            <ReferenceLine yAxisId="left" y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />
          )}

          {viewMode === 'holdings' ? (
            /* Holdings mode: stacked area */
            <>
              {COUNTRY_CONFIG.map(({ key, label, color }) => (
                <Area
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stackId="holdings"
                  stroke={color}
                  fill={color}
                  fillOpacity={0.7}
                  strokeWidth={0.5}
                  name={label}
                  yAxisId="left"
                  connectNulls
                  isAnimationActive={false}
                  hide={isHidden(key)}
                />
              ))}
            </>
          ) : (
            /* Flows mode: stacked bar */
            <>
              {COUNTRY_CONFIG.map(({ key, label, color }) => (
                <Bar
                  key={key}
                  dataKey={key}
                  stackId="flows"
                  fill={color}
                  name={label}
                  yAxisId="left"
                  isAnimationActive={false}
                  hide={isHidden(key)}
                />
              ))}
            </>
          )}

          {/* Gold Price line (right Y) */}
          <Line
            type="monotone"
            dataKey="gold_price_usd"
            stroke={COLOR_GOLD}
            strokeWidth={1.5}
            strokeDasharray="6 3"
            dot={false}
            name="金価格 (USD/oz)"
            yAxisId="right"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('gold_price_usd')}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
