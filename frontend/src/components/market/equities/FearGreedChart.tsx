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
  ReferenceArea,
} from 'recharts'
import ChartContainer from '../../common/ChartContainer'
import PeriodSelector, { type PeriodValue } from '../../common/PeriodSelector'
import { formatMonthLabel, formatDayLabel } from '../../../utils/dateFormatters'

const { Text } = Typography

// ダークテーマ
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

// センチメントカラー（背景用: 半透明）
const SENTIMENT_COLORS = {
  'extreme fear': 'rgba(220, 38, 38, 0.15)',   // 赤
  'fear':         'rgba(249, 115, 22, 0.12)',   // オレンジ
  'neutral':      'rgba(234, 179, 8, 0.10)',    // 黄
  'greed':        'rgba(34, 197, 94, 0.12)',    // 緑
  'extreme greed': 'rgba(16, 185, 129, 0.15)',  // 濃い緑
}

// センチメントラベル
const SENTIMENT_LABELS: Record<string, string> = {
  'extreme fear': 'Extreme Fear',
  'fear': 'Fear',
  'neutral': 'Neutral',
  'greed': 'Greed',
  'extreme greed': 'Extreme Greed',
}

// センチメントテキストカラー
const SENTIMENT_TEXT_COLORS: Record<string, string> = {
  'extreme fear': '#ef4444',
  'fear': '#f97316',
  'neutral': '#eab308',
  'greed': '#22c55e',
  'extreme greed': '#10b981',
}

// チャートカラー
const FEAR_GREED_COLOR = '#f59e0b'
const SP500_COLOR = '#3b82f6'

// センチメント閾値
const SENTIMENT_BANDS = [
  { y1: 0, y2: 25, rating: 'extreme fear' },
  { y1: 25, y2: 45, rating: 'fear' },
  { y1: 45, y2: 55, rating: 'neutral' },
  { y1: 55, y2: 75, rating: 'greed' },
  { y1: 75, y2: 100, rating: 'extreme greed' },
] as const

// API レスポンス型
interface FearGreedItem {
  date: string
  score: number
  rating: string
  sp500?: number | null
}

interface FearGreedLatest {
  date: string
  score: number
  rating: string
  sp500?: number | null
  previous_close?: number
  previous_1_week?: number
  previous_1_month?: number
  previous_1_year?: number | null
}

interface FearGreedResponse {
  data: FearGreedItem[]
  latest: FearGreedLatest | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

function useFearGreedData() {
  return useQuery({
    queryKey: ['market', 'fear-greed'],
    queryFn: async () => {
      const { data } = await axios.get<FearGreedResponse>('/api/market/fear-greed')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

// カスタムツールチップ
function CustomTooltip({ active, payload, label }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
}) {
  if (!active || !payload || payload.length === 0) return null

  const formattedLabel = formatDayLabel(String(label))
  const fgItem = payload.find((p: { dataKey: string }) => p.dataKey === 'score')
  const spItem = payload.find((p: { dataKey: string }) => p.dataKey === 'sp500')

  // Get rating from raw data
  const rawData = payload[0]?.payload as FearGreedItem | undefined
  const rating = rawData?.rating || ''

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

      {fgItem && typeof fgItem.value === 'number' && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
          <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
            <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: FEAR_GREED_COLOR, marginRight: 6 }} />
            Fear & Greed
          </span>
          <span style={{ fontWeight: 500, color: FEAR_GREED_COLOR }}>
            {fgItem.value.toFixed(1)}
          </span>
        </div>
      )}

      {rating && (
        <div style={{ fontSize: 12, color: SENTIMENT_TEXT_COLORS[rating] || '#94a3b8', marginBottom: 4, paddingLeft: 16 }}>
          {SENTIMENT_LABELS[rating] || rating}
        </div>
      )}

      {spItem && typeof spItem.value === 'number' && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
          <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
            <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: SP500_COLOR, marginRight: 6 }} />
            S&P 500
          </span>
          <span style={{ fontWeight: 500, color: SP500_COLOR }}>
            {spItem.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </span>
        </div>
      )}
    </div>
  )
}

