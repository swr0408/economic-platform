/**
 * ローソク足チャートコンポーネント
 *
 * 経済指標発表時のマーケットインパクト表示用
 * rechartsを使用したシンプルなローソク足チャート
 */
import { useMemo } from 'react'
import {
  ComposedChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Customized,
} from 'recharts'

// ダークテーマカラー
const DARK_THEME = {
  textSecondary: '#94a3b8',
  gridLine: '#475569',
  axisLine: '#64748b',
  tooltipBg: '#334155',
  tooltipBorder: '#475569',
  chartBg: '#1e293b',
  bullish: '#22c55e',    // 上昇（緑）
  bearish: '#ef4444',    // 下落（赤）
  releaseMarker: '#fbbf24', // 発表時刻マーカー（黄）
}

interface CandleData {
  timestamp: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  volume?: number
}

interface CandlestickChartProps {
  data: CandleData[]
  height?: number
  releaseIndex?: number | null  // 発表時刻のインデックス
  interval?: '1m' | '5m'
}

// ローソク足描画コンポーネント（Customized用）
function CandlestickSeries({
  xAxisMap,
  yAxisMap,
  data,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  xAxisMap?: Record<string, any>
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  yAxisMap?: Record<string, any>
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data?: any[]
}) {
  if (!xAxisMap || !yAxisMap || !data) return null

  const xAxis = xAxisMap[0]
  const yAxis = yAxisMap[0]
  if (!xAxis || !yAxis) return null

  const xScale = xAxis.scale
  const yScale = yAxis.scale
  const bandwidth = xAxis.bandwidth?.() || 10

  return (
    <g className="candlestick-series">
      {data.map((d, i) => {
        if (d.high == null || d.low == null || d.open == null || d.close == null) return null

        const color = d.isBullish ? DARK_THEME.bullish : DARK_THEME.bearish
        const x = xScale(d.timeLabel)
        const centerX = x + bandwidth / 2
        const barWidth = Math.max(bandwidth * 0.6, 2)

        const highY = yScale(d.high)
        const lowY = yScale(d.low)
        const openY = yScale(d.open)
        const closeY = yScale(d.close)

        if (isNaN(highY) || isNaN(lowY) || isNaN(openY) || isNaN(closeY)) return null

        const bodyTop = Math.min(openY, closeY)
        const bodyBottom = Math.max(openY, closeY)
        const bodyHeight = Math.max(bodyBottom - bodyTop, 1)

        return (
          <g key={`candle-${i}`}>
            {/* ヒゲ（高値から安値まで） */}
            <line
              x1={centerX}
              y1={highY}
              x2={centerX}
              y2={lowY}
              stroke={color}
              strokeWidth={1}
            />
            {/* ボディ（始値と終値の間） */}
            <rect
              x={centerX - barWidth / 2}
              y={bodyTop}
              width={barWidth}
              height={bodyHeight}
              fill={color}
            />
          </g>
        )
      })}
    </g>
  )
}

