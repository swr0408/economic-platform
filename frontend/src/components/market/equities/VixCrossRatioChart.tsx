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
const COLOR_VVIX_VIX = '#f59e0b'
const COLOR_SKEW_VIX = '#f472b6'
const COLOR_MOVE_VIX = '#ef4444'
const COLOR_VXN_VIX = '#8b5cf6'
const COLOR_OVX_VIX = '#10b981'
const COLOR_GVZ_VIX = '#06b6d4'

// MA色
const COLOR_MA = '#ffffff'

// 薄い生値色
const COLOR_VIX_THIN = '#ef4444'
const COLOR_VVIX_THIN = '#f59e0b'
const COLOR_SKEW_THIN = '#f472b6'
const COLOR_MOVE_THIN = '#10b981'
const COLOR_VXN_THIN = '#8b5cf6'
const COLOR_OVX_THIN = '#14b8a6'
const COLOR_GVZ_THIN = '#06b6d4'

// オーバーレイ色
const COLOR_SP500 = '#3b82f6'
const COLOR_US10Y = '#f97316'
const COLOR_NDX = '#a78bfa'
const COLOR_WTI = '#fbbf24'
const COLOR_GOLD = '#fcd34d'

interface VixCrossRatioItem {
  date: string
  vix: number
  sp500?: number | null
  vvix?: number | null
  skew?: number | null
  move?: number | null
  vxn?: number | null
  ovx?: number | null
  gvz?: number | null
  vvix_vix?: number | null
  skew_vix?: number | null
  move_vix?: number | null
  vxn_vix?: number | null
  ovx_vix?: number | null
  gvz_vix?: number | null
  us10y?: number | null
  ndx?: number | null
  wti?: number | null
  gold?: number | null
}

