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
} from 'recharts'
import ChartContainer from '../../common/ChartContainer'
import PeriodSelector, { type PeriodValue } from '../../common/PeriodSelector'
import { formatDayLabel } from '../../../utils/dateFormatters'
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

const COLOR_RATIO_25 = '#f59e0b'   // amber - 25日
const COLOR_RATIO_75 = '#a78bfa'   // violet - 75日
const COLOR_NIKKEI = '#ef4444'
const COLOR_TOPIX = '#3b82f6'

interface AdRatioItem {
  date: string
  ratio: number | null
  advances: number
  declines: number
  unchanged: number
  advances_25d: number
  declines_25d: number
  nikkei225?: number | null
  topix?: number | null
}

interface AdRatioResponse {
  data: AdRatioItem[]
  latest: AdRatioItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

function useAdvanceDeclineRatioData() {
  return useQuery({
    queryKey: ['market', 'advance-decline-ratio'],
    queryFn: async () => {
      const { data } = await axios.get<AdRatioResponse>('/api/market/advance-decline-ratio')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

type SeriesKey = 'ratio' | 'ratio75' | 'nikkei225' | 'topix'

/** 日次advances/declinesからN日騰落レシオを算出 */
function computeRollingRatio(
  data: { advances: number; declines: number }[],
  window: number
): (number | null)[] {
  const result: (number | null)[] = []
  for (let i = 0; i < data.length; i++) {
    if (i < window - 1) {
      result.push(null)
      continue
    }
    let sumAdv = 0
    let sumDec = 0
    for (let j = i - window + 1; j <= i; j++) {
      sumAdv += data[j].advances
      sumDec += data[j].declines
    }
    result.push(sumDec > 0 ? Math.round((sumAdv / sumDec) * 1000) / 10 : null)
  }
  return result
}

const SERIES_CONFIG: { key: SeriesKey; label: string; color: string }[] = [
  { key: 'ratio', label: '騰落レシオ (25日)', color: COLOR_RATIO_25 },
  { key: 'ratio75', label: '騰落レシオ (75日)', color: COLOR_RATIO_75 },
  { key: 'nikkei225', label: '日経平均', color: COLOR_NIKKEI },
  { key: 'topix', label: 'TOPIX', color: COLOR_TOPIX },
]

function CustomTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null

  const formattedLabel = formatDayLabel(String(label))
  const rawData = payload[0]?.payload as (AdRatioItem & { ratio75?: number | null }) | undefined

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

        const formatted = (key === 'ratio' || key === 'ratio75')
          ? `${item.value.toFixed(1)}%`
          : item.value.toLocaleString(undefined, { maximumFractionDigits: 0 })

        return (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: color, marginRight: 6 }} />
              {seriesLabel}
            </span>
            <span style={{ fontWeight: 500, color }}>
              {formatted}
            </span>
          </div>
        )
      })}

      {/* 騰落数の内訳 */}
      {rawData && !hiddenSeries.has('ratio') && (
        <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid #475569', fontSize: 11, color: DARK_THEME.textSecondary }}>
          <span style={{ color: '#22c55e' }}>↑{rawData.advances}</span>
          {' / '}
          <span style={{ color: '#ef4444' }}>↓{rawData.declines}</span>
          {' / '}
          <span>→{rawData.unchanged}</span>
          <span style={{ marginLeft: 8 }}>
            (25日: ↑{rawData.advances_25d} / ↓{rawData.declines_25d})
          </span>
        </div>
      )}
    </div>
  )
}

