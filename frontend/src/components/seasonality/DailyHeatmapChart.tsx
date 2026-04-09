import { useEffect, useState, useMemo, useRef } from 'react'
import { Spin, Alert, Typography, Segmented, Popover } from 'antd'
import { InfoCircleOutlined } from '@ant-design/icons'
import axios from 'axios'

const { Text } = Typography

const COLORS = {
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textTertiary: '#64748b',
  border: '#334155',
  gridLine: '#475569',
  positive: '#10b981',
  positiveStrong: '#059669',
  positiveAlt: '#34d399',
  negative: '#ef4444',
  negativeStrong: '#dc2626',
  negativeAlt: '#f87171',
  neutral: '#1e293b',
  cellEmpty: '#0f172a',
  tooltipBg: '#1e293b',
  tooltipBorder: '#475569',
}

interface DailyCell {
  day: number
  n: number
  mean_pct: number
  median_pct?: number
  neg_rate: number
}

interface MonthDaily {
  month: number
  full: DailyCell[]
  recent: DailyCell[]
}

interface DailyStatsResponse {
  symbol: string
  generated_at: string
  periods: {
    full: { start_year: number; end_year: number; label: string }
    recent: { start_year: number; end_year: number; label: string }
  }
  months: MonthDaily[]
}

const MONTH_LABELS = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

type PeriodMode = 'full' | 'recent'
type MetricMode = 'mean' | 'median' | 'neg_rate'

interface DailyHeatmapChartProps {
  symbol: string
}

