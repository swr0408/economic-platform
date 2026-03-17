/**
 * MOF対外対内証券売買チャート
 * 財務省「対外及び対内証券売買等の状況」（週次）
 *
 * 4つのサブチャート:
 *  1. 対外 株式（Net）+ S&P500 + 日経平均
 *  2. 対外 中長期債（Net）+ 米国10年債利回り + ドル円
 *  3. 対内 株式（Net）+ 日経平均
 *  4. 対内 中長期債（Net）+ 日本10年国債利回り
 */
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

// 棒グラフの色
const COLOR_BAR = '#3b82f6'
// オーバーレイ線の色
const COLOR_SP500 = '#10b981'
const COLOR_NIKKEI = '#ef4444'
const COLOR_USDJPY = '#f59e0b'
const COLOR_US10Y = '#8b5cf6'
const COLOR_JGB10Y = '#06b6d4'

interface MofDataItem {
  date: string
  assets_equity_net: number | null
  assets_longterm_debt_net: number | null
  liabilities_equity_net: number | null
  liabilities_longterm_debt_net: number | null
  sp500: number | null
  nikkei225: number | null
  usdjpy: number | null
  us10y: number | null
  jgb10y: number | null
}

interface MofResponse {
  data: MofDataItem[]
  latest: MofDataItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

type ViewMode = 'assets_equity' | 'assets_debt' | 'liabilities_equity' | 'liabilities_debt'
const VIEW_MODE_OPTIONS = [
  { mode: 'assets_equity' as ViewMode, label: '対外株式' },
  { mode: 'assets_debt' as ViewMode, label: '対外中長期債' },
  { mode: 'liabilities_equity' as ViewMode, label: '対内株式' },
  { mode: 'liabilities_debt' as ViewMode, label: '対内中長期債' },
]

function useMofSecuritiesTradingData() {
  return useQuery({
    queryKey: ['market', 'mof-securities-trading'],
    queryFn: async () => {
      const { data } = await axios.get<MofResponse>('/api/market/mof-securities-trading')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

// --- Chart config per view mode ---
// yAxisId: 'right' = 右Y軸①（primary）, 'right2' = 右Y軸②（secondary, 外側）
interface OverlayConfig {
  key: string
  label: string
  color: string
  dasharray?: string
  yAxisId: 'right' | 'right2'
}

interface ChartConfig {
  barKey: string
  barLabel: string
  barColor: string
  overlays: OverlayConfig[]
  title: string
}

function getChartConfig(viewMode: ViewMode): ChartConfig {
  switch (viewMode) {
    case 'assets_equity':
      return {
        barKey: 'assets_equity_net',
        barLabel: '対外 株式Net (億円)',
        barColor: COLOR_BAR,
        overlays: [
          { key: 'nikkei225', label: '日経平均', color: COLOR_NIKKEI, yAxisId: 'right' },
          { key: 'sp500', label: 'S&P 500', color: COLOR_SP500, dasharray: '6 3', yAxisId: 'right2' },
        ],
        title: '対外証券投資 - 株式・投資ファンド持分',
      }
    case 'assets_debt':
      return {
        barKey: 'assets_longterm_debt_net',
        barLabel: '対外 中長期債Net (億円)',
        barColor: '#8b5cf6',
        overlays: [
          { key: 'us10y', label: '米国10年債利回り (%)', color: COLOR_US10Y, yAxisId: 'right' },
          { key: 'usdjpy', label: 'USD/JPY', color: COLOR_USDJPY, dasharray: '6 3', yAxisId: 'right2' },
        ],
        title: '対外証券投資 - 中長期債',
      }
    case 'liabilities_equity':
      return {
        barKey: 'liabilities_equity_net',
        barLabel: '対内 株式Net (億円)',
        barColor: '#ef4444',
        overlays: [
          { key: 'nikkei225', label: '日経平均', color: COLOR_NIKKEI, yAxisId: 'right' },
        ],
        title: '対内証券投資 - 株式・投資ファンド持分',
      }
    case 'liabilities_debt':
      return {
        barKey: 'liabilities_longterm_debt_net',
        barLabel: '対内 中長期債Net (億円)',
        barColor: '#f59e0b',
        overlays: [
          { key: 'jgb10y', label: 'JGB 10Y (%)', color: COLOR_JGB10Y, yAxisId: 'right' },
        ],
        title: '対内証券投資 - 中長期債',
      }
  }
}

type AllSeriesKey = 'bar' | 'overlay0' | 'overlay1'

// --- Custom Tooltip ---
function MofTooltip({ active, payload, label, config }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  config: ChartConfig
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))
  const dataPoint = payload[0]?.payload as Record<string, unknown> | undefined

  return (
    <div style={{ backgroundColor: DARK_THEME.tooltipBg, border: `1px solid ${DARK_THEME.tooltipBorder}`, borderRadius: 8, padding: '12px 16px', boxShadow: '0 4px 16px rgba(0,0,0,0.3)' }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: '#f1f5f9' }}>{formattedLabel}</div>
      {/* Bar value */}
      {(() => {
        const val = dataPoint?.[config.barKey]
        if (typeof val !== 'number') return null
        return (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: config.barColor, marginRight: 6 }} />
              {config.barLabel.split(' (')[0]}
            </span>
            <span style={{ fontWeight: 500, color: config.barColor }}>{val.toLocaleString()} 億円</span>
          </div>
        )
      })()}
      {/* Overlays */}
      {config.overlays.map(({ key, label: ovLabel, color }) => {
        const val = dataPoint?.[key]
        if (typeof val !== 'number') return null
        const fmt = key === 'us10y' || key === 'jgb10y'
          ? `${val.toFixed(3)}%`
          : key === 'usdjpy'
            ? `¥${val.toFixed(2)}`
            : val.toLocaleString(undefined, { maximumFractionDigits: 0 })
        return (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13, borderTop: '1px solid #475569', paddingTop: 4, marginTop: 2 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: color, marginRight: 6 }} />
              {ovLabel}
            </span>
            <span style={{ fontWeight: 500, color }}>{fmt}</span>
          </div>
        )
      })}
    </div>
  )
}