export default function CandlestickChart({
  data,
  height = 400,
  releaseIndex,
  interval = '1m',
}: CandlestickChartProps) {
  // データを変換（ローソク足表示用）
  const chartData = useMemo(() => {
    return data.map((d, index) => {
      const open = d.open ?? 0
      const close = d.close ?? 0
      const high = d.high ?? Math.max(open, close)
      const low = d.low ?? Math.min(open, close)
      const isBullish = close >= open

      // 時刻をフォーマット
      let timeLabel = ''
      try {
        const dt = new Date(d.timestamp)
        if (interval === '1m') {
          timeLabel = dt.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' })
        } else {
          timeLabel = dt.toLocaleString('ja-JP', {
            month: 'numeric',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
          })
        }
      } catch {
        timeLabel = String(index)
      }

      return {
        index,
        timestamp: d.timestamp,
        timeLabel,
        open,
        high,
        low,
        close,
        volume: d.volume ?? 0,
        isBullish,
        // Y軸のドメイン計算用にダミーデータポイントを持つ
        dummy: (high + low) / 2,
      }
    })
  }, [data, interval])

  // Y軸のドメインを計算
  const yDomain = useMemo((): [number, number] => {
    if (!chartData.length) return [0, 100]

    const allLows = chartData.map(d => d.low).filter(v => v != null && v > 0)
    const allHighs = chartData.map(d => d.high).filter(v => v != null && v > 0)

    if (!allLows.length || !allHighs.length) return [0, 100]

    const min = Math.min(...allLows)
    const max = Math.max(...allHighs)
    const padding = (max - min) * 0.1

    return [min - padding, max + padding]
  }, [chartData])

  // 発表時刻の位置
  const releaseTime = useMemo(() => {
    if (releaseIndex == null || releaseIndex < 0 || releaseIndex >= chartData.length) {
      return null
    }
    return chartData[releaseIndex]?.timeLabel
  }, [releaseIndex, chartData])

  if (!data.length) {
    return (
      <div
        style={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: DARK_THEME.chartBg,
          color: DARK_THEME.textSecondary,
          borderRadius: 8,
        }}
      >
        データがありません
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart
        data={chartData}
        margin={{ top: 16, right: 16, bottom: 32, left: 8 }}
        style={{ backgroundColor: DARK_THEME.chartBg }}
      >
        <CartesianGrid
          strokeDasharray="3 3"
          stroke={DARK_THEME.gridLine}
          fill={DARK_THEME.chartBg}
        />
        <XAxis
          dataKey="timeLabel"
          type="category"
          axisLine={{ stroke: DARK_THEME.axisLine }}
          tickLine={{ stroke: DARK_THEME.axisLine }}
          tick={{ fill: DARK_THEME.textSecondary, fontSize: 10 }}
          tickMargin={8}
          interval="preserveStartEnd"
          minTickGap={50}
        />
        <YAxis
          type="number"
          domain={yDomain}
          allowDataOverflow={false}
          axisLine={{ stroke: DARK_THEME.axisLine }}
          tickLine={{ stroke: DARK_THEME.axisLine }}
          tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
          tickFormatter={(v: number) => v.toFixed(v >= 100 ? 2 : 4)}
          width={70}
        />
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload || payload.length === 0) return null

            const d = payload[0]?.payload
            if (!d) return null

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
                <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 13, color: '#f1f5f9' }}>
                  {d.timeLabel}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px', fontSize: 12 }}>
                  <span style={{ color: DARK_THEME.textSecondary }}>始値</span>
                  <span style={{ color: '#f1f5f9', textAlign: 'right' }}>{d.open?.toFixed(4)}</span>
                  <span style={{ color: DARK_THEME.textSecondary }}>高値</span>
                  <span style={{ color: DARK_THEME.bullish, textAlign: 'right' }}>{d.high?.toFixed(4)}</span>
                  <span style={{ color: DARK_THEME.textSecondary }}>安値</span>
                  <span style={{ color: DARK_THEME.bearish, textAlign: 'right' }}>{d.low?.toFixed(4)}</span>
                  <span style={{ color: DARK_THEME.textSecondary }}>終値</span>
                  <span style={{ color: d.isBullish ? DARK_THEME.bullish : DARK_THEME.bearish, textAlign: 'right' }}>
                    {d.close?.toFixed(4)}
                  </span>
                </div>
              </div>
            )
          }}
        />

        {/* 発表時刻マーカー */}
        {releaseTime && (
          <ReferenceLine
            x={releaseTime}
            stroke={DARK_THEME.releaseMarker}
            strokeWidth={2}
            strokeDasharray="4 4"
            label={{
              value: '発表',
              position: 'top',
              fill: DARK_THEME.releaseMarker,
              fontSize: 12,
            }}
          />
        )}

        {/* ローソク足をCustomizedで描画 */}
        <Customized
          component={(props: unknown) => (
            <CandlestickSeries
              {...(props as Record<string, unknown>)}
              data={chartData}
            />
          )}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
