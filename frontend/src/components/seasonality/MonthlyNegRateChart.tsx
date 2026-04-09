import { useEffect, useState } from 'react'
import { Spin, Alert, Typography, Popover } from 'antd'
import { InfoCircleOutlined } from '@ant-design/icons'
import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from 'recharts'
import axios from 'axios'

const { Text } = Typography

const COLORS = {
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textTertiary: '#64748b',
  border: '#334155',
  gridLine: '#475569',
  axisLine: '#64748b',
  tooltipBg: '#1e293b',
  tooltipBorder: '#475569',
  positive: '#10b981',
  negative: '#ef4444',
  negativeAlt: '#f87171',
  full: '#3b82f6',
  recent: '#f59e0b',
}

interface PeriodStats {
  n: number
  neg_rate: number
}

interface MonthData {
  month: number
  full: PeriodStats
  recent: PeriodStats
  diff: {
    neg_rate_diff: number
  }
}

interface MonthlyStatsResponse {
  symbol: string
  generated_at: string
  periods: {
    full: { start_year: number; end_year: number; label: string }
    recent: { start_year: number; end_year: number; label: string }
  }
  months: MonthData[]
}

interface ChartDataPoint {
  month: string
  fullNegRate: number
  recentNegRate: number
  fullN: number
  recentN: number
  negRateDiff: number
}

const MONTH_LABELS = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

interface MonthlyNegRateChartProps {
  symbol: string
}

