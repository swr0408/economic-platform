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
  ErrorBar,
  Cell,
} from 'recharts'
import axios from 'axios'

const { Text } = Typography

// EconAlpha ダークテーマ
const COLORS = {
  bgPrimary: '#0f172a',
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
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
  neutral: '#64748b',
  full: '#3b82f6',
  recent: '#f59e0b',
}

// 型定義
interface PeriodStats {
  n: number
  mean: number
  median: number
  std: number
  se: number
  ci95_low: number
  ci95_high: number
  neg_rate: number
  mean_median_gap: number
  t_stat: number | null
  p_value: number | null
}

interface MonthData {
  month: number
  full: PeriodStats
  recent: PeriodStats
  diff: {
    mean_diff: number
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
  monthNum: number
  fullMean: number
  fullMedian: number
  fullN: number
  fullStd: number
  fullCiLow: number
  fullCiHigh: number
  fullNegRate: number
  fullGap: number
  fullPValue: number | null
  recentMean: number
  recentMedian: number
  recentN: number
  recentStd: number
  recentCiLow: number
  recentCiHigh: number
  recentNegRate: number
  recentGap: number
  recentPValue: number | null
  meanDiff: number
  negRateDiff: number
  // ErrorBar 用 [下振れ, 上振れ]
  fullErr: [number, number]
  recentErr: [number, number]
}

const MONTH_LABELS = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

interface MonthlyStatsChartProps {
  symbol: string
}

export default function MonthlyStatsChart({ symbol }: MonthlyStatsChartProps) {
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
        <p style={{ marginTop: 12, color: COLORS.textSecondary }}>統計データを読み込み中...</p>
      </div>
    )
  }

  if (error) {
    return (
      <Alert
        message="情報"
        description={error}
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />
    )
  }

  if (!data || !data.months || data.months.length === 0) {
    return (
      <Alert message="データなし" description="統計データがありません。" type="warning" showIcon />
    )
  }

  // データ整形
  const chartData: ChartDataPoint[] = data.months.map((m) => {
    const fullErrLow = Math.max(0, m.full.mean - m.full.ci95_low)
    const fullErrHigh = Math.max(0, m.full.ci95_high - m.full.mean)
    const recentErrLow = Math.max(0, m.recent.mean - m.recent.ci95_low)
    const recentErrHigh = Math.max(0, m.recent.ci95_high - m.recent.mean)
    return {
      month: MONTH_LABELS[m.month - 1],
      monthNum: m.month,
      fullMean: m.full.mean,
      fullMedian: m.full.median,
      fullN: m.full.n,
      fullStd: m.full.std,
      fullCiLow: m.full.ci95_low,
      fullCiHigh: m.full.ci95_high,
      fullNegRate: m.full.neg_rate * 100,
      fullGap: m.full.mean_median_gap,
      fullPValue: m.full.p_value,
      recentMean: m.recent.mean,
      recentMedian: m.recent.median,
      recentN: m.recent.n,
      recentStd: m.recent.std,
      recentCiLow: m.recent.ci95_low,
      recentCiHigh: m.recent.ci95_high,
      recentNegRate: m.recent.neg_rate * 100,
      recentGap: m.recent.mean_median_gap,
      recentPValue: m.recent.p_value,
      meanDiff: m.diff.mean_diff,
      negRateDiff: m.diff.neg_rate_diff * 100,
      fullErr: [fullErrLow, fullErrHigh],
      recentErr: [recentErrLow, recentErrHigh],
    }
  })

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
            月別統計
          </Text>
          <Popover
            trigger="click"
            placement="bottomLeft"
            overlayStyle={{ maxWidth: 520 }}
            content={
              <div style={{ fontSize: 12, lineHeight: 1.7, maxWidth: 480, color: COLORS.textPrimary }}>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 平均騰落率</b><br />
                  対象月のリターン（月初→月末）の算術平均。「この月は平均的に上がる／下がる」傾向の中心値。
                  <div style={{ color: '#cbd5e1', marginTop: 2 }}>例: 12月の平均が +1.5% なら、過去平均で1.5%上昇している。</div>
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 中央値</b><br />
                  サンプルを並べた中央の値。外れ値（暴騰／暴落）の影響を受けにくい代表値。
                  <div style={{ color: '#cbd5e1', marginTop: 2 }}>例: 平均は +1.5% でも中央値が +0.3% なら、一部の大きな上昇に押し上げられている可能性。</div>
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 下落率</b><br />
                  対象月のリターンがマイナスだった年の割合。「負けやすさ」を示す勝率の裏返し。
                  <div style={{ color: '#cbd5e1', marginTop: 2 }}>例: 9月の下落率が 65% なら、過去9月の約3分の2でマイナス。</div>
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● サンプル数 n</b><br />
                  集計に使った年数（月次データ点数）。n が小さいと偶然の影響が大きい。
                  <div style={{ color: '#cbd5e1', marginTop: 2 }}>例: n=20 なら20年分の同月データ。n=5 なら結論は控えめに。</div>
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 95%信頼区間（エラーバー）</b><br />
                  平均がこの範囲に入る確率が95%という幅。t分布で算出。バーが0をまたぐと「真の平均=0」を否定できない。
                  <div style={{ color: '#cbd5e1', marginTop: 2 }}>例: 平均 +1.0%, CI [-0.5, +2.5] → 0をまたぐので有意差なし。</div>
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 長期 vs 直近差分（平均差・下落率差）</b><br />
                  全期間平均と直近10年平均の差。プラスなら直近のほうが強い／マイナスなら直近で弱化。
                  <div style={{ color: '#cbd5e1', marginTop: 2 }}>例: 11月の平均差 +1.2% → 直近10年は11月が長期平均より強い。</div>
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 標準偏差（σ）</b><br />
                  リターンのばらつき。大きいほど月のリスクが高い。
                  <div style={{ color: '#cbd5e1', marginTop: 2 }}>例: σ=2% と σ=6% なら後者が3倍ぶれやすい。</div>
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 平均-中央値の乖離</b><br />
                  分布の歪み。プラスなら右裾（大きな上昇外れ値）、マイナスなら左裾（大きな下落外れ値）。
                  <div style={{ color: '#cbd5e1', marginTop: 2 }}>例: 平均 +2%, 中央値 0% → 乖離 +2%（少数の大上昇に依存）。</div>
                </div>
                <div>
                  <b style={{ color: '#fbbf24' }}>● p値</b><br />
                  「真の月平均=0」を仮定したとき、観測された平均が偶然出る確率（両側t検定）。小さいほど偶然と言いにくい。
                  <div style={{ color: '#cbd5e1', marginTop: 2 }}>*** p&lt;0.01 / ** p&lt;0.05 / * p&lt;0.10 / 例: p=0.02 → 5%水準で有意な月。</div>
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
      <ResponsiveContainer width="100%" height={380}>
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
              value: '平均騰落率 (%)',
              angle: -90,
              position: 'insideLeft',
              fill: COLORS.textSecondary,
              fontSize: 12,
              offset: 16,
            }}
          />
          <ReferenceLine y={0} stroke={COLORS.textTertiary} strokeWidth={1} />
          <RechartsTooltip
            content={<CustomTooltip fullLabel={data.periods.full.label} recentLabel={data.periods.recent.label} />}
          />
          <Legend
            wrapperStyle={{ color: COLORS.textPrimary, fontSize: 12 }}
            formatter={(value) => <span style={{ color: COLORS.textPrimary }}>{value}</span>}
          />
          <Bar dataKey="fullMean" name={data.periods.full.label} fill={COLORS.full}>
            {chartData.map((entry, idx) => (
              <Cell
                key={`full-${idx}`}
                fill={entry.fullMean >= 0 ? COLORS.full : COLORS.negative}
              />
            ))}
            <ErrorBar
              dataKey="fullErr"
              width={4}
              strokeWidth={1.5}
              stroke={COLORS.textPrimary}
              direction="y"
            />
          </Bar>
          <Bar dataKey="recentMean" name={data.periods.recent.label} fill={COLORS.recent}>
            {chartData.map((entry, idx) => (
              <Cell
                key={`recent-${idx}`}
                fill={entry.recentMean >= 0 ? COLORS.recent : COLORS.negativeAlt}
              />
            ))}
            <ErrorBar
              dataKey="recentErr"
              width={4}
              strokeWidth={1.5}
              stroke={COLORS.textPrimary}
              direction="y"
            />
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>

      {/* 注記 */}
      <div style={{ marginTop: 8, fontSize: 11, color: COLORS.textTertiary, textAlign: 'right' }}>
        ※ 白いエラーバーは平均の95%信頼区間（t分布） / p値: *** p&lt;0.01 / ** p&lt;0.05 / * p&lt;0.10（H₀: 月平均=0）
      </div>
    </div>
  )
}

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{ payload: ChartDataPoint }>
  label?: string
  fullLabel: string
  recentLabel: string
}

