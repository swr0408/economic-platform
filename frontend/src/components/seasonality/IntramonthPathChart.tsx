import { useEffect, useState, useMemo } from 'react'
import { Spin, Alert, Typography, Segmented, Popover } from 'antd'
import { InfoCircleOutlined } from '@ant-design/icons'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
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
  full: '#3b82f6',
  recent: '#f59e0b',
}

interface PeriodPath {
  trading_days: number[]
  cum_mean_pct: number[]
  n_per_day: number[]
}

interface MonthPath {
  month: number
  full: PeriodPath
  recent: PeriodPath
}

interface IntramonthPathResponse {
  symbol: string
  generated_at: string
  periods: {
    full: { start_year: number; end_year: number; label: string }
    recent: { start_year: number; end_year: number; label: string }
  }
  months: MonthPath[]
}

const MONTH_OPTIONS = [
  { label: '1月', value: 1 },
  { label: '2月', value: 2 },
  { label: '3月', value: 3 },
  { label: '4月', value: 4 },
  { label: '5月', value: 5 },
  { label: '6月', value: 6 },
  { label: '7月', value: 7 },
  { label: '8月', value: 8 },
  { label: '9月', value: 9 },
  { label: '10月', value: 10 },
  { label: '11月', value: 11 },
  { label: '12月', value: 12 },
]

interface IntramonthPathChartProps {
  symbol: string
  initialMonth?: number
}

