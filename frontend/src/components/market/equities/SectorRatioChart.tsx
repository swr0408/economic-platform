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

// レシオの色
const COLOR_XLY_XLP = '#f59e0b'  // amber - 景気サイクル
const COLOR_XLF_XLU = '#8b5cf6'  // purple - 金利プロキシ
const COLOR_HYG_LQD = '#ef4444'  // red - クレジットリスク
const COLOR_HYG_IEF = '#10b981'  // emerald - クレジットスプレッド
const COLOR_LUMBER_GOLD = '#06b6d4'  // cyan - 住宅/安全資産

// 生値の薄い色
const COLOR_NUM_THIN = '#94a3b8'
const COLOR_DEN_THIN = '#64748b'

// S&P500 オーバーレイ
const COLOR_SP500 = '#3b82f6'

interface SectorRatioItem {
  date: string
  sp500?: number | null
  xly?: number | null
  xlp?: number | null
  xlf?: number | null
  xlu?: number | null
  hyg?: number | null
  lqd?: number | null
  ief?: number | null
  lumber?: number | null
  gold?: number | null
  xly_xlp?: number | null
  xlf_xlu?: number | null
  hyg_lqd?: number | null
  hyg_ief?: number | null
  lumber_gold?: number | null
}

interface SectorRatioResponse {
  data: SectorRatioItem[]
  latest: SectorRatioItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

function useSectorRatioData() {
  return useQuery({
    queryKey: ['market', 'sector-ratio'],
    queryFn: async () => {
      const { data } = await axios.get<SectorRatioResponse>('/api/market/sector-ratio')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

type ViewMode = 'xly_xlp' | 'xlf_xlu' | 'hyg_lqd' | 'hyg_ief' | 'lumber_gold'

const VIEW_MODE_OPTIONS = [
  { mode: 'xly_xlp' as ViewMode, label: 'XLY/XLP' },
  { mode: 'xlf_xlu' as ViewMode, label: 'XLF/XLU' },
  { mode: 'hyg_lqd' as ViewMode, label: 'HYG/LQD' },
  { mode: 'hyg_ief' as ViewMode, label: 'HYG/IEF' },
  { mode: 'lumber_gold' as ViewMode, label: '木材/金' },
]

type SeriesKey = 'ratio' | 'ma' | 'raw_num' | 'raw_den' | 'sp500'

interface RatioConfig {
  label: string
  description: string
  color: string
  maWindow: number
  numKey: keyof SectorRatioItem
  numLabel: string
  denKey: keyof SectorRatioItem
  denLabel: string
}

const RATIO_CONFIG: Record<ViewMode, RatioConfig> = {
  xly_xlp: {
    label: 'XLY/XLP',
    description: '消費循環/安定',
    color: COLOR_XLY_XLP,
    maWindow: 20,
    numKey: 'xly',
    numLabel: 'XLY (消費循環)',
    denKey: 'xlp',
    denLabel: 'XLP (消費安定)',
  },
  xlf_xlu: {
    label: 'XLF/XLU',
    description: '金融/公益',
    color: COLOR_XLF_XLU,
    maWindow: 20,
    numKey: 'xlf',
    numLabel: 'XLF (金融)',
    denKey: 'xlu',
    denLabel: 'XLU (公益)',
  },
  hyg_lqd: {
    label: 'HYG/LQD',
    description: 'ハイイールド/投資適格',
    color: COLOR_HYG_LQD,
    maWindow: 20,
    numKey: 'hyg',
    numLabel: 'HYG (ハイイールド)',
    denKey: 'lqd',
    denLabel: 'LQD (投資適格)',
  },
  hyg_ief: {
    label: 'HYG/IEF',
    description: 'HY/中期国債',
    color: COLOR_HYG_IEF,
    maWindow: 20,
    numKey: 'hyg',
    numLabel: 'HYG (ハイイールド)',
    denKey: 'ief',
    denLabel: 'IEF (中期国債)',
  },
  lumber_gold: {
    label: '木材/金',
    description: '住宅需要vs安全資産。先行指標',
    color: COLOR_LUMBER_GOLD,
    maWindow: 20,
    numKey: 'lumber',
    numLabel: 'Lumber (木材先物)',
    denKey: 'gold',
    denLabel: 'Gold (金先物)',
  },
}

// 移動平均計算
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

// --- Custom tooltip ---
function RatioTooltip({ active, payload, label, hiddenSeries, cfg }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
  cfg: RatioConfig
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))

  const tooltipSeries = [
    { key: 'ratio', label: cfg.label, color: cfg.color, fmt: (v: number) => v.toFixed(4) },
    { key: 'ma', label: `${cfg.maWindow}MA`, color: '#ffffff', fmt: (v: number) => v.toFixed(4) },
    { key: 'raw_num', label: cfg.numLabel, color: COLOR_NUM_THIN, fmt: (v: number) => `$${v.toFixed(2)}` },
    { key: 'raw_den', label: cfg.denLabel, color: COLOR_DEN_THIN, fmt: (v: number) => `$${v.toFixed(2)}` },
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

export default function SectorRatioChart() {
  const { data: apiData, isLoading, error } = useSectorRatioData()
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(2)
  const [viewMode, setViewMode] = useState<ViewMode>('xly_xlp')
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

  const cfg = RATIO_CONFIG[viewMode]

  // チャートデータ（レシオ + MA + 生値 + S&P500）
  const viewData = useMemo(() => {
    const ratioKey = viewMode as keyof SectorRatioItem

    // 全期間データでMA計算
    const fullRatioData = chartData.map((d) => ({
      ratio: (d[ratioKey] as number | null) ?? null,
    }))
    const maValues = computeMA(fullRatioData, cfg.maWindow)
    const startIdx = chartData.length - filteredData.length

    return filteredData.map((d, i) => ({
      date: d.date,
      ratio: (d[ratioKey] as number | null) ?? null,
      ma: maValues[startIdx + i] ?? null,
      raw_num: (d[cfg.numKey] as number | null) ?? null,
      raw_den: (d[cfg.denKey] as number | null) ?? null,
      sp500: d.sp500 ?? null,
    }))
  }, [chartData, filteredData, viewMode, cfg])

  if (isLoading) {
    return (
      <ChartContainer title="セクターレシオ" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (error || !apiData || chartData.length === 0) {
    return (
      <ChartContainer title="セクターレシオ" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = apiData.latest

  return (
    <ChartContainer
      title="セクターレシオ"
      dataSource="cboe"
      sourceUrl="https://www.cboe.com/"
      handbookId="sector-ratio"
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
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>{cfg.label}</Text>
            <Text style={{ color: cfg.color, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
              {((latest[viewMode as keyof SectorRatioItem] as number) ?? 0).toFixed(4)}
            </Text>
          </div>

          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>{cfg.numLabel.split(' ')[0]}</Text>
            <Text style={{ color: COLOR_NUM_THIN, fontSize: 13, fontWeight: 600 }} className="tabular-nums">
              ${((latest[cfg.numKey] as number) ?? 0).toFixed(2)}
            </Text>
          </div>

          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>{cfg.denLabel.split(' ')[0]}</Text>
            <Text style={{ color: COLOR_DEN_THIN, fontSize: 13, fontWeight: 600 }} className="tabular-nums">
              ${((latest[cfg.denKey] as number) ?? 0).toFixed(2)}
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

      {/* ViewModeButtonGroup + データ比較ボタン */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <ViewModeButtonGroup
          options={VIEW_MODE_OPTIONS}
          currentMode={viewMode}
          onChange={(m) => setViewMode(m as ViewMode)}
        />
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            size="small"
            onClick={() => window.open('/compare?s=sector_ratio', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 期間選択 */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* 注釈 */}
      <div style={{ marginBottom: 8, padding: '6px 10px', background: 'rgba(59,130,246,0.08)', borderRadius: 6, fontSize: 11, color: DARK_THEME.textSecondary }}>
        {cfg.description} — レシオ上昇 = リスクオン, 下降 = リスクオフ
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

          {/* 左Y軸: レシオ + MA */}
          <YAxis
            yAxisId="left"
            domain={['dataMin * 0.95', 'dataMax * 1.05']}
            tickFormatter={(v: number) => v.toFixed(2)}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: cfg.color, fontSize: 11 }}
            tickMargin={8}
            label={{ value: cfg.label, angle: -90, position: 'insideLeft', offset: -8, fill: cfg.color, fontSize: 11 }}
          />

          {/* 非表示Y軸: 生値（分子/分母）— 独立スケール */}
          <YAxis
            yAxisId="raw"
            hide
            domain={['dataMin * 0.8', 'dataMax * 1.2']}
          />

          {/* 右Y軸: S&P500 */}
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={['dataMin', 'dataMax']}
            tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}K` : `${v}`}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: COLOR_SP500, fontSize: 11 }}
            tickMargin={8}
          />

          <RechartsTooltip content={<RatioTooltip hiddenSeries={hiddenSeries.hiddenSeries} cfg={cfg} />} />

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
          <Line type="monotone" dataKey="ratio" stroke={cfg.color} strokeWidth={2} dot={false} name={cfg.label} yAxisId="left" connectNulls isAnimationActive={false} hide={hiddenSeries.isHidden('ratio')} />

          {/* MA線 */}
          <Line type="monotone" dataKey="ma" stroke="#ffffff" strokeWidth={1.5} strokeDasharray="4 2" dot={false} name={`${cfg.maWindow}MA`} yAxisId="left" connectNulls isAnimationActive={false} hide={hiddenSeries.isHidden('ma')} />

          {/* 分子の生値（薄く、独立スケール） */}
          <Line type="monotone" dataKey="raw_num" stroke={COLOR_NUM_THIN} strokeWidth={1} strokeOpacity={0.3} dot={false} name={cfg.numLabel} yAxisId="raw" connectNulls isAnimationActive={false} hide={hiddenSeries.isHidden('raw_num')} />

          {/* 分母の生値（薄く、独立スケール） */}
          <Line type="monotone" dataKey="raw_den" stroke={COLOR_DEN_THIN} strokeWidth={1} strokeOpacity={0.3} dot={false} name={cfg.denLabel} yAxisId="raw" connectNulls isAnimationActive={false} hide={hiddenSeries.isHidden('raw_den')} />

          {/* S&P500（右Y軸） */}
          <Line type="monotone" dataKey="sp500" stroke={COLOR_SP500} strokeWidth={1.5} strokeDasharray="4 2" dot={false} name="S&P 500" yAxisId="right" connectNulls isAnimationActive={false} hide={hiddenSeries.isHidden('sp500')} />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