function CustomTooltip({ active, payload, label, fullLabel, recentLabel }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null
  const d = payload[0].payload

  const fmt = (v: number, digits = 2) => v.toFixed(digits)
  const fmtSign = (v: number, digits = 2) => `${v >= 0 ? '+' : ''}${v.toFixed(digits)}`

  // p値を有意性記号付きでフォーマット
  const fmtP = (p: number | null): { text: string; color: string } => {
    if (p === null || p === undefined) return { text: '—', color: COLORS.textTertiary }
    let stars = ''
    let color = COLORS.textPrimary
    if (p < 0.01) {
      stars = ' ***'
      color = COLORS.positive
    } else if (p < 0.05) {
      stars = ' **'
      color = COLORS.positiveAlt
    } else if (p < 0.10) {
      stars = ' *'
      color = COLORS.recent
    } else {
      color = COLORS.textSecondary
    }
    const text = p < 0.001 ? `<0.001${stars}` : `${p.toFixed(3)}${stars}`
    return { text, color }
  }

  const fullP = fmtP(d.fullPValue)
  const recentP = fmtP(d.recentPValue)

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
      <div style={{ fontWeight: 600, marginBottom: 6, color: COLORS.textPrimary }}>{label}</div>

      {/* 全期間 */}
      <div style={{ marginBottom: 6 }}>
        <div style={{ color: COLORS.full, fontWeight: 600, marginBottom: 2 }}>
          ● {fullLabel} (n={d.fullN})
        </div>
        <div style={{ color: COLORS.textSecondary }}>
          平均: <span style={{ color: COLORS.textPrimary }}>{fmtSign(d.fullMean)}%</span>
          {' | '}
          中央値: <span style={{ color: COLORS.textPrimary }}>{fmtSign(d.fullMedian)}%</span>
        </div>
        <div style={{ color: COLORS.textSecondary }}>
          95% CI: <span style={{ color: COLORS.textPrimary }}>[{fmt(d.fullCiLow)}, {fmt(d.fullCiHigh)}]</span>
        </div>
        <div style={{ color: COLORS.textSecondary }}>
          σ: <span style={{ color: COLORS.textPrimary }}>{fmt(d.fullStd)}%</span>
          {' | '}
          平均-中央値: <span style={{ color: COLORS.textPrimary }}>{fmtSign(d.fullGap)}%</span>
        </div>
        <div style={{ color: COLORS.textSecondary }}>
          p値: <span style={{ color: fullP.color, fontWeight: 600 }}>{fullP.text}</span>
        </div>
      </div>

      {/* 直近 */}
      <div style={{ marginBottom: 6 }}>
        <div style={{ color: COLORS.recent, fontWeight: 600, marginBottom: 2 }}>
          ● {recentLabel} (n={d.recentN})
        </div>
        <div style={{ color: COLORS.textSecondary }}>
          平均: <span style={{ color: COLORS.textPrimary }}>{fmtSign(d.recentMean)}%</span>
          {' | '}
          中央値: <span style={{ color: COLORS.textPrimary }}>{fmtSign(d.recentMedian)}%</span>
        </div>
        <div style={{ color: COLORS.textSecondary }}>
          95% CI: <span style={{ color: COLORS.textPrimary }}>[{fmt(d.recentCiLow)}, {fmt(d.recentCiHigh)}]</span>
        </div>
        <div style={{ color: COLORS.textSecondary }}>
          σ: <span style={{ color: COLORS.textPrimary }}>{fmt(d.recentStd)}%</span>
          {' | '}
          平均-中央値: <span style={{ color: COLORS.textPrimary }}>{fmtSign(d.recentGap)}%</span>
        </div>
        <div style={{ color: COLORS.textSecondary }}>
          p値: <span style={{ color: recentP.color, fontWeight: 600 }}>{recentP.text}</span>
        </div>
      </div>

      {/* 長期 vs 直近差分 */}
      <div style={{ borderTop: `1px solid ${COLORS.border}`, paddingTop: 6 }}>
        <div style={{ color: COLORS.textSecondary }}>
          平均差（直近-全期間）: <span style={{ color: d.meanDiff >= 0 ? COLORS.positive : COLORS.negativeAlt, fontWeight: 600 }}>
            {fmtSign(d.meanDiff)}%
          </span>
        </div>
      </div>
    </div>
  )
}
