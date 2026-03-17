/**
 * 価格転嫁率（中小企業庁）チャート
 *
 * 中小企業庁「価格交渉促進月間」フォローアップ調査から
 * 価格転嫁率を表示
 *
 * 推奨3系列: コスト全般 / 労務費 / 全く転嫁できず割合
 * 全系列: コスト全般 / 原材料費 / エネルギー費 / 労務費
 *
 * 頻度: 半年（3月・9月調査）
 */

import { useMemo, useState } from 'react'
import { Tooltip, Button } from 'antd'
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
import ChartContainer from '../../../common/ChartContainer'
import { useHiddenSeries } from '../../usa/common/useChartData'
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS, CHART_MARGIN } from '../../usa/common/chartConstants'
import { formatMonthLabel } from '../../../../utils/dateFormatters'

// =============================================================================
// 色定義
// =============================================================================
const COLOR_TOTAL = '#3b82f6'          // 青 - コスト全般
const COLOR_RAW_MATERIALS = '#f59e0b'  // アンバー - 原材料費
const COLOR_ENERGY = '#ef4444'          // 赤 - エネルギー費
const COLOR_LABOR = '#10b981'           // エメラルド - 労務費
const COLOR_ZERO = '#8b5cf6'            // パープル - 全く転嫁できず

const DARK_THEME = {
  tooltipBg: '#334155',
  tooltipBorder: '#475569',
}

// =============================================================================
// 型定義
// =============================================================================
interface PricePassThroughItem {
  date: string
  survey_period: string
  total: number
  raw_materials: number | null
  energy: number | null
  labor: number | null
  zero_pass_through: number | null
  supply_chain: {
    tier_1: number
    tier_2: number
    tier_3: number
    tier_4_plus: number
  } | null
}