export default function DailyHeatmapChart({ symbol }: DailyHeatmapChartProps) {
  const [data, setData] = useState<DailyStatsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [periodMode, setPeriodMode] = useState<PeriodMode>('full')
  const [metricMode, setMetricMode] = useState<MetricMode>('mean')
  const [hover, setHover] = useState<{ month: number; day: number; cell: DailyCell; x: number; y: number } | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await axios.get<DailyStatsResponse>(
          `/api/seasonality/${encodeURIComponent(symbol)}/daily-stats`
        )
        setData(response.data)
      } catch (err) {
        console.error('Failed to fetch daily stats:', err)
        if (axios.isAxiosError(err) && err.response?.status === 404) {
          setError('この銘柄の日別統計データはまだ生成されていません。')
        } else {
          setError('日別統計データの取得に失敗しました。')
        }
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [symbol])

  // セルの指標値を取り出す (モードに応じて)
  const getCellValue = (cell: DailyCell): number => {
    if (metricMode === 'mean') return cell.mean_pct
    if (metricMode === 'median') return cell.median_pct ?? 0
    // 下落率: 数値が高いほど下落しやすい → 赤になるよう符号反転
    // 50% → 0, 100% → -50 (強い赤), 0% → +50 (強い緑)
    return 50 - cell.neg_rate * 100
  }

  // カラースケール用の閾値 (銘柄ごとのVolatilityに頑健)
  // - 平均/中央値モード: 全セルの絶対値の 95 パーセンタイルを「最大濃度」にする
  //   → 外れ値1〜2セルで全体が薄くなる問題を回避
  // - 下落率モード: 50% 中心で ±50 を固定スケール (0%や100%で最大濃度)
  const colorScale = useMemo(() => {
    if (!data) return 1
    if (metricMode === 'neg_rate') return 50 // 固定スケール

    const abs: number[] = []
    for (const month of data.months) {
      const cells = periodMode === 'full' ? month.full : month.recent
      for (const c of cells) {
        const v = metricMode === 'mean' ? c.mean_pct : (c.median_pct ?? 0)
        if (Number.isFinite(v)) abs.push(Math.abs(v))
      }
    }
    if (abs.length === 0) return 1
    abs.sort((a, b) => a - b)
    // 95 パーセンタイル (外れ値を除外)
    const idx = Math.floor(abs.length * 0.95)
    const p95 = abs[Math.min(idx, abs.length - 1)]
    return p95 > 0 ? p95 : 1
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, periodMode, metricMode])

  const maxDays = useMemo(() => {
    if (!data) return 23
    let m = 0
    for (const month of data.months) {
      const cells = periodMode === 'full' ? month.full : month.recent
      if (cells.length > m) m = cells.length
    }
    return m || 23
  }, [data, periodMode])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '60px 20px' }}>
        <Spin />
        <p style={{ marginTop: 12, color: COLORS.textSecondary }}>日別統計を読み込み中...</p>
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
      <Alert message="データなし" description="日別統計データがありません。" type="warning" showIcon />
    )
  }

  // セル色: 平均/中央値モードはプラス=緑, マイナス=赤。下落率モードは50%中心 (0.5未満=緑, 0.5超=赤)
  // colorScale は 95 パーセンタイルに基づく正規化値 (Volatilityに頑健)
  const getCellColor = (cell: DailyCell): string => {
    const v = getCellValue(cell)
    if (colorScale === 0) return COLORS.neutral
    // 95 パーセンタイルを 1.0 とし、それを超えるセルは 1.0 にクランプ (飽和)
    const t = Math.min(1, Math.abs(v) / colorScale)
    // 下限を 0.35 に引き上げ、上限 1.0 で視認性を改善
    const alpha = 0.35 + 0.65 * t
    if (v >= 0) {
      return `rgba(16, 185, 129, ${alpha})` // 緑
    } else {
      return `rgba(239, 68, 68, ${alpha})` // 赤
    }
  }

  // セルに表示する数値文字列
  const getCellLabel = (cell: DailyCell): string => {
    if (metricMode === 'mean') {
      return cell.mean_pct.toFixed(2)
    }
    if (metricMode === 'median') {
      return (cell.median_pct ?? 0).toFixed(2)
    }
    // 下落率: パーセント整数
    return Math.round(cell.neg_rate * 100).toString()
  }

  const cellWidth = 42
  const cellHeight = 26
  const monthLabelWidth = 44
  const dayLabelHeight = 20
  const gap = 2
  const svgWidth = monthLabelWidth + (cellWidth + gap) * maxDays
  const svgHeight = dayLabelHeight + (cellHeight + gap) * 12

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
            日別ヒートマップ
          </Text>
          <Popover
            trigger="click"
            placement="bottomLeft"
            overlayStyle={{ maxWidth: 520 }}
            content={
              <div style={{ fontSize: 12, lineHeight: 1.7, maxWidth: 480, color: COLORS.textPrimary }}>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 日別ヒートマップとは</b><br />
                  縦軸=月（1〜12月）、横軸=月初からの<b>営業日インデックス</b>（カレンダー日ではない）。
                  各セルは「その月のN営業日目」の<b>1日リターンの平均</b>を色で表します。
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 平均モード</b><br />
                  日次リターンの平均（%）。<span style={{ color: '#10b981' }}>緑=プラス</span>／<span style={{ color: '#ef4444' }}>赤=マイナス</span>。
                  色が濃いほど絶対値が大きい。
                  <div style={{ color: '#cbd5e1', marginTop: 2 }}>例: 12月の営業日20が濃い緑 → 12月後半に強い上昇日が集中。</div>
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 中央値モード</b><br />
                  日次リターンの中央値（%）。外れ値（極端に大きい/小さい年）の影響を受けにくい
                  <b>代表値</b>。平均モードと比較して、
                  <span style={{ color: '#10b981' }}>平均より中央値が大きくプラス</span>＝安定して上昇しやすい日、
                  <span style={{ color: '#ef4444' }}>平均より中央値が大きくマイナス</span>＝安定して下落しやすい日。
                  <div style={{ color: '#cbd5e1', marginTop: 2 }}>
                    例: 平均は小さくプラスだが中央値が明確にマイナス → 少数の急騰日に引きずられた偽シグナル。中央値で実態を確認。
                  </div>
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 平均 vs 中央値の使い分け</b><br />
                  ・<b>平均</b>は外れ値（リーマン・コロナ等の急落日）に引っ張られやすい<br />
                  ・<b>中央値</b>は「ふつうの年にどうなるか」を表す頑健な指標<br />
                  両者が同じ符号で揃っていれば信頼性が高いシグナル。
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 下落率モード</b><br />
                  その日にマイナスとなった年の割合を、50%中心で表示。
                  <span style={{ color: '#10b981' }}>緑=50%未満（上昇優勢）</span>／<span style={{ color: '#ef4444' }}>赤=50%超（下落優勢）</span>。
                  <div style={{ color: '#cbd5e1', marginTop: 2 }}>例: 9月前半が濃い赤 → 9月の月初〜中盤は負けやすい日が連続。</div>
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 期間切替（全期間 / 直近）</b><br />
                  全期間=長期の構造／直近=直近10年の足元の動き。両者の色パターンの違いで「直近で変質した日」が見える。
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 色スケール（Volatility対応）</b><br />
                  銘柄によって日次リターンの大きさ（Volatility）が違うため、色の濃度は
                  <b>銘柄内の 95 パーセンタイル</b>を最大濃度として正規化しています。
                  これにより VIX のような高ボラ銘柄でも S&P500 のような低ボラ銘柄でも
                  同じ強さで色が出ます。外れ値1〜2セルで全体が薄くなる問題も回避。
                  <div style={{ color: '#cbd5e1', marginTop: 2 }}>
                    ※ 下落率モードは 50% 中心の固定スケール。
                  </div>
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● サンプル数 n（マウスオーバー）</b><br />
                  各セルで集計に使った年数。月末側（営業日19〜23）は n が小さくなりがちなので過信しない。
                  <div style={{ color: '#cbd5e1', marginTop: 2 }}>例: 営業日23の n=3 なら、その日が存在する年が3年だけ。</div>
                </div>
                <div>
                  <b style={{ color: '#fbbf24' }}>● 使い方のヒント</b><br />
                  ・<b>横方向の連続した同色帯</b>＝月の中で持続的なバイアス<br />
                  ・<b>縦方向の同色帯</b>＝季節を超えて同じ営業日番号で発生する効果（給料日／月末リバランス等）<br />
                  ・点として濃い1セル＝特定日に強い偏り
                </div>
              </div>
            }
          >
            <InfoCircleOutlined style={{ color: COLORS.textSecondary, cursor: 'pointer' }} />
          </Popover>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Segmented
            value={periodMode}
            onChange={(v) => setPeriodMode(v as PeriodMode)}
            options={[
              { label: data.periods.full.label, value: 'full' },
              { label: data.periods.recent.label, value: 'recent' },
            ]}
            size="small"
          />
          <Segmented
            value={metricMode}
            onChange={(v) => setMetricMode(v as MetricMode)}
            options={[
              { label: '平均', value: 'mean' },
              { label: '中央値', value: 'median' },
              { label: '下落率', value: 'neg_rate' },
            ]}
            size="small"
          />
        </div>
      </div>

      {/* SVG ヒートマップ */}
      <div ref={containerRef} style={{ overflowX: 'auto', position: 'relative' }}>
        <svg width={svgWidth} height={svgHeight} style={{ display: 'block' }}>
          {/* 列ヘッダー（営業日番号） */}
          {Array.from({ length: maxDays }, (_, i) => {
            const day = i + 1
            const x = monthLabelWidth + i * (cellWidth + gap) + cellWidth / 2
            return (
              <text
                key={`day-${day}`}
                x={x}
                y={dayLabelHeight - 6}
                textAnchor="middle"
                fill={COLORS.textSecondary}
                fontSize={10}
              >
                {day}
              </text>
            )
          })}

          {/* 行（月） */}
          {data.months.map((month, mi) => {
            const cells = periodMode === 'full' ? month.full : month.recent
            const cellMap = new Map(cells.map((c) => [c.day, c]))
            const y = dayLabelHeight + mi * (cellHeight + gap)
            return (
              <g key={`month-${month.month}`}>
                {/* 月ラベル */}
                <text
                  x={monthLabelWidth - 6}
                  y={y + cellHeight / 2 + 4}
                  textAnchor="end"
                  fill={COLORS.textSecondary}
                  fontSize={11}
                >
                  {MONTH_LABELS[month.month - 1]}
                </text>
                {/* セル */}
                {Array.from({ length: maxDays }, (_, di) => {
                  const day = di + 1
                  const cell = cellMap.get(day)
                  const x = monthLabelWidth + di * (cellWidth + gap)
                  if (!cell) {
                    return (
                      <rect
                        key={`cell-${month.month}-${day}`}
                        x={x}
                        y={y}
                        width={cellWidth}
                        height={cellHeight}
                        fill={COLORS.cellEmpty}
                        stroke={COLORS.border}
                        strokeWidth={0.5}
                        rx={2}
                      />
                    )
                  }
                  const color = getCellColor(cell)
                  const label = getCellLabel(cell)
                  return (
                    <g
                      key={`cell-${month.month}-${day}`}
                      style={{ cursor: 'pointer' }}
                      onMouseEnter={(e) => {
                        const rect = (e.currentTarget.ownerSVGElement as SVGSVGElement)
                          ?.parentElement?.getBoundingClientRect()
                        const px = rect ? e.clientX - rect.left : 0
                        const py = rect ? e.clientY - rect.top : 0
                        setHover({ month: month.month, day, cell, x: px, y: py })
                      }}
                      onMouseMove={(e) => {
                        const rect = (e.currentTarget.ownerSVGElement as SVGSVGElement)
                          ?.parentElement?.getBoundingClientRect()
                        const px = rect ? e.clientX - rect.left : 0
                        const py = rect ? e.clientY - rect.top : 0
                        setHover({ month: month.month, day, cell, x: px, y: py })
                      }}
                      onMouseLeave={() => setHover(null)}
                    >
                      <rect
                        x={x}
                        y={y}
                        width={cellWidth}
                        height={cellHeight}
                        fill={color}
                        stroke={COLORS.border}
                        strokeWidth={0.5}
                        rx={2}
                      />
                      <text
                        x={x + cellWidth / 2}
                        y={y + cellHeight / 2 + 3}
                        textAnchor="middle"
                        fill={COLORS.textPrimary}
                        fontSize={9}
                        fontWeight={500}
                        style={{ pointerEvents: 'none', userSelect: 'none' }}
                      >
                        {label}
                      </text>
                    </g>
                  )
                })}
              </g>
            )
          })}
        </svg>

        {/* ホバー情報 (マウス追従、境界で反転) */}
        {hover && (() => {
          const tipW = 200 // 推定幅
          const tipH = 130 // 推定高さ
          const offset = 14
          const containerW = containerRef.current?.clientWidth ?? 0
          const containerH = containerRef.current?.scrollHeight ?? 0
          // 右端を超える場合は左側に出す
          const flipX = hover.x + offset + tipW > containerW
          const flipY = hover.y + offset + tipH > containerH
          const left = flipX ? Math.max(0, hover.x - tipW - offset) : hover.x + offset
          const top = flipY ? Math.max(0, hover.y - tipH - offset) : hover.y + offset
          return (
          <div
            style={{
              position: 'absolute',
              left,
              top,
              background: COLORS.tooltipBg,
              border: `1px solid ${COLORS.tooltipBorder}`,
              borderRadius: 6,
              padding: '8px 12px',
              fontSize: 12,
              color: COLORS.textPrimary,
              lineHeight: 1.6,
              minWidth: 180,
              pointerEvents: 'none',
              boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
              zIndex: 10,
            }}
          >
            <div style={{ fontWeight: 600, marginBottom: 4 }}>
              {MONTH_LABELS[hover.month - 1]} 営業日 {hover.day}
            </div>
            <div style={{ color: COLORS.textSecondary }}>
              平均: <span style={{
                color: hover.cell.mean_pct >= 0 ? COLORS.positive : COLORS.negativeAlt,
                fontWeight: 600,
              }}>
                {hover.cell.mean_pct >= 0 ? '+' : ''}{hover.cell.mean_pct.toFixed(3)}%
              </span>
            </div>
            {hover.cell.median_pct !== undefined && (
              <div style={{ color: COLORS.textSecondary }}>
                中央値: <span style={{
                  color: hover.cell.median_pct >= 0 ? COLORS.positive : COLORS.negativeAlt,
                  fontWeight: 600,
                }}>
                  {hover.cell.median_pct >= 0 ? '+' : ''}{hover.cell.median_pct.toFixed(3)}%
                </span>
              </div>
            )}
            <div style={{ color: COLORS.textSecondary }}>
              下落率: <span style={{ color: COLORS.textPrimary }}>
                {(hover.cell.neg_rate * 100).toFixed(1)}%
              </span>
            </div>
            <div style={{ color: COLORS.textSecondary }}>
              n: <span style={{ color: COLORS.textPrimary }}>{hover.cell.n}</span>
            </div>
          </div>
          )
        })()}
      </div>

      {/* 凡例 */}
      <div style={{
        marginTop: 12,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        fontSize: 11,
        color: COLORS.textTertiary,
        flexWrap: 'wrap',
      }}>
        <span>※ 横軸=月初からの営業日インデックス（最大{maxDays}日）</span>
        <span>
          ※ 色濃度は{metricMode === 'neg_rate' ? '50%中心の固定スケール' : '銘柄内 95 パーセンタイル基準'}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span>強くマイナス</span>
          <div style={{ display: 'flex' }}>
            {[1, 0.7, 0.4, 0.15, 0, 0.15, 0.4, 0.7, 1].map((t, i) => {
              const isNeg = i < 4
              const alpha = 0.35 + 0.65 * t
              const color = i === 4
                ? 'rgba(100,116,139,0.3)'
                : isNeg
                ? `rgba(239, 68, 68, ${alpha})`
                : `rgba(16, 185, 129, ${alpha})`
              return (
                <div key={i} style={{
                  width: 14,
                  height: 12,
                  background: color,
                  border: `1px solid ${COLORS.border}`,
                }} />
              )
            })}
          </div>
          <span>強くプラス</span>
        </div>
      </div>
    </div>
  )
}