export default function MonthlyNegRateChart({ symbol }: MonthlyNegRateChartProps) {
  const [data, setData] = useState<MonthlyStatsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await axios.get<MonthlyStatsResponse>(
          `/api/seasonality/${encodeURIComponent(symbol)}/monthly-stats`
        )
        setData(response.data)
      } catch (err) {
        console.error('Failed to fetch monthly stats:', err)
        if (axios.isAxiosError(err) && err.response?.status === 404) {
          setError('この銘柄の月別統計データはまだ生成されていません。')
        } else {
          setError('月別統計データの取得に失敗しました。')
        }
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [symbol])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '60px 20px' }}>
        <Spin />
        <p style={{ marginTop: 12, color: COLORS.textSecondary }}>下落率データを読み込み中...</p>
      </div>
    )
  }

  if (error) {
    return <Alert message="情報" description={error} type="info" showIcon style={{ marginBottom: 16 }} />
  }

  if (!data || !data.months || data.months.length === 0) {
    return <Alert message="データなし" description="データがありません。" type="warning" showIcon />
  }

  const chartData: ChartDataPoint[] = data.months.map((m) => ({
    month: MONTH_LABELS[m.month - 1],
    fullNegRate: m.full.neg_rate * 100,
    recentNegRate: m.recent.neg_rate * 100,
    fullN: m.full.n,
    recentN: m.recent.n,
    negRateDiff: m.diff.neg_rate_diff * 100,
  }))

  return (
    <div>
      {/* ヘッダー */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 16,
        flexWrap: 'wrap',
        gap: 12,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Text style={{ color: COLORS.textPrimary, fontSize: 14, fontWeight: 600 }}>
            月別下落率
          </Text>
          <Popover
            trigger="click"
            placement="bottomLeft"
            overlayStyle={{ maxWidth: 480 }}
            content={
              <div style={{ fontSize: 12, lineHeight: 1.7, maxWidth: 440, color: COLORS.textPrimary }}>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 下落率とは</b><br />
                  対象月のリターンがマイナスだった年の割合。「負けやすさ」を示す勝率の裏返し。
                  <div style={{ color: '#cbd5e1', marginTop: 2 }}>例: 9月の下落率が 65% なら、過去9月の約3分の2でマイナス。</div>
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 50%基準線</b><br />
                  50%超 = マイナスの方が多い「負け越し月」<br />
                  50%未満 = プラスの方が多い「勝ち越し月」
                </div>
                <div>
                  <b style={{ color: '#fbbf24' }}>● 全期間 vs 直近</b><br />
                  両者の差で「直近で勝率がどう変化したか」を確認。Tooltipに差分を表示しています。
                </div>
              </div>
            }
          >
            <InfoCircleOutlined style={{ color: COLORS.textSecondary, cursor: 'pointer' }} />
          </Popover>
        </div>
      </div>

      {/* 期間情報 */}
      <div style={{ marginBottom: 12, fontSize: 12, color: COLORS.textSecondary }}>
        <span style={{ marginRight: 16 }}>
          <span style={{ display: 'inline-block', width: 10, height: 10, background: COLORS.full, marginRight: 6, borderRadius: 2 }} />
          全期間: {data.periods.full.label}
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 10, height: 10, background: COLORS.recent, marginRight: 6, borderRadius: 2 }} />
          {data.periods.recent.label}: {data.periods.recent.start_year}-{data.periods.recent.end_year}
        </span>
      </div>

      {/* グラフ */}
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={chartData} margin={{ top: 16, right: 24, left: 8, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={COLORS.gridLine} opacity={0.3} />
          <XAxis
            dataKey="month"
            stroke={COLORS.axisLine}
            tick={{ fill: COLORS.textSecondary, fontSize: 12 }}
          />
          <YAxis
            stroke={COLORS.axisLine}
            tick={{ fill: COLORS.textSecondary, fontSize: 12 }}
            domain={[0, 100]}
            label={{
              value: '下落率 (%)',
              angle: -90,
              position: 'insideLeft',
              fill: COLORS.textSecondary,
              fontSize: 12,
              offset: 16,
            }}
          />
          <ReferenceLine
            y={50}
            stroke={COLORS.textPrimary}
            strokeDasharray="4 4"
            strokeWidth={1}
            label={{ value: '50%', fill: COLORS.textSecondary, fontSize: 11, position: 'right' }}
          />
          <RechartsTooltip
            content={<NegRateTooltip fullLabel={data.periods.full.label} recentLabel={data.periods.recent.label} />}
          />
          <Legend
            wrapperStyle={{ color: COLORS.textPrimary, fontSize: 12 }}
            formatter={(value) => <span style={{ color: COLORS.textPrimary }}>{value}</span>}
          />
          <Bar dataKey="fullNegRate" name={data.periods.full.label} fill={COLORS.full}>
            {chartData.map((entry, idx) => (
              <Cell
                key={`full-${idx}`}
                fill={entry.fullNegRate >= 50 ? COLORS.negative : COLORS.full}
              />
            ))}
          </Bar>
          <Bar dataKey="recentNegRate" name={data.periods.recent.label} fill={COLORS.recent}>
            {chartData.map((entry, idx) => (
              <Cell
                key={`recent-${idx}`}
                fill={entry.recentNegRate >= 50 ? COLORS.negativeAlt : COLORS.recent}
              />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>

      <div style={{ marginTop: 8, fontSize: 11, color: COLORS.textTertiary, textAlign: 'right' }}>
        ※ 50%超は赤系（負け越し月）。バーをホバーで全期間 vs 直近の差分を確認できます。
      </div>
    </div>
  )
}

interface NegRateTooltipProps {
  active?: boolean
  payload?: Array<{ payload: ChartDataPoint }>
  label?: string
  fullLabel: string
  recentLabel: string
}

function NegRateTooltip({ active, payload, label, fullLabel, recentLabel }: NegRateTooltipProps) {
  if (!active || !payload || payload.length === 0) return null
  const d = payload[0].payload

  const fmt = (v: number, digits = 1) => v.toFixed(digits)
  const fmtSign = (v: number, digits = 1) => `${v >= 0 ? '+' : ''}${v.toFixed(digits)}`

  return (
    <div
      style={{
        background: COLORS.tooltipBg,
        border: `1px solid ${COLORS.tooltipBorder}`,
        borderRadius: 6,
        padding: '10px 12px',
        color: COLORS.textPrimary,
        fontSize: 12,
        lineHeight: 1.6,
        minWidth: 220,
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 6 }}>{label}</div>

      <div style={{ marginBottom: 6 }}>
        <div style={{ color: COLORS.full, fontWeight: 600, marginBottom: 2 }}>
          ● {fullLabel} (n={d.fullN})
        </div>
        <div style={{ color: COLORS.textSecondary }}>
          下落率: <span style={{ color: COLORS.textPrimary, fontWeight: 600 }}>{fmt(d.fullNegRate)}%</span>
        </div>
      </div>

      <div style={{ marginBottom: 6 }}>
        <div style={{ color: COLORS.recent, fontWeight: 600, marginBottom: 2 }}>
          ● {recentLabel} (n={d.recentN})
        </div>
        <div style={{ color: COLORS.textSecondary }}>
          下落率: <span style={{ color: COLORS.textPrimary, fontWeight: 600 }}>{fmt(d.recentNegRate)}%</span>
        </div>
      </div>

      <div style={{ borderTop: `1px solid ${COLORS.border}`, paddingTop: 6 }}>
        <div style={{ color: COLORS.textSecondary }}>
          下落率差（直近-全期間）:{' '}
          <span style={{ color: d.negRateDiff >= 0 ? COLORS.negativeAlt : COLORS.positive, fontWeight: 600 }}>
            {fmtSign(d.negRateDiff)}pp
          </span>
        </div>
      </div>
    </div>
  )
}
