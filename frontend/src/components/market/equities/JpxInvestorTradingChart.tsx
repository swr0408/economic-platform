import { useState, useMemo } from 'react'
import { Typography, Tooltip, Button } from 'antd'
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
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../common/ChartContainer'
import PeriodSelector, { type PeriodValue } from '../../common/PeriodSelector'
import { formatMonthLabel, formatDayLabel } from '../../../utils/dateFormatters'
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

// 投資家タイプ色
const COLOR_INDIVIDUALS = '#ef4444'      // 個人 - red
const COLOR_FOREIGNERS = '#3b82f6'       // 海外投資家 - blue
const COLOR_TRUST_BANKS = '#10b981'      // 信託銀行 - green
const COLOR_PROPRIETARY = '#f59e0b'      // 自己計 - amber
const COLOR_BUSINESS_CORPS = '#8b5cf6'   // 事業法人 - purple
const COLOR_INVESTMENT_TRUSTS = '#869ba5' // 投資信託 - cyan
const COLOR_NIKKEI = '#fff'           // 日経平均 - gray (dashed)

interface TradingItem {
  date: string
  individuals: number | null
  foreigners: number | null
  trust_banks: number | null
  investment_trusts: number | null
  business_corps: number | null
  proprietary: number | null
  nikkei_close: number | null
}

interface LatestNikkei {
  date: string
  close: number
}

interface TradingResponse {
  data: TradingItem[]
  latest: TradingItem | null
  latest_nikkei: LatestNikkei | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

type ViewMode = 'main' | 'sub' | 'all'
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'all', label: '全体' },
  { mode: 'main', label: 'メイン' },
  { mode: 'sub', label: 'サブ' },
]

type SeriesKey = 'individuals' | 'foreigners' | 'trust_banks' | 'investment_trusts' | 'business_corps' | 'proprietary' | 'nikkei_close'
type InvestorKey = Exclude<SeriesKey, 'nikkei_close'>

interface SeriesConfig {
  key: InvestorKey
  label: string
  color: string
  group: 'main' | 'sub'
}

const ALL_SERIES: SeriesConfig[] = [
  { key: 'individuals', label: '個人', color: COLOR_INDIVIDUALS, group: 'main' },
  { key: 'foreigners', label: '海外投資家', color: COLOR_FOREIGNERS, group: 'main' },
  { key: 'trust_banks', label: '信託銀行', color: COLOR_TRUST_BANKS, group: 'main' },
  { key: 'proprietary', label: '自己計', color: COLOR_PROPRIETARY, group: 'sub' },
  { key: 'business_corps', label: '事業法人', color: COLOR_BUSINESS_CORPS, group: 'sub' },
  { key: 'investment_trusts', label: '投資信託', color: COLOR_INVESTMENT_TRUSTS, group: 'sub' },
]

function getVisibleSeries(viewMode: ViewMode): SeriesConfig[] {
  if (viewMode === 'main') return ALL_SERIES.filter(s => s.group === 'main')
  if (viewMode === 'sub') return ALL_SERIES.filter(s => s.group === 'sub')
  return ALL_SERIES
}

function formatOku(val: number | null): string {
  if (val == null) return '-'
  const sign = val > 0 ? '+' : ''
  return `${sign}${val.toLocaleString(undefined, { maximumFractionDigits: 1 })}億`
}

/**
 * チャートデータ構築: 元の値をそのまま使用。
 * stackOffset="sign" により正の値は0から上、負の値は0から下にスタックされる。
 * 日経のみ週（売買データなし）ではバーを描画しない。
 */
function buildChartData(data: TradingItem[], keys: InvestorKey[]): Record<string, unknown>[] {
  return data.map((item) => {
    const hasTrading = keys.some(k => item[k] != null)
    const row: Record<string, unknown> = {
      date: item.date,
      nikkei_close: item.nikkei_close,
    }
    for (const key of keys) {
      row[key] = hasTrading ? (item[key] ?? 0) : undefined
    }
    return row
  })
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function TradingTooltip({ active, payload, label, hiddenSeries, visibleSeries }: {
  active?: boolean
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
  visibleSeries: SeriesConfig[]
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))

  const dataPoint = payload[0]?.payload as Record<string, unknown> | undefined

  return (
    <div style={{
      backgroundColor: DARK_THEME.tooltipBg,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: '#f1f5f9' }}>{formattedLabel}</div>
      {visibleSeries.map(({ key, label: seriesLabel, color }) => {
        if (hiddenSeries.has(key)) return null
        const val = dataPoint?.[key]
        if (typeof val !== 'number') return null
        return (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: color, marginRight: 6 }} />
              {seriesLabel}
            </span>
            <span style={{ fontWeight: 500, color }}>{formatOku(val)}</span>
          </div>
        )
      })}
      {/* 日経平均 */}
      {!hiddenSeries.has('nikkei_close') && (() => {
        const nikkeiVal = dataPoint?.nikkei_close
        if (typeof nikkeiVal !== 'number') return null
        return (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13, borderTop: '1px solid #475569', paddingTop: 4, marginTop: 4 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: COLOR_NIKKEI, marginRight: 6 }} />
              日経平均
            </span>
            <span style={{ fontWeight: 500, color: COLOR_NIKKEI }}>{nikkeiVal.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
          </div>
        )
      })()}
    </div>
  )
}