export default function FearGreedChart() {
  const { data: apiData, isLoading } = useFearGreedData()
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>('default')

  const chartData = useMemo(() => {
    if (!apiData?.data) return []
    return apiData.data
      .map((d) => ({
        date: d.date,
        score: d.score,
        rating: d.rating,
        sp500: d.sp500 ?? null,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [apiData])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    if (selectedPeriod === 'default') {
      // デフォルト: 2年
      const cutoff = new Date()
      cutoff.setFullYear(cutoff.getFullYear() - 2)
      const cutoffStr = cutoff.toISOString().slice(0, 10)
      return chartData.filter((d) => d.date >= cutoffStr)
    }
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 2
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  if (isLoading) {
    return (
      <ChartContainer title="Fear & Greed Index" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (!apiData || chartData.length === 0) {
    return (
      <ChartContainer title="Fear & Greed Index" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = apiData.latest

  return (
    <ChartContainer
      title="CNN Fear & Greed Index"
      dataSource="CNN Business"
      sourceUrl="https://edition.cnn.com/markets/fear-and-greed"
      showPeriodSelector={false}
    >
      {/* 最新値表示 */}
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
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>最新値</Text>
            <Text
              style={{ color: FEAR_GREED_COLOR, fontSize: 22, fontWeight: 700 }}
              className="tabular-nums"
            >
              {latest.score.toFixed(1)}
            </Text>
            <Text
              style={{
                color: SENTIMENT_TEXT_COLORS[latest.rating] || DARK_THEME.textSecondary,
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              {SENTIMENT_LABELS[latest.rating] || latest.rating}
            </Text>
          </div>

          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            {latest.previous_close != null && (
              <div>
                <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>前日</Text>{' '}
                <Text style={{ color: DARK_THEME.textPrimary, fontSize: 12 }} className="tabular-nums">
                  {latest.previous_close.toFixed(1)}
                </Text>
              </div>
            )}
            {latest.previous_1_week != null && (
              <div>
                <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>1W前</Text>{' '}
                <Text style={{ color: DARK_THEME.textPrimary, fontSize: 12 }} className="tabular-nums">
                  {latest.previous_1_week.toFixed(1)}
                </Text>
              </div>
            )}
            {latest.previous_1_month != null && (
              <div>
                <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>1M前</Text>{' '}
                <Text style={{ color: DARK_THEME.textPrimary, fontSize: 12 }} className="tabular-nums">
                  {latest.previous_1_month.toFixed(1)}
                </Text>
              </div>
            )}
            {latest.previous_1_year != null && (
              <div>
                <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>1Y前</Text>{' '}
                <Text style={{ color: DARK_THEME.textPrimary, fontSize: 12 }} className="tabular-nums">
                  {latest.previous_1_year.toFixed(1)}
                </Text>
              </div>
            )}
          </div>

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
            onClick={() => window.open('/compare?s=fear_greed', '_blank')}
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
          margin={{ top: 16, right: 8, bottom: 0, left: 0 }}
          style={{ backgroundColor: DARK_THEME.chartBg }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />

          {/* センチメント帯の背景色 */}
          {SENTIMENT_BANDS.map((band) => (
            <ReferenceArea
              key={band.rating}
              yAxisId="left"
              y1={band.y1}
              y2={band.y2}
              fill={SENTIMENT_COLORS[band.rating]}
              fillOpacity={1}
              strokeOpacity={0}
            />
          ))}

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
            yAxisId="left"
            domain={[0, 100]}
            ticks={[0, 25, 45, 55, 75, 100]}
            tickFormatter={(v: number) => `${v}`}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: FEAR_GREED_COLOR, fontSize: 11 }}
            tickMargin={8}
            label={{ value: 'F&G Index', angle: -90, position: 'insideLeft', offset: -8, fill: FEAR_GREED_COLOR, fontSize: 11 }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={['dataMin', 'dataMax']}
            tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}K` : `${v}`}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: SP500_COLOR, fontSize: 11 }}
            tickMargin={8}
            label={{ value: 'S&P 500', angle: 90, position: 'insideRight', offset: -4, fill: SP500_COLOR, fontSize: 11 }}
          />

          <RechartsTooltip content={<CustomTooltip />} />

          <Legend
            wrapperStyle={{ paddingTop: 8 }}
          />

          <Line
            type="monotone"
            dataKey="score"
            stroke={FEAR_GREED_COLOR}
            strokeWidth={1.5}
            dot={false}
            name="Fear & Greed Index"
            yAxisId="left"
            connectNulls
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="sp500"
            stroke={SP500_COLOR}
            strokeWidth={1.5}
            dot={false}
            name="S&P 500"
            yAxisId="right"
            connectNulls
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* センチメント凡例 */}
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        gap: 12,
        marginTop: 8,
        flexWrap: 'wrap',
      }}>
        {SENTIMENT_BANDS.map((band) => (
          <div
            key={band.rating}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              fontSize: 11,
            }}
          >
            <span
              style={{
                display: 'inline-block',
                width: 12,
                height: 12,
                borderRadius: 2,
                backgroundColor: SENTIMENT_COLORS[band.rating],
                border: `1px solid ${SENTIMENT_TEXT_COLORS[band.rating]}`,
              }}
            />
            <span style={{ color: SENTIMENT_TEXT_COLORS[band.rating] }}>
              {SENTIMENT_LABELS[band.rating]} ({band.y1}-{band.y2})
            </span>
          </div>
        ))}
      </div>
    </ChartContainer>
  )
}