// --- Y-axis formatter for overlay ---
function overlayTickFormatter(key: string): (v: number) => string {
  if (key === 'us10y' || key === 'jgb10y') return (v: number) => `${v.toFixed(1)}%`
  if (key === 'usdjpy') return (v: number) => `¥${v.toFixed(0)}`
  // sp500, nikkei225
  return (v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}K` : `${v}`
}

export default function MofSecuritiesTradingChart() {
  const { data: apiData, isLoading, error } = useMofSecuritiesTradingData()
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(3)
  const [viewMode, setViewMode] = useState<ViewMode>('liabilities_equity')
  const { hiddenSeries, handleLegendClick, isHidden } = useHiddenSeries<AllSeriesKey>()

  const config = getChartConfig(viewMode)

  const chartData = useMemo(() => {
    if (!apiData?.data) return []
    return [...apiData.data].sort((a, b) => a.date.localeCompare(b.date))
  }, [apiData])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 3
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  if (isLoading) {
    return (
      <ChartContainer title="対外対内証券売買" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (error || !apiData || chartData.length === 0) {
    return (
      <ChartContainer title="対外対内証券売買" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = apiData.latest

  // 右Y軸①（right）と右Y軸②（right2）に分離
  const rightOverlays = config.overlays.filter(o => o.yAxisId === 'right')
  const right2Overlays = config.overlays.filter(o => o.yAxisId === 'right2')
  const hasRight2 = right2Overlays.length > 0

  return (
    <ChartContainer
      title="対外対内証券売買"
      dataSource="MOF / yfinance / FRED"
      sourceUrl="https://www.mof.go.jp/policy/international_policy/reference/itn_transactions_in_securities/week.csv"
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
          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>
            {latest.date}
          </Text>

          {latest.liabilities_equity_net != null && (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>対内株式</Text>
              <Text style={{ color: '#ef4444', fontSize: 15, fontWeight: 700 }} className="tabular-nums">
                {latest.liabilities_equity_net.toLocaleString()}
              </Text>
            </div>
          )}

          {latest.liabilities_longterm_debt_net != null && (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>対内中長期債</Text>
              <Text style={{ color: '#f59e0b', fontSize: 15, fontWeight: 700 }} className="tabular-nums">
                {latest.liabilities_longterm_debt_net.toLocaleString()}
              </Text>
            </div>
          )}

          {latest.assets_equity_net != null && (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>対外株式</Text>
              <Text style={{ color: COLOR_BAR, fontSize: 14, fontWeight: 600 }} className="tabular-nums">
                {latest.assets_equity_net.toLocaleString()}
              </Text>
            </div>
          )}

          {latest.assets_longterm_debt_net != null && (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>対外中長期債</Text>
              <Text style={{ color: '#8b5cf6', fontSize: 14, fontWeight: 600 }} className="tabular-nums">
                {latest.assets_longterm_debt_net.toLocaleString()}
              </Text>
            </div>
          )}

          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>億円</Text>
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
            onClick={() => {
              const keyMap: Record<ViewMode, string> = {
                assets_equity: 'mof_assets_equity_net',
                assets_debt: 'mof_assets_longterm_debt_net',
                liabilities_equity: 'mof_liabilities_equity_net',
                liabilities_debt: 'mof_liabilities_longterm_debt_net',
              }
              window.open(`/compare?s=${keyMap[viewMode]}`, '_blank')
            }}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 期間選択 */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* サブタイトル */}
      <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12, display: 'block', marginBottom: 4 }}>
        {config.title}
      </Text>

      {/* チャート */}
      <ResponsiveContainer width="100%" height={420}>
        <ComposedChart
          data={filteredData}
          margin={{ top: 16, right: 0, bottom: 0, left: 0 }}
          style={{ backgroundColor: DARK_THEME.chartBg }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
          <XAxis
            dataKey="date"
            tickFormatter={formatMonthLabel}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            tickMargin={16}
            height={60}
            interval="preserveStartEnd"
          />

          {/* 左Y軸: 億円 (Net売買) */}
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

          {/* 右Y軸①: primary overlay（内側） */}
          {rightOverlays.length > 0 && (
            <YAxis
              yAxisId="right"
              orientation="right"
              domain={['dataMin * 0.95', 'dataMax * 1.05']}
              tickFormatter={overlayTickFormatter(rightOverlays[0].key)}
              axisLine={{ stroke: rightOverlays[0].color }}
              tickLine={{ stroke: rightOverlays[0].color }}
              tick={{ fill: rightOverlays[0].color, fontSize: 11 }}
              tickMargin={4}
              width={55}
            />
          )}

          {/* 右Y軸②: secondary overlay（外側） */}
          {hasRight2 && (
            <YAxis
              yAxisId="right2"
              orientation="right"
              domain={['dataMin * 0.95', 'dataMax * 1.05']}
              tickFormatter={overlayTickFormatter(right2Overlays[0].key)}
              axisLine={{ stroke: right2Overlays[0].color, strokeDasharray: '4 3' }}
              tickLine={{ stroke: right2Overlays[0].color }}
              tick={{ fill: right2Overlays[0].color, fontSize: 11 }}
              tickMargin={4}
              width={55}
            />
          )}

          <ReferenceLine y={0} yAxisId="left" stroke={DARK_THEME.axisLine} strokeDasharray="2 2" />

          <RechartsTooltip content={<MofTooltip config={config} />} />

          <Legend
            wrapperStyle={{ paddingTop: 8 }}
            onClick={(e) => handleLegendClick(e.dataKey as string)}
            formatter={(value: string, entry) => (
              <span style={{ color: hiddenSeries.has(entry.dataKey as AllSeriesKey) ? '#64748b' : DARK_THEME.textPrimary, fontSize: 11 }}>
                {value}
              </span>
            )}
          />

          {/* Bar: Net売買額 */}
          <Bar
            dataKey={config.barKey}
            name={config.barLabel}
            fill={config.barColor}
            fillOpacity={0.85}
            yAxisId="left"
            isAnimationActive={false}
            hide={isHidden('bar')}
          />

          {/* Overlay lines - 各lineを自分のyAxisIdに紐付け */}
          {config.overlays.map((ov, idx) => (
            <Line
              key={ov.key}
              type="monotone"
              dataKey={ov.key}
              name={ov.label}
              stroke={ov.color}
              strokeWidth={1.5}
              strokeDasharray={ov.dasharray}
              dot={false}
              yAxisId={ov.yAxisId}
              connectNulls
              isAnimationActive={false}
              hide={isHidden(`overlay${idx}` as AllSeriesKey)}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>

    </ChartContainer>
  )
}
