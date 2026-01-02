/**
 * ラインチャートコンポーネント
 *
 * 経済指標発表時のマーケットインパクト表示用（5分足）
 * rechartsを使用したシンプルなラインチャート
 */
import { useMemo } from 'react'
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'

// ダークテーマカラー
const DARK_THEME = {
  textSecondary: '#94a3b8',
  gridLine: '#475569',
  axisLine: '#64748b',
  tooltipBg: '#334155',
  tooltipBorder: '#475569',
  chartBg: '#1e293b',
  lineColor: '#3b82f6',    // ライン色（青）
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

interface LineChartProps {
  data: CandleData[]
  height?: number
  releaseIndex?: number | null  // 発表時刻のインデックス
}

export default function LineChart({
  data,
  height = 400,
  releaseIndex,
}: LineChartProps) {
  // データを変換（ライン表示用）
  const chartData = useMemo(() => {
    return data.map((d, index) => {
      const close = d.close ?? d.open ?? 0

      // 時刻をフォーマット（5分足用）
      let timeLabel = ''
      try {
        const dt = new Date(d.timestamp)
        timeLabel = dt.toLocaleString('ja-JP', {
          month: 'numeric',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit'
        })
      } catch {
        timeLabel = String(index)
      }

      return {
        index,
        timestamp: d.timestamp,
        timeLabel,
        close,
        high: d.high ?? close,
        low: d.low ?? close,
        open: d.open ?? close,
      }
    })
  }, [data])

  // Y軸のドメインを計算
  const yDomain = useMemo((): [number, number] => {
    if (!chartData.length) return [0, 100]

    const allValues = chartData
      .flatMap(d => [d.high, d.low, d.close])
      .filter((v): v is number => v != null && v > 0)

    if (!allValues.length) return [0, 100]

    const min = Math.min(...allValues)
    const max = Math.max(...allValues)
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
                  <span style={{ color: '#22c55e', textAlign: 'right' }}>{d.high?.toFixed(4)}</span>
                  <span style={{ color: DARK_THEME.textSecondary }}>安値</span>
                  <span style={{ color: '#ef4444', textAlign: 'right' }}>{d.low?.toFixed(4)}</span>
                  <span style={{ color: DARK_THEME.textSecondary }}>終値</span>
                  <span style={{ color: DARK_THEME.lineColor, textAlign: 'right' }}>
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

        {/* 終値ライン */}
        <Line
          type="monotone"
          dataKey="close"
          stroke={DARK_THEME.lineColor}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