export default function IntramonthPathChart({ symbol, initialMonth = 1 }: IntramonthPathChartProps) {
  const [data, setData] = useState<IntramonthPathResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedMonth, setSelectedMonth] = useState<number>(initialMonth)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await axios.get<IntramonthPathResponse>(
          `/api/seasonality/${encodeURIComponent(symbol)}/intramonth-path`
        )
        setData(response.data)
      } catch (err) {
        console.error('Failed to fetch intramonth path:', err)
        if (axios.isAxiosError(err) && err.response?.status === 404) {
          setError('この銘柄の月内パスデータはまだ生成されていません。')
        } else {
          setError('月内パスデータの取得に失敗しました。')
        }
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [symbol])

  const chartData = useMemo(() => {
    if (!data) return []
    const monthEntry = data.months.find((m) => m.month === selectedMonth)
    if (!monthEntry) return []

    const fullDays = monthEntry.full.trading_days
    const recentDays = monthEntry.recent.trading_days
    const maxDays = Math.max(fullDays.length, recentDays.length)

    const points: Array<{
      day: number
      fullPct: number | null
      recentPct: number | null
      fullN: number | null
      recentN: number | null
    }> = []

    for (let i = 0; i < maxDays; i++) {
      points.push({
        day: i + 1,
        fullPct: i < fullDays.length ? monthEntry.full.cum_mean_pct[i] : null,
        recentPct: i < recentDays.length ? monthEntry.recent.cum_mean_pct[i] : null,
        fullN: i < fullDays.length ? monthEntry.full.n_per_day[i] : null,
        recentN: i < recentDays.length ? monthEntry.recent.n_per_day[i] : null,
      })
    }
    return points
  }, [data, selectedMonth])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '60px 20px' }}>
        <Spin />
        <p style={{ marginTop: 12, color: COLORS.textSecondary }}>月内パスを読み込み中...</p>
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
      <Alert message="データなし" description="月内パスデータがありません。" type="warning" showIcon />
    )
  }

  return (
    <div>
      {/* ヘッダー */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 12,
        flexWrap: 'wrap',
        gap: 12,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Text style={{ color: COLORS.textPrimary, fontSize: 14, fontWeight: 600 }}>
            月内累積パス
          </Text>
          <Popover
            trigger="click"
            placement="bottomLeft"
            overlayStyle={{ maxWidth: 500 }}
            content={
              <div style={{ fontSize: 12, lineHeight: 1.7, maxWidth: 460, color: COLORS.textPrimary }}>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 月内累積平均パス</b><br />
                  月初を 0% として、営業日インデックス t（1, 2, 3 ...）ごとにそこまでの累積リターンを取り、過去年で平均した曲線。
                  「対象月の中で、どのタイミングで動きが集中しているか」を可視化します。
                </div>
                <div style={{ marginBottom: 6, color: '#cbd5e1' }}>
                  <b>見方の例:</b><br />
                  ・前半で上がって後半に減速 → <b>月初買い／月末売り</b>の傾向<br />
                  ・後半に急上昇 → <b>月末ラリー</b>（月末リバランス・配当再投資など）<br />
                  ・全体に右肩下がり → 平均的に「持っているとマイナス」になる月
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 横軸（営業日インデックス）</b><br />
                  カレンダー日ではなく <b>月初からの取引日番号</b>。月によって最終日が異なります（19〜23日程度）。
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 全期間 vs 直近</b><br />
                  青線=全期間平均（長期構造）／橙線=直近10年平均（足元の動き）。差が広がっているほど傾向が変化しています。
                </div>
                <div>
                  <b style={{ color: '#fbbf24' }}>● 日別サンプル数 n</b><br />
                  各営業日インデックスで集計に使った年数。月末側ほど営業日が存在しない年が出るため n が小さくなります。
                  <div style={{ color: '#cbd5e1', marginTop: 2 }}>例: 営業日23の n=3 なら、その日まで取引がある年が3年しかないため過信は禁物。</div>
                </div>
              </div>
            }
          >
            <InfoCircleOutlined style={{ color: COLORS.textSecondary, cursor: 'pointer' }} />
          </Popover>
        </div>
      </div>

      {/* 月選択 */}
      <div style={{ marginBottom: 12, overflowX: 'auto' }}>
        <Segmented
          value={selectedMonth}
          onChange={(val) => setSelectedMonth(val as number)}
          options={MONTH_OPTIONS}
          size="small"
        />
      </div>

      {/* 期間情報 */}
      <div style={{ marginBottom: 12, fontSize: 12, color: COLORS.textSecondary }}>
        <span style={{ marginRight: 16 }}>
          <span style={{ display: 'inline-block', width: 12, height: 2, background: COLORS.full, marginRight: 6, verticalAlign: 'middle' }} />
          全期間: {data.periods.full.label}
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 2, background: COLORS.recent, marginRight: 6, verticalAlign: 'middle' }} />
          {data.periods.recent.label}: {data.periods.recent.start_year}-{data.periods.recent.end_year}
        </span>
      </div>

      {/* グラフ */}
      <ResponsiveContainer width="100%" height={360}>
        <LineChart data={chartData} margin={{ top: 16, right: 24, left: 8, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={COLORS.gridLine} opacity={0.3} />
          <XAxis
            dataKey="day"
            stroke={COLORS.axisLine}
            tick={{ fill: COLORS.textSecondary, fontSize: 12 }}
            label={{
              value: '営業日',
              position: 'insideBottomRight',
              fill: COLORS.textSecondary,
              fontSize: 11,
              offset: -2,
            }}
          />
          <YAxis
            stroke={COLORS.axisLine}
            tick={{ fill: COLORS.textSecondary, fontSize: 12 }}
            label={{
              value: '累積騰落率 (%)',
              angle: -90,
              position: 'insideLeft',
              fill: COLORS.textSecondary,
              fontSize: 12,
              offset: 16,
            }}
          />
          <ReferenceLine y={0} stroke={COLORS.textTertiary} strokeWidth={1} />
          <RechartsTooltip
            content={
              <CustomTooltip
                fullLabel={data.periods.full.label}
                recentLabel={data.periods.recent.label}
              />
            }
          />
          <Legend
            wrapperStyle={{ color: COLORS.textPrimary, fontSize: 12 }}
            formatter={(value) => <span style={{ color: COLORS.textPrimary }}>{value}</span>}
          />
          <Line
            type="monotone"
            dataKey="fullPct"
            name={data.periods.full.label}
            stroke={COLORS.full}
            strokeWidth={2}
            dot={{ r: 2.5, fill: COLORS.full }}
            activeDot={{ r: 5 }}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="recentPct"
            name={data.periods.recent.label}
            stroke={COLORS.recent}
            strokeWidth={2}
            dot={{ r: 2.5, fill: COLORS.recent }}
            activeDot={{ r: 5 }}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>

      <div style={{ marginTop: 8, fontSize: 11, color: COLORS.textTertiary, textAlign: 'right' }}>
        ※ 横軸は月初からの営業日インデックス（カレンダー日ではない）
      </div>
    </div>
  )
}

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{ payload: { day: number; fullPct: number | null; recentPct: number | null; fullN: number | null; recentN: number | null } }>
  label?: number
  fullLabel: string
  recentLabel: string
}

function CustomTooltip({ active, payload, label, fullLabel, recentLabel }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null
  const d = payload[0].payload

  const fmtSign = (v: number | null, digits = 2) =>
    v === null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(digits)}%`

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
        minWidth: 200,
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 6 }}>営業日 {label}</div>
      <div style={{ marginBottom: 4 }}>
        <span style={{ color: COLORS.full, fontWeight: 600 }}>● {fullLabel}</span>
        <span style={{ color: COLORS.textSecondary, marginLeft: 8 }}>(n={d.fullN ?? '—'})</span>
        <div style={{ color: COLORS.textPrimary, marginLeft: 14 }}>{fmtSign(d.fullPct)}</div>
      </div>
      <div>
        <span style={{ color: COLORS.recent, fontWeight: 600 }}>● {recentLabel}</span>
        <span style={{ color: COLORS.textSecondary, marginLeft: 8 }}>(n={d.recentN ?? '—'})</span>
        <div style={{ color: COLORS.textPrimary, marginLeft: 14 }}>{fmtSign(d.recentPct)}</div>
      </div>
    </div>
  )
}