interface PricePassThroughResponse {
  data: PricePassThroughItem[]
  latest: PricePassThroughItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

type SeriesKey = 'total' | 'raw_materials' | 'energy' | 'labor' | 'zero_pass_through'
type ViewMode = 'main' | 'all'

// =============================================================================
// データ取得フック
// =============================================================================
function usePricePassThroughRateData() {
  return useQuery({
    queryKey: ['japan', 'price-pass-through-rate'],
    queryFn: async () => {
      const { data } = await axios.get<PricePassThroughResponse>(
        '/api/japan/price-pass-through-rate'
      )
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

// =============================================================================
// 系列設定
// =============================================================================
const MAIN_SERIES: { key: SeriesKey; label: string; color: string }[] = [
  { key: 'total', label: 'コスト全般', color: COLOR_TOTAL },
  { key: 'labor', label: '労務費', color: COLOR_LABOR },
  { key: 'zero_pass_through', label: '全く転嫁できず', color: COLOR_ZERO },
]

const ALL_SERIES: { key: SeriesKey; label: string; color: string }[] = [
  { key: 'total', label: 'コスト全般', color: COLOR_TOTAL },
  { key: 'raw_materials', label: '原材料費', color: COLOR_RAW_MATERIALS },
  { key: 'energy', label: 'エネルギー費', color: COLOR_ENERGY },
  { key: 'labor', label: '労務費', color: COLOR_LABOR },
]

const VIEW_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'main', label: '主要3系列' },
  { mode: 'all', label: '全コスト別' },
]

// =============================================================================
// カスタムTooltip
// =============================================================================
function CustomTooltip({
  active,
  payload,
  label,
  hiddenSeries,
  seriesConfig,
}: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
  seriesConfig: typeof MAIN_SERIES
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
      {seriesConfig.map(({ key, label: seriesLabel, color }) => {
        if (hiddenSeries.has(key)) return null
        const item = payload.find((p: { dataKey: string }) => p.dataKey === key)
        if (!item || typeof item.value !== 'number') return null
        return (
          <div
            key={key}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 4,
              fontSize: 13,
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span
                style={{
                  display: 'inline-block',
                  width: 10,
                  height: 10,
                  borderRadius: 2,
                  backgroundColor: color,
                  marginRight: 6,
                }}
              />
              {seriesLabel}
            </span>
            <span style={{ fontWeight: 500, color }}>{item.value.toFixed(1)}%</span>
          </div>
        )
      })}
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================
export default function PricePassThroughRateChart() {
  const { data: apiData, isLoading, error } = usePricePassThroughRateData()
  const [viewMode, setViewMode] = useState<ViewMode>('main')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<SeriesKey>()

  const chartData = useMemo(() => {
    if (!apiData?.data) return []
    return [...apiData.data].sort((a, b) => a.date.localeCompare(b.date))
  }, [apiData])

  if (isLoading) {
    return (
      <ChartContainer title="価格転嫁率（中小企業庁）" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (error || !apiData?.data?.length) {
    return (
      <ChartContainer title="価格転嫁率（中小企業庁）" showPeriodSelector={false}>
        <div style={{ color: TEXT_COLORS.secondary, textAlign: 'center', padding: 40 }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  const latest = apiData.latest
  const seriesConfig = viewMode === 'main' ? MAIN_SERIES : ALL_SERIES

  return (
    <ChartContainer
      title="価格転嫁率（中小企業庁）"
      dataSource="中小企業庁"
      sourceUrl="https://www.chusho.meti.go.jp/keiei/torihiki/follow-up/index.html"
      showPeriodSelector={false}
    >
      {/* 最新値ボックス */}
      <div style={LATEST_VALUE_BOX_STYLE}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          {latest && (
            <>
              <span style={{ color: TEXT_COLORS.secondary, fontSize: 13 }}>
                {latest.survey_period}
              </span>
              <span style={{ color: COLOR_TOTAL, fontWeight: 700, fontSize: 20 }}>
                全体 {latest.total}%
              </span>
              {latest.labor != null && (
                <span style={{ color: COLOR_LABOR, fontWeight: 600, fontSize: 14 }}>
                  労務費 {latest.labor}%
                </span>
              )}
              {latest.raw_materials != null && (
                <span style={{ color: COLOR_RAW_MATERIALS, fontWeight: 600, fontSize: 14 }}>
                  原材料 {latest.raw_materials}%
                </span>
              )}
              {latest.energy != null && (
                <span style={{ color: COLOR_ENERGY, fontWeight: 600, fontSize: 14 }}>
                  エネルギー {latest.energy}%
                </span>
              )}
              {latest.zero_pass_through != null && (
                <span style={{ color: COLOR_ZERO, fontWeight: 600, fontSize: 14 }}>
                  全く転嫁できず {latest.zero_pass_through}%
                </span>
              )}
            </>
          )}
        </div>
      </div>

      {/* ビューモード切替 + データ比較 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div style={{ display: 'flex', gap: 4 }}>
          {VIEW_OPTIONS.map(({ mode, label }) => (
            <Button
              key={mode}
              type={viewMode === mode ? 'primary' : 'default'}
              size="small"
              onClick={() => setViewMode(mode)}
            >
              {label}
            </Button>
          ))}
        </div>
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            onClick={() => window.open('/compare?s=japan_price_pass_through_total', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* チャート */}
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart data={chartData} margin={CHART_MARGIN}>
          <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
          <XAxis
            dataKey="date"
            tickFormatter={(v: string) => formatMonthLabel(v)}
            stroke="#94a3b8"
            tick={{ fill: '#94a3b8', fontSize: 11 }}
          />
          <YAxis
            stroke="#94a3b8"
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            domain={viewMode === 'main' ? [0, 'dataMax + 5'] : ['dataMin - 5', 'dataMax + 5']}
            tickFormatter={(v: number) => `${v}%`}
          />
          <RechartsTooltip
            content={<CustomTooltip hiddenSeries={hiddenSeries} seriesConfig={seriesConfig} />}
          />
          <Legend
            onClick={(e) => {
              if (e && e.dataKey) handleLegendClick(e.dataKey as SeriesKey)
            }}
            wrapperStyle={{ cursor: 'pointer' }}
          />

          {/* 50%基準線（半数が転嫁できた水準） */}
          <ReferenceLine
            y={50}
            stroke="#64748b"
            strokeDasharray="3 3"
            label={{ value: '50%', position: 'insideTopRight', fill: '#64748b', fontSize: 11 }}
          />

          {viewMode === 'main' ? (
            <>
              {/* 主要3系列: 全体・労務費は折れ線、全く転嫁できずは棒グラフ */}
              <Line
                type="monotone"
                dataKey="total"
                name="コスト全般"
                stroke={COLOR_TOTAL}
                strokeWidth={2.5}
                dot={{ r: 4, fill: COLOR_TOTAL }}
                hide={hiddenSeries.has('total')}
                connectNulls
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="labor"
                name="労務費"
                stroke={COLOR_LABOR}
                strokeWidth={2}
                dot={{ r: 3, fill: COLOR_LABOR }}
                hide={hiddenSeries.has('labor')}
                connectNulls
                isAnimationActive={false}
              />
              <Bar
                dataKey="zero_pass_through"
                name="全く転嫁できず"
                fill={COLOR_ZERO}
                opacity={0.6}
                hide={hiddenSeries.has('zero_pass_through')}
                isAnimationActive={false}
                barSize={20}
              />
            </>
          ) : (
            <>
              {/* 全コスト別4系列 */}
              <Line
                type="monotone"
                dataKey="total"
                name="コスト全般"
                stroke={COLOR_TOTAL}
                strokeWidth={2.5}
                dot={{ r: 4, fill: COLOR_TOTAL }}
                hide={hiddenSeries.has('total')}
                connectNulls
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="raw_materials"
                name="原材料費"
                stroke={COLOR_RAW_MATERIALS}
                strokeWidth={2}
                dot={{ r: 3, fill: COLOR_RAW_MATERIALS }}
                hide={hiddenSeries.has('raw_materials')}
                connectNulls
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="energy"
                name="エネルギー費"
                stroke={COLOR_ENERGY}
                strokeWidth={2}
                dot={{ r: 3, fill: COLOR_ENERGY }}
                hide={hiddenSeries.has('energy')}
                connectNulls
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="labor"
                name="労務費"
                stroke={COLOR_LABOR}
                strokeWidth={2}
                dot={{ r: 3, fill: COLOR_LABOR }}
                hide={hiddenSeries.has('labor')}
                connectNulls
                isAnimationActive={false}
              />
            </>
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