interface VixCrossRatioResponse {
  data: VixCrossRatioItem[]
  latest: VixCrossRatioItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

function useVixCrossRatioData() {
  return useQuery({
    queryKey: ['market', 'vix-cross-ratio'],
    queryFn: async () => {
      const { data } = await axios.get<VixCrossRatioResponse>('/api/market/vix-cross-ratio')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

type ViewMode = 'vvix_vix' | 'skew_vix' | 'move_vix' | 'vxn_vix' | 'ovx_vix' | 'gvz_vix'

const VIEW_MODE_OPTIONS = [
  { mode: 'vvix_vix' as ViewMode, label: 'VVIX/VIX' },
  { mode: 'skew_vix' as ViewMode, label: 'SKEW/VIX' },
  { mode: 'move_vix' as ViewMode, label: 'MOVE/VIX' },
  { mode: 'vxn_vix' as ViewMode, label: 'VXN/VIX' },
  { mode: 'ovx_vix' as ViewMode, label: 'OVX/VIX' },
  { mode: 'gvz_vix' as ViewMode, label: 'GVZ/VIX' },
]

type SeriesKey = 'ratio' | 'ma' | 'raw_num' | 'raw_vix' | 'sp500' | 'overlay2'

// 各レシオの設定
interface RatioConfig {
  label: string
  color: string
  maWindow: number
  numKey: keyof VixCrossRatioItem
  numLabel: string
  numColor: string
  // 追加オーバーレイ（MOVE/VIX→US10Y, OVX/VIX→WTI, GVZ/VIX→Gold, VXN/VIX→なし）
  overlay2Key: keyof VixCrossRatioItem | null
  overlay2Label: string
  overlay2Color: string
  overlay2Format: (v: number) => string
  overlay2AxisLabel: string
}

const RATIO_CONFIG: Record<ViewMode, RatioConfig> = {
  vvix_vix: {
    label: 'VVIX/VIX', color: COLOR_VVIX_VIX, maWindow: 5,
    numKey: 'vvix', numLabel: 'VVIX', numColor: COLOR_VVIX_THIN,
    overlay2Key: null, overlay2Label: '', overlay2Color: '', overlay2Format: () => '', overlay2AxisLabel: '',
  },
  skew_vix: {
    label: 'SKEW/VIX', color: COLOR_SKEW_VIX, maWindow: 20,
    numKey: 'skew', numLabel: 'SKEW', numColor: COLOR_SKEW_THIN,
    overlay2Key: null, overlay2Label: '', overlay2Color: '', overlay2Format: () => '', overlay2AxisLabel: '',
  },
  move_vix: {
    label: 'MOVE/VIX', color: COLOR_MOVE_VIX, maWindow: 0,
    numKey: 'move', numLabel: 'MOVE', numColor: COLOR_MOVE_THIN,
    overlay2Key: 'us10y', overlay2Label: '米国債10年 (%)', overlay2Color: COLOR_US10Y,
    overlay2Format: (v: number) => `${v.toFixed(2)}%`, overlay2AxisLabel: '米国10年 (%)',
  },
  vxn_vix: {
    label: 'VXN/VIX', color: COLOR_VXN_VIX, maWindow: 0,
    numKey: 'vxn', numLabel: 'VXN', numColor: COLOR_VXN_THIN,
    overlay2Key: 'ndx', overlay2Label: 'Nasdaq 100', overlay2Color: COLOR_NDX,
    overlay2Format: (v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}K` : `${v}`, overlay2AxisLabel: 'Nasdaq 100',
  },
  ovx_vix: {
    label: 'OVX/VIX', color: COLOR_OVX_VIX, maWindow: 0,
    numKey: 'ovx', numLabel: 'OVX', numColor: COLOR_OVX_THIN,
    overlay2Key: 'wti', overlay2Label: 'WTI原油 (USD)', overlay2Color: COLOR_WTI,
    overlay2Format: (v: number) => `$${v.toFixed(0)}`, overlay2AxisLabel: 'WTI (USD)',
  },
  gvz_vix: {
    label: 'GVZ/VIX', color: COLOR_GVZ_VIX, maWindow: 0,
    numKey: 'gvz', numLabel: 'GVZ', numColor: COLOR_GVZ_THIN,
    overlay2Key: 'gold', overlay2Label: '金 (USD)', overlay2Color: COLOR_GOLD,
    overlay2Format: (v: number) => `$${v.toFixed(0)}`, overlay2AxisLabel: 'Gold (USD)',
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
function RatioTooltip({ active, payload, label, hiddenSeries, cfg, hasOverlay2 }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
  cfg: RatioConfig
  hasOverlay2: boolean
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))

  const tooltipSeries = [
    { key: 'ratio', label: cfg.label, color: cfg.color, fmt: (v: number) => v.toFixed(4) },
    ...(cfg.maWindow > 0 ? [{ key: 'ma', label: `${cfg.maWindow}MA`, color: COLOR_MA, fmt: (v: number) => v.toFixed(4) }] : []),
    { key: 'raw_num', label: cfg.numLabel, color: cfg.numColor, fmt: (v: number) => v.toFixed(2) },
    { key: 'raw_vix', label: 'VIX', color: COLOR_VIX_THIN, fmt: (v: number) => v.toFixed(2) },
    { key: 'sp500', label: 'S&P 500', color: COLOR_SP500, fmt: (v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 0 }) },
    ...(hasOverlay2 ? [{ key: 'overlay2', label: cfg.overlay2Label, color: cfg.overlay2Color, fmt: cfg.overlay2Format }] : []),
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

export default function VixCrossRatioChart() {
  const { data: apiData, isLoading, error } = useVixCrossRatioData()
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(2)
  const [viewMode, setViewMode] = useState<ViewMode>('vvix_vix')
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
  const hasOverlay2 = cfg.overlay2Key != null

  // チャートデータ（レシオ + MA + 生値 + S&P500 + 追加オーバーレイ）
  const viewData = useMemo(() => {
    const ratioKey = viewMode as keyof VixCrossRatioItem

    // 全期間データでMA計算
    const fullRatioData = chartData.map((d) => ({
      ratio: (d[ratioKey] as number | null) ?? null,
    }))
    const maValues = computeMA(fullRatioData, cfg.maWindow)
    const startIdx = chartData.length - filteredData.length

    return filteredData.map((d, i) => {
      const item: Record<string, string | number | null> = {
        date: d.date,
        ratio: (d[ratioKey] as number | null) ?? null,
        ma: maValues[startIdx + i] ?? null,
        raw_num: (d[cfg.numKey] as number | null) ?? null,
        raw_vix: d.vix,
        sp500: d.sp500 ?? null,
      }
      if (cfg.overlay2Key) {
        item.overlay2 = (d[cfg.overlay2Key] as number | null) ?? null
      }
      return item
    })
  }, [chartData, filteredData, viewMode, cfg])

  if (isLoading) {
    return (
      <ChartContainer title="VIXクロスレシオ" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (error || !apiData || chartData.length === 0) {
    return (
      <ChartContainer title="VIXクロスレシオ" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = apiData.latest

  return (
    <ChartContainer
      title="VIXクロスレシオ"
      dataSource="yfinance"
      sourceUrl="https://finance.yahoo.com/quote/%5EVIX/"
      handbookId="vix-term-structure"
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
              {((latest[viewMode as keyof VixCrossRatioItem] as number) ?? 0).toFixed(4)}
            </Text>
          </div>

          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>{cfg.numLabel}</Text>
            <Text style={{ color: cfg.numColor, fontSize: 13, fontWeight: 600 }} className="tabular-nums">
              {((latest[cfg.numKey] as number) ?? 0).toFixed(2)}
            </Text>
          </div>

          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>VIX</Text>
            <Text style={{ color: COLOR_VIX_THIN, fontSize: 13, fontWeight: 600 }} className="tabular-nums">
              {latest.vix.toFixed(2)}
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

          {hasOverlay2 && latest[cfg.overlay2Key!] != null && (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>{cfg.overlay2Label}</Text>
              <Text style={{ color: cfg.overlay2Color, fontSize: 13, fontWeight: 600 }} className="tabular-nums">
                {cfg.overlay2Format(latest[cfg.overlay2Key!] as number)}
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
            onClick={() => window.open('/compare?s=vix_cross_ratio', '_blank')}
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
          data={viewData}
          margin={{ top: 16, right: hasOverlay2 ? 60 : 8, bottom: 0, left: 0 }}
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
            domain={['dataMin * 0.9', 'dataMax * 1.1']}
            tickFormatter={(v: number) => v.toFixed(2)}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: cfg.color, fontSize: 11 }}
            tickMargin={8}
            label={{ value: cfg.label, angle: -90, position: 'insideLeft', offset: -8, fill: cfg.color, fontSize: 11 }}
          />

          {/* 非表示Y軸: 生値（VIX, 分子）— スケールなし表示用 */}
          <YAxis
            yAxisId="raw"
            hide
            domain={['dataMin * 0.8', 'dataMax * 1.2']}
          />

          {/* 右Y軸①: S&P500 */}
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={['dataMin', 'dataMax']}
            tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}K` : `${v}`}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: COLOR_SP500, fontSize: 11 }}
            tickMargin={8}
            // 
            // 
            
            
            
            
            label={{ value: 'S&P 500', angle: 90, position: 'insideRight', offset: -4, fill: COLOR_SP500, fontSize: 11 }}
          />

          {/* 右Y軸②: 追加オーバーレイ（US10Y / WTI / Gold）— ある場合のみ */}
          {hasOverlay2 && (
            <YAxis
              yAxisId="right2"
              orientation="right"
              domain={['dataMin * 0.95', 'dataMax * 1.05']}
              tickFormatter={(v: number) => cfg.overlay2Format(v)}
              axisLine={{ stroke: cfg.overlay2Color, strokeDasharray: '4 3' }}
              tickLine={{ stroke: cfg.overlay2Color }}
              tick={{ fill: cfg.overlay2Color, fontSize: 10 }}
              tickMargin={4}
              width={50}
            />
          )}

          <RechartsTooltip content={<RatioTooltip hiddenSeries={hiddenSeries.hiddenSeries} cfg={cfg} hasOverlay2={hasOverlay2} />} />

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
          {cfg.maWindow > 0 && (
            <Line type="monotone" dataKey="ma" stroke={COLOR_MA} strokeWidth={1.5} strokeDasharray="4 2" dot={false} name={`${cfg.maWindow}MA`} yAxisId="left" connectNulls isAnimationActive={false} hide={hiddenSeries.isHidden('ma')} />
          )}

          {/* 分子の生値（薄く、独立スケール） */}
          <Line type="monotone" dataKey="raw_num" stroke={cfg.numColor} strokeWidth={1} strokeOpacity={0.3} dot={false} name={cfg.numLabel} yAxisId="raw" connectNulls isAnimationActive={false} hide={hiddenSeries.isHidden('raw_num')} />

          {/* VIX生値（薄く、独立スケール） */}
          <Line type="monotone" dataKey="raw_vix" stroke={COLOR_VIX_THIN} strokeWidth={1} strokeOpacity={0.3} dot={false} name="VIX" yAxisId="raw" connectNulls isAnimationActive={false} hide={hiddenSeries.isHidden('raw_vix')} />

          {/* S&P500（右Y軸①） */}
          <Line type="monotone" dataKey="sp500" stroke={COLOR_SP500} strokeWidth={1.5} strokeDasharray="4 2" dot={false} name="S&P 500" yAxisId="right" connectNulls isAnimationActive={false} hide={hiddenSeries.isHidden('sp500')} />

          {/* 追加オーバーレイ（右Y軸②） */}
          {hasOverlay2 && (
            <Line type="monotone" dataKey="overlay2" stroke={cfg.overlay2Color} strokeWidth={1.5} strokeDasharray="6 3" dot={false} name={cfg.overlay2Label} yAxisId="right2" connectNulls isAnimationActive={false} hide={hiddenSeries.isHidden('overlay2')} />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