export default function JpxInvestorTradingChart() {
  const [viewMode, setViewMode] = useState<ViewMode>('all')
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(1)
  const { hiddenSeries, handleLegendClick, isHidden } = useHiddenSeries<SeriesKey>()

  const { data: tradingData, isLoading } = useQuery({
    queryKey: ['market', 'jpx-investor-trading'],
    queryFn: async () => {
      const { data } = await axios.get<TradingResponse>('/api/market/jpx-investor-trading')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })

  const chartData = useMemo(() => {
    if (!tradingData?.data) return []
    return tradingData.data
  }, [tradingData])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 2
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  const visibleSeries = getVisibleSeries(viewMode)
  const visibleKeys = visibleSeries.map(s => s.key)

  // 正負分離データ（同一stackIdで1本のバーに）
  const splitData = useMemo(
    () => buildChartData(filteredData, visibleKeys),
    [filteredData, visibleKeys],
  )

  const latest = tradingData?.latest ?? null
  const latestNikkei = tradingData?.latest_nikkei ?? null

  // 日経平均の表示値：latest_nikkei（日足最新）があればそれを使い、なければlatest.nikkei_closeにフォールバック
  const nikkeiDisplay = useMemo(() => {
    if (latestNikkei) return { value: latestNikkei.close, date: latestNikkei.date }
    if (latest?.nikkei_close != null) return { value: latest.nikkei_close, date: latest.date }
    return null
  }, [latestNikkei, latest])

  if (isLoading) {
    return (
      <ChartContainer title="投資部門別売買状況" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (chartData.length === 0) {
    return (
      <ChartContainer title="投資部門別売買状況" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  return (
    <ChartContainer
      title="投資部門別売買状況"
      dataSource="JPX / yfinance"
      showPeriodSelector={false}
      sourceUrl="https://www.jpx.co.jp/markets/statistics-equities/investor-type/index.html"
      handbookId="jpx-investor-trading"
    >
      {/* 1. Latest values */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        marginBottom: 12,
        padding: '10px 14px',
        background: DARK_THEME.bgTertiary,
        borderRadius: 8,
        flexWrap: 'wrap',
      }}>
        {visibleSeries.map(({ key, label, color }) => {
          const val = latest?.[key]
          if (val == null) return null
          return (
            <div
              key={key}
              style={{ display: 'flex', alignItems: 'baseline', gap: 6, opacity: isHidden(key) ? 0.3 : 1, cursor: 'pointer' }}
              onClick={() => handleLegendClick(key)}
            >
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>{label}</Text>
              <Text style={{ color, fontSize: 15, fontWeight: 700 }} className="tabular-nums">
                {formatOku(val as number)}
              </Text>
            </div>
          )
        })}
        {nikkeiDisplay && (
          <div
            style={{ display: 'flex', alignItems: 'baseline', gap: 6, opacity: isHidden('nikkei_close') ? 0.3 : 1, cursor: 'pointer' }}
            onClick={() => handleLegendClick('nikkei_close')}
          >
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>日経平均</Text>
            <Text style={{ color: COLOR_NIKKEI, fontSize: 15, fontWeight: 700 }} className="tabular-nums">
              {nikkeiDisplay.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </Text>
            {nikkeiDisplay.date !== latest?.date && (
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>({nikkeiDisplay.date})</Text>
            )}
          </div>
        )}
        {latest?.date && (
          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>({latest.date})</Text>
        )}
      </div>

      {/* 2. ViewMode + Compare button */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            size="small"
            onClick={() => window.open('/compare?s=jpx_inv_foreigners&s=jpx_inv_individuals&s=jpx_inv_trust_banks', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 3. Period selector */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* 4. Chart - 同一stackIdで正負を1本のバーに */}
      <ResponsiveContainer width="100%" height={420}>
        <ComposedChart
          data={splitData}
          margin={{ top: 16, right: 60, bottom: 0, left: 0 }}
          style={{ backgroundColor: DARK_THEME.chartBg }}
          stackOffset="sign"
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

          {/* Left Y: 億円 */}
          <YAxis
            yAxisId="left"
            tickFormatter={(v: number) => {
              const abs = Math.abs(v)
              if (abs >= 10000) return `${(v / 10000).toFixed(0)}兆`
              return `${v.toFixed(0)}`
            }}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            tickMargin={8}
            label={{ value: '億円', position: 'top', offset: 8, style: { fill: DARK_THEME.textSecondary, fontSize: 10 } }}
          />

          {/* Right Y: 日経平均 */}
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={['dataMin - 500', 'dataMax + 500']}
            tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}K` : `${v}`}
            axisLine={{ stroke: COLOR_NIKKEI }}
            tickLine={{ stroke: COLOR_NIKKEI }}
            tick={{ fill: COLOR_NIKKEI, fontSize: 11 }}
            tickMargin={4}
            width={50}
          />

          <ReferenceLine y={0} yAxisId="left" stroke={DARK_THEME.axisLine} strokeDasharray="2 2" />

          <RechartsTooltip content={<TradingTooltip hiddenSeries={hiddenSeries} visibleSeries={visibleSeries} />} />

          <Legend
            wrapperStyle={{ paddingTop: 8 }}
            onClick={(e) => handleLegendClick(e.dataKey as string)}
            formatter={(value: string, entry) => (
              <span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : DARK_THEME.textPrimary }}>
                {value}
              </span>
            )}
          />

          {/* 積み上げ棒グラフ: rechartsは正値を0から上、負値を0から下に正しくスタックする */}
          {visibleSeries.map(({ key, label, color }) => (
            <Bar
              key={key}
              dataKey={key}
              fill={color}
              fillOpacity={0.85}
              name={label}
              yAxisId="left"
              stackId="a"
              isAnimationActive={false}
              hide={isHidden(key)}
            />
          ))}

          {/* Nikkei line */}
          <Line
            type="monotone"
            dataKey="nikkei_close"
            stroke={COLOR_NIKKEI}
            strokeWidth={1.5}
            strokeDasharray="6 3"
            dot={false}
            name="日経平均"
            yAxisId="right"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('nikkei_close')}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