export default function AdvanceDeclineRatioChart() {
  const { data: apiData, isLoading, error } = useAdvanceDeclineRatioData()
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(2)
  const { hiddenSeries, handleLegendClick, isHidden } = useHiddenSeries<SeriesKey>(['topix'])

  const chartData = useMemo(() => {
    if (!apiData?.data) return []
    return apiData.data
      .map((d) => ({
        date: d.date,
        ratio: d.ratio,
        advances: d.advances,
        declines: d.declines,
        unchanged: d.unchanged,
        advances_25d: d.advances_25d,
        declines_25d: d.declines_25d,
        nikkei225: d.nikkei225 ?? null,
        topix: d.topix ?? null,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [apiData])

  // 75日騰落レシオを算出
  const chartDataWith75 = useMemo(() => {
    if (chartData.length === 0) return []
    const ratio75Values = computeRollingRatio(chartData, 75)
    return chartData.map((d, i) => ({
      ...d,
      ratio75: ratio75Values[i],
    }))
  }, [chartData])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartDataWith75
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 2
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartDataWith75.filter((d) => d.date >= cutoffStr)
  }, [chartDataWith75, selectedPeriod])

  if (isLoading) {
    return (
      <ChartContainer title="東証プライム 騰落レシオ" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (error || !apiData || chartData.length === 0) {
    return (
      <ChartContainer title="東証プライム 騰落レシオ" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = apiData.latest
  const latest75 = chartDataWith75.length > 0 ? chartDataWith75[chartDataWith75.length - 1].ratio75 : null

  return (
    <ChartContainer
      title="東証プライム 騰落レシオ"
      dataSource="nikkei225jp.com / yfinance"
      sourceUrl="https://nikkei225jp.com/data/touraku.php"
      handbookId="advance-decline-ratio"
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
          <div
            style={{ display: 'flex', alignItems: 'baseline', gap: 6, opacity: isHidden('ratio') ? 0.3 : 1, cursor: 'pointer' }}
            onClick={() => handleLegendClick('ratio')}
          >
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>25日</Text>
            <Text style={{ color: COLOR_RATIO_25, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
              {(latest.ratio ?? 0).toFixed(1)}%
            </Text>
          </div>

          {latest75 != null && (
            <div
              style={{ display: 'flex', alignItems: 'baseline', gap: 6, opacity: isHidden('ratio75') ? 0.3 : 1, cursor: 'pointer' }}
              onClick={() => handleLegendClick('ratio75')}
            >
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>75日</Text>
              <Text style={{ color: COLOR_RATIO_75, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
                {latest75.toFixed(1)}%
              </Text>
            </div>
          )}

          {latest.nikkei225 != null && (
            <div
              style={{ display: 'flex', alignItems: 'baseline', gap: 6, opacity: isHidden('nikkei225') ? 0.3 : 1, cursor: 'pointer' }}
              onClick={() => handleLegendClick('nikkei225')}
            >
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>日経平均</Text>
              <Text style={{ color: COLOR_NIKKEI, fontSize: 13, fontWeight: 600 }} className="tabular-nums">
                {(latest.nikkei225 ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </Text>
            </div>
          )}

          {latest.topix != null && (
            <div
              style={{ display: 'flex', alignItems: 'baseline', gap: 6, opacity: isHidden('topix') ? 0.3 : 1, cursor: 'pointer' }}
              onClick={() => handleLegendClick('topix')}
            >
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>TOPIX</Text>
              <Text style={{ color: COLOR_TOPIX, fontSize: 13, fontWeight: 600 }} className="tabular-nums">
                {(latest.topix ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </Text>
            </div>
          )}

          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>
            ({latest.date})
          </Text>
        </div>
      )}

      {/* データ比較ボタン */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            size="small"
            onClick={() => window.open('/compare?s=advance_decline_ratio', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 期間選択 */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* チャート */}
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart
          data={filteredData}
          margin={{ top: 16, right: 8, bottom: 0, left: 4 }}
          style={{ backgroundColor: DARK_THEME.chartBg }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />

          <XAxis
            type="category"
            dataKey="date"
            tickFormatter={formatDayLabel}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            tickMargin={16}
            height={60}
            interval="preserveStartEnd"
          />

          {/* 左Y軸: 騰落レシオ (%) */}
          <YAxis
            yAxisId="left"
            domain={[60, 140]}
            ticks={[70, 80, 90, 100, 110, 120, 130]}
            tickFormatter={(v: number) => `${v}%`}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: COLOR_RATIO_25, fontSize: 11 }}
            tickMargin={4}
            width={42}
          />

          {/* 右Y軸①: 日経平均 */}
          <YAxis
            yAxisId="right1"
            orientation="right"
            domain={['dataMin', 'dataMax']}
            tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}K` : `${v}`}
            axisLine={{ stroke: COLOR_NIKKEI }}
            tickLine={{ stroke: COLOR_NIKKEI }}
            tick={{ fill: COLOR_NIKKEI, fontSize: 11 }}
            tickMargin={4}
            width={50}
          />

          {/* 右Y軸②: TOPIX ETF */}
          <YAxis
            yAxisId="right2"
            orientation="right"
            domain={['dataMin', 'dataMax']}
            tickFormatter={(v: number) => v.toLocaleString()}
            axisLine={{ stroke: COLOR_TOPIX }}
            tickLine={{ stroke: COLOR_TOPIX }}
            tick={{ fill: COLOR_TOPIX, fontSize: 11 }}
            tickMargin={4}
            width={50}
          />

          {/* 基準線: 120%（過熱警戒） */}
          <ReferenceLine yAxisId="left" y={120} stroke="#ef4444" strokeDasharray="6 3" strokeWidth={1.5} />
          {/* 基準線: 100%（中立） */}
          <ReferenceLine yAxisId="left" y={100} stroke="#94a3b8" strokeDasharray="4 4" strokeWidth={1} />
          {/* 基準線: 70%（底値圏） */}
          <ReferenceLine yAxisId="left" y={70} stroke="#22c55e" strokeDasharray="6 3" strokeWidth={1.5} />

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
            dataKey="ratio"
            stroke={COLOR_RATIO_25}
            strokeWidth={2}
            dot={false}
            name="騰落レシオ (25日)"
            yAxisId="left"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('ratio')}
          />
          <Line
            type="monotone"
            dataKey="ratio75"
            stroke={COLOR_RATIO_75}
            strokeWidth={1.5}
            strokeDasharray="4 2"
            dot={false}
            name="騰落レシオ (75日)"
            yAxisId="left"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('ratio75')}
          />
          <Line
            type="monotone"
            dataKey="nikkei225"
            stroke={COLOR_NIKKEI}
            strokeWidth={1.5}
            dot={false}
            name="日経平均"
            yAxisId="right1"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('nikkei225')}
          />
          <Line
            type="monotone"
            dataKey="topix"
            stroke={COLOR_TOPIX}
            strokeWidth={1.5}
            dot={false}
            name="TOPIX"
            yAxisId="right2"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('topix')}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* 目安凡例 */}
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        gap: 16,
        marginTop: 8,
        flexWrap: 'wrap',
        fontSize: 11,
      }}>
        <span style={{ color: '#ef4444' }}>120%以上: 過熱警戒</span>
        <span style={{ color: '#94a3b8' }}>100%前後: 中立</span>
        <span style={{ color: '#22c55e' }}>70%以下: 底値圏</span>
      </div>
    </ChartContainer>
  )
}
