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
  positiveAlt: '#34d399',
  negative: '#ef4444',
  negativeAlt: '#f87171',
  full: '#3b82f6',
  recent: '#f59e0b',
}

interface PeriodStats {
  n: number
  mean: number
  median: number
  mean_median_gap: number
}

interface MonthData {
  month: number
  full: PeriodStats
  recent: PeriodStats
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
  fullMedian: number
  recentMedian: number
  fullMean: number
  recentMean: number
  fullGap: number
  recentGap: number
  fullN: number
  recentN: number
}

const MONTH_LABELS = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

interface MonthlyMedianChartProps {
  symbol: string
}

export default function MonthlyMedianChart({ symbol }: MonthlyMedianChartProps) {
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
        <p style={{ marginTop: 12, color: COLORS.textSecondary }}>中央値データを読み込み中...</p>
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
    fullMedian: m.full.median,
    recentMedian: m.recent.median,
    fullMean: m.full.mean,
    recentMean: m.recent.mean,
    fullGap: m.full.mean_median_gap,
    recentGap: m.recent.mean_median_gap,
    fullN: m.full.n,
    recentN: m.recent.n,
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
            月別中央値
          </Text>
          <Popover
            trigger="click"
            placement="bottomLeft"
            overlayStyle={{ maxWidth: 500 }}
            content={
              <div style={{ fontSize: 12, lineHeight: 1.7, maxWidth: 460, color: COLORS.textPrimary }}>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 中央値とは</b><br />
                  対象月のリターンを並べた中央の値（50パーセンタイル）。
                  暴騰／暴落といった<b>外れ値の影響を受けにくい代表値</b>で、「典型的な年に何が起きているか」を示します。
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 平均との違い</b><br />
                  ・<b>平均 ≈ 中央値</b>: 分布が対称に近い（平年並みの安定した月）<br />
                  ・<b>平均 &gt; 中央値</b>: 一部の大きな上昇に押し上げられた月（右裾型）<br />
                  ・<b>平均 &lt; 中央値</b>: 一部の大暴落に引きずられた月（左裾型）
                  <div style={{ color: '#cbd5e1', marginTop: 2 }}>例: 平均+1.5%, 中央値+0.3% → 「平年は0.3%だが、稀に大上昇する月」</div>
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 使い方</b><br />
                  平均グラフと並べて見ると、その月の上昇が「<b>毎年コツコツ型</b>」か「<b>当たり外れの大きい型</b>」かが判断できます。
                </div>
                <div>
                  <b style={{ color: '#fbbf24' }}>● 全期間 vs 直近</b><br />
                  Tooltipで両期間の中央値、平均、平均-中央値の乖離を同時確認できます。
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
            label={{
              value: '中央値 (%)',
              angle: -90,
              position: 'insideLeft',
              fill: COLORS.textSecondary,
              fontSize: 12,
              offset: 16,
            }}
          />
          <ReferenceLine y={0} stroke={COLORS.textTertiary} strokeWidth={1} />
          <RechartsTooltip
            content={<MedianTooltip fullLabel={data.periods.full.label} recentLabel={data.periods.recent.label} />}
          />
          <Legend
            wrapperStyle={{ color: COLORS.textPrimary, fontSize: 12 }}
            formatter={(value) => <span style={{ color: COLORS.textPrimary }}>{value}</span>}
          />
          <Bar dataKey="fullMedian" name={data.periods.full.label} fill={COLORS.full}>
            {chartData.map((entry, idx) => (
              <Cell
                key={`full-${idx}`}
                fill={entry.fullMedian >= 0 ? COLORS.full : COLORS.negative}
              />
            ))}
          </Bar>
          <Bar dataKey="recentMedian" name={data.periods.recent.label} fill={COLORS.recent}>
            {chartData.map((entry, idx) => (
              <Cell
                key={`recent-${idx}`}
                fill={entry.recentMedian >= 0 ? COLORS.recent : COLORS.negativeAlt}
              />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>

      <div style={{ marginTop: 8, fontSize: 11, color: COLORS.textTertiary, textAlign: 'right' }}>
        ※ 中央値は外れ値の影響を受けにくい代表値。Tooltipで平均との乖離も確認できます。
      </div>
    </div>
  )
}

interface MedianTooltipProps {
  active?: boolean
  payload?: Array<{ payload: ChartDataPoint }>
  label?: string
  fullLabel: string
  recentLabel: string
}

function MedianTooltip({ active, payload, label, fullLabel, recentLabel }: MedianTooltipProps) {
  if (!active || !payload || payload.length === 0) return null
  const d = payload[0].payload

  const fmtSign = (v: number, digits = 2) => `${v >= 0 ? '+' : ''}${v.toFixed(digits)}`

  // 乖離の解釈
  const interpretGap = (gap: number): { text: string; color: string } => {
    if (Math.abs(gap) < 0.1) return { text: '対称', color: COLORS.textSecondary }
    if (gap > 0) return { text: '右裾（上振れ外れ値）', color: COLORS.positiveAlt }
    return { text: '左裾（下振れ外れ値）', color: COLORS.negativeAlt }
  }

  const fullInterp = interpretGap(d.fullGap)
  const recentInterp = interpretGap(d.recentGap)

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
        minWidth: 240,
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 6 }}>{label}</div>

      {/* 全期間 */}
      <div style={{ marginBottom: 6 }}>
        <div style={{ color: COLORS.full, fontWeight: 600, marginBottom: 2 }}>
          ● {fullLabel} (n={d.fullN})
        </div>
        <div style={{ color: COLORS.textSecondary }}>
          中央値: <span style={{ color: COLORS.textPrimary, fontWeight: 600 }}>{fmtSign(d.fullMedian)}%</span>
          {' | '}
          平均: <span style={{ color: COLORS.textPrimary }}>{fmtSign(d.fullMean)}%</span>
        </div>
        <div style={{ color: COLORS.textSecondary }}>
          平均-中央値: <span style={{ color: COLORS.textPrimary }}>{fmtSign(d.fullGap)}%</span>
          {' '}
          <span style={{ color: fullInterp.color, fontSize: 11 }}>({fullInterp.text})</span>
        </div>
      </div>

      {/* 直近 */}
      <div>
        <div style={{ color: COLORS.recent, fontWeight: 600, marginBottom: 2 }}>
          ● {recentLabel} (n={d.recentN})
        </div>
        <div style={{ color: COLORS.textSecondary }}>
          中央値: <span style={{ color: COLORS.textPrimary, fontWeight: 600 }}>{fmtSign(d.recentMedian)}%</span>
          {' | '}
          平均: <span style={{ color: COLORS.textPrimary }}>{fmtSign(d.recentMean)}%</span>
        </div>
        <div style={{ color: COLORS.textSecondary }}>
          平均-中央値: <span style={{ color: COLORS.textPrimary }}>{fmtSign(d.recentGap)}%</span>
          {' '}
          <span style={{ color: recentInterp.color, fontSize: 11 }}>({recentInterp.text})</span>
        </div>
      </div>
    </div>
  )
}
