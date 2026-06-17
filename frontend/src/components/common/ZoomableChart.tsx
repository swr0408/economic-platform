import React, { useState, useMemo, useCallback } from 'react'
import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceArea,
  ReferenceLine,
} from 'recharts'
import { dragThrottle } from '../../utils/performance'
import { formatMonthLabel } from '../../utils/dateFormatters'

// EconAlpha ダークテーマカラー
const DARK_THEME = {
  textSecondary: '#94a3b8',
  gridLine: '#475569',
  axisLine: '#64748b',
  referenceLine: '#94a3b8',
  tooltipBg: '#334155',
  tooltipBorder: '#475569',
  chartBg: '#1e293b', // チャートエリア背景色（やや明るめ）
}

type ActiveLabelEvent =
  | {
      activeLabel?: string | number
    }
  | undefined

interface DataPoint {
  date: string
  value: number | null
  dateValue?: number
  [key: string]: unknown
}

// 数値タイムスタンプ(ms) → 'YYYY-MM-DD'（時間軸モードのラベル/フォーマッタ用）
function tsToDateStr(ts: number): string {
  const d = new Date(ts)
  if (isNaN(d.getTime())) return String(ts)
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

interface AdditionalLine {
  dataKey: string
  color: string
  name: string
  strokeWidth?: number
  yAxisId?: string
  strokeDasharray?: string
  type?: 'monotone' | 'linear' | 'step' | 'stepBefore' | 'stepAfter'
  seriesType?: 'line' | 'bar'
}

interface ZoomableChartProps {
  data: DataPoint[]
  dataKey?: string
  height?: number
  color?: string
  strokeWidth?: number
  name?: string
  domain?: [string | number, string | number]
  tickFormatter?: (value: number) => string
  tooltipFormatter?: (value: number) => string
  tooltipLabelFormatter?: (value: string) => string
  xAxisTickFormatter?: (value: string) => string
  yAxisTicks?: number[]
  yAxisInterval?: number
  showZeroLine?: boolean
  showFiftyLine?: boolean
  zeroLineValue?: number
  fiftyLineValue?: number
  children?: React.ReactNode
  enableDynamicTicks?: boolean
  hideLegend?: boolean
  hideMainLine?: boolean
  initialHiddenLines?: string[]
  showDefaultTooltip?: boolean
  onLegendClick?: (dataKey: string) => void
  rightYAxis?: {
    domain?: [string | number, string | number]
    ticks?: number[]
    tickFormatter?: (value: number) => string
  }
  rightYAxes?: {
    id: string
    domain?: [string | number, string | number]
    ticks?: number[]
    tickFormatter?: (value: number) => string
    color?: string
  }[]
  xAxisLabel?: string
  yAxisLabel?: string
  xAxisInterval?: number | 'preserveStart' | 'preserveEnd' | 'preserveStartEnd' | 'equidistantPreserveStart'
  margin?: {
    top?: number
    right?: number
    bottom?: number
    left?: number
  }
  responsiveMargin?: boolean
  connectNulls?: boolean
  additionalLines?: AdditionalLine[]
  chartType?: 'line' | 'bar'
  /** X軸を時間比例軸(type=number, scale=time)にする。data に dateValue(ms) が必要。
   *  異頻度データ混在時に実日付位置で描画し、点の圧縮(つぶれ)を防ぐ。 */
  useTimeAxis?: boolean
}

export default function ZoomableChart({
  data,
  dataKey = 'value',
  height = 400,
  color = '#1890ff',
  strokeWidth = 2,
  name,
  domain = ['dataMin', 'dataMax'],
  tickFormatter,
  tooltipFormatter,
  tooltipLabelFormatter,
  xAxisTickFormatter,
  yAxisTicks,
  yAxisInterval = 0,
  showZeroLine = true,
  showFiftyLine = false,
  zeroLineValue = 0,
  fiftyLineValue = 50,
  children,
  enableDynamicTicks = true,
  hideLegend = false,
  hideMainLine = false,
  initialHiddenLines = [],
  showDefaultTooltip = true,
  onLegendClick,
  rightYAxis,
  rightYAxes,
  xAxisLabel,
  yAxisLabel,
  xAxisInterval = 'preserveStartEnd',
  connectNulls = false,
  margin,
  responsiveMargin = false,
  additionalLines = [],
  chartType = 'line',
  useTimeAxis = false,
}: ZoomableChartProps) {
  const [refAreaLeft, setRefAreaLeft] = useState<string | null>(null)
  const [refAreaRight, setRefAreaRight] = useState<string | null>(null)
  const [currentData, setCurrentData] = useState(data)
  const [hiddenLines, setHiddenLines] = useState<Set<string>>(new Set(initialHiddenLines))

  const chartMargin = useMemo(() => {
    if (margin) {
      return margin
    }

    if (responsiveMargin) {
      return {
        top: 16,
        right: 24,
        bottom: xAxisLabel ? 56 : 32,
        left: yAxisLabel ? 56 : 32,
      }
    }

    return {
      top: 16,
    }
  }, [margin, responsiveMargin, xAxisLabel, yAxisLabel])

  // データが更新されたらリセット
  React.useEffect(() => {
    if (data.length > 0) {
      setCurrentData(data)
    }
  }, [data])

  const handleMouseDown = useCallback(
    dragThrottle((event: ActiveLabelEvent) => {
      if (event?.activeLabel) {
        setRefAreaLeft(String(event.activeLabel))
      }
    }),
    []
  )

  const handleMouseMove = useCallback(
    dragThrottle((event: ActiveLabelEvent) => {
      if (refAreaLeft && event?.activeLabel) {
        setRefAreaRight(String(event.activeLabel))
      }
    }),
    [refAreaLeft]
  )

  const handleMouseUp = useCallback(() => {
    if (refAreaLeft && refAreaRight) {
      // 時間軸モードでは activeLabel が数値(ms)なので数値順で大小比較する
      const lte = useTimeAxis
        ? Number(refAreaLeft) <= Number(refAreaRight)
        : refAreaLeft <= refAreaRight
      const [newLeft, newRight] = lte ? [refAreaLeft, refAreaRight] : [refAreaRight, refAreaLeft]

      // Zoom機能: 選択された範囲のデータのみ表示
      const matchKey = (item: DataPoint) =>
        useTimeAxis ? String(item.dateValue) : item.date
      const leftIndex = data.findIndex((item) => matchKey(item) === newLeft)
      const rightIndex = data.findIndex((item) => matchKey(item) === newRight)

      if (leftIndex !== -1 && rightIndex !== -1) {
        const zoomedData = data.slice(leftIndex, rightIndex + 1)
        setCurrentData(zoomedData)
      }
    }
    setRefAreaLeft(null)
    setRefAreaRight(null)
  }, [refAreaLeft, refAreaRight, data, useTimeAxis])

  // 動的Y軸ティック計算（表示中のラインのみ考慮）
  const dynamicYAxisTicks = useMemo(() => {
    if (!enableDynamicTicks || yAxisTicks) {
      return yAxisTicks
    }

    if (!currentData.length) return undefined

    // 現在表示されているデータから値を取得（非表示ラインを除外）
    const values: number[] = []
    const isRightAxis = (axisId?: string) =>
      typeof axisId === 'string' && axisId.startsWith('right')

    currentData.forEach((item) => {
      // メインのデータキーの値（非表示でない場合）
      if (!hideMainLine && !hiddenLines.has(dataKey)) {
        const mainValue = item[dataKey]
        if (typeof mainValue === 'number' && !isNaN(mainValue) && mainValue !== null) {
          values.push(mainValue)
        }
      }

      // 追加ラインの値（非表示でない場合）
      additionalLines.forEach((line) => {
        if (!hiddenLines.has(line.dataKey) && !isRightAxis(line.yAxisId)) {
          const lineValue = item[line.dataKey]
          if (typeof lineValue === 'number' && !isNaN(lineValue) && lineValue !== null) {
            values.push(lineValue)
          }
        }
      })
    })

    if (values.length === 0) return undefined

    const min = Math.min(...values)
    const max = Math.max(...values)
    const range = max - min

    // 範囲が0の場合の処理
    if (range === 0) {
      const value = min
      if (value === 0) return [-0.5, 0, 0.5]
      const absValue = Math.abs(value)
      const step = absValue > 1 ? 1 : 0.1
      return [value - step, value, value + step]
    }

    // 適切なステップサイズを計算
    let step: number
    const magnitude = Math.pow(10, Math.floor(Math.log10(range)))
    const normalizedRange = range / magnitude

    if (normalizedRange <= 1) {
      step = magnitude * 0.2
    } else if (normalizedRange <= 2) {
      step = magnitude * 0.5
    } else if (normalizedRange <= 5) {
      step = magnitude
    } else {
      step = magnitude * 2
    }

    // ティックを生成
    const ticks: number[] = []
    let start = Math.floor(min / step) * step
    const end = Math.ceil(max / step) * step

    // 一番下のティックが最小値より十分上になるよう調整
    if (start <= min + step * 0.1) {
      start += step
    }

    // 数値の精度を決定
    const precision = Math.max(0, -Math.floor(Math.log10(step)) + 1)

    for (let i = start; i <= end; i += step) {
      const tick = Number(i.toFixed(precision))
      if (!ticks.includes(tick) && tick >= min + step * 0.2 && tick <= max - step * 0.1) {
        ticks.push(tick)
      }
    }

    // 0を含める（showZeroLineがtrueで範囲内にある場合）
    if (showZeroLine && zeroLineValue >= min && zeroLineValue <= max) {
      const zeroRounded = Number(zeroLineValue.toFixed(precision))
      if (!ticks.includes(zeroRounded)) {
        ticks.push(zeroRounded)
        ticks.sort((a, b) => a - b)
      }
    }

    if (showFiftyLine && fiftyLineValue >= min && fiftyLineValue <= max) {
      const fiftyRounded = Number(fiftyLineValue.toFixed(precision))
      if (!ticks.includes(fiftyRounded)) {
        ticks.push(fiftyRounded)
        ticks.sort((a, b) => a - b)
      }
    }

    // ティック数が多すぎる場合はシンプルなロジックにフォールバック
    if (ticks.length > 10) {
      return undefined
    }

    return ticks
  }, [
    currentData,
    dataKey,
    enableDynamicTicks,
    yAxisTicks,
    showZeroLine,
    zeroLineValue,
    showFiftyLine,
    fiftyLineValue,
    hiddenLines,
    hideMainLine,
    additionalLines,
  ])

  // 動的Y軸ドメイン計算（表示中のラインのみ考慮）
  const dynamicDomain = useMemo((): [number | string, number | string] => {
    if (!enableDynamicTicks) {
      return domain
    }

    if (!currentData.length) return domain

    // 表示中のラインの値を収集
    const values: number[] = []
    const isRightAxis = (axisId?: string) =>
      typeof axisId === 'string' && axisId.startsWith('right')

    currentData.forEach((item) => {
      // メインのデータキーの値（非表示でない場合）
      if (!hideMainLine && !hiddenLines.has(dataKey)) {
        const mainValue = item[dataKey]
        if (typeof mainValue === 'number' && !isNaN(mainValue) && mainValue !== null) {
          values.push(mainValue)
        }
      }

      // 追加ラインの値（非表示でない場合）
      additionalLines.forEach((line) => {
        if (!hiddenLines.has(line.dataKey) && !isRightAxis(line.yAxisId)) {
          const lineValue = item[line.dataKey]
          if (typeof lineValue === 'number' && !isNaN(lineValue) && lineValue !== null) {
            values.push(lineValue)
          }
        }
      })
    })

    if (values.length === 0) return domain

    const min = Math.min(...values)
    const max = Math.max(...values)
    const padding = (max - min) * 0.1 || 0.5

    return [min - padding, max + padding]
  }, [currentData, dataKey, enableDynamicTicks, domain, hiddenLines, hideMainLine, additionalLines])

  const refAreaData = useMemo(() => {
    if (refAreaLeft && refAreaRight && refAreaLeft !== refAreaRight) {
      return { x1: refAreaLeft, x2: refAreaRight }
    }
    return null
  }, [refAreaLeft, refAreaRight])

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart
        data={currentData}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        margin={chartMargin}
        style={{ backgroundColor: DARK_THEME.chartBg }}
      >
        <defs>
          <linearGradient id="chartAreaBg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={DARK_THEME.chartBg} />
            <stop offset="100%" stopColor={DARK_THEME.chartBg} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
        <XAxis
          type={useTimeAxis ? 'number' : 'category'}
          dataKey={useTimeAxis ? 'dateValue' : 'date'}
          scale={useTimeAxis ? 'time' : 'auto'}
          domain={useTimeAxis ? ['dataMin', 'dataMax'] : undefined}
          tickFormatter={
            useTimeAxis
              ? (v: number) => (xAxisTickFormatter || formatMonthLabel)(tsToDateStr(v))
              : (xAxisTickFormatter || formatMonthLabel)
          }
          axisLine={{ stroke: DARK_THEME.axisLine }}
          tickLine={{ stroke: DARK_THEME.axisLine }}
          tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
          tickMargin={16}
          height={60}
          label={xAxisLabel ? { value: xAxisLabel, position: 'bottom', offset: 10, fill: DARK_THEME.textSecondary } : undefined}
          allowDataOverflow={false}
          interval={useTimeAxis ? undefined : xAxisInterval}
        />
        <YAxis
          yAxisId="left"
          domain={dynamicDomain}
          tickFormatter={tickFormatter}
          ticks={dynamicYAxisTicks}
          interval={dynamicYAxisTicks ? undefined : yAxisInterval}
          axisLine={{ stroke: DARK_THEME.axisLine }}
          tickLine={{ stroke: DARK_THEME.axisLine }}
          tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
          tickMargin={8}
          allowDataOverflow={true}
          label={
            yAxisLabel
              ? { value: yAxisLabel, angle: -90, position: 'insideLeft', offset: -12, fill: DARK_THEME.textSecondary }
              : undefined
          }
        />
        {(() => {
          const axes = rightYAxes && rightYAxes.length > 0
            ? rightYAxes
            : rightYAxis
              ? [{ id: 'right', ...rightYAxis }]
              : []

          return axes.map((axis, index) => (
            <YAxis
              key={axis.id}
              yAxisId={axis.id}
              orientation="right"
              domain={axis.domain || ['dataMin', 'dataMax']}
              ticks={axis.ticks}
              tickFormatter={axis.tickFormatter}
              axisLine={index === 0 ? { stroke: DARK_THEME.axisLine } : false}
              tickLine={index === 0 ? { stroke: DARK_THEME.axisLine } : false}
              tick={{ fill: axis.color || DARK_THEME.textSecondary, fontSize: 11 }}
            />
          ))
        })()}
        {showDefaultTooltip && (
          <Tooltip
            content={({ active, payload, label }) => {
              if (!active || !payload || payload.length === 0) return null

              // 時間軸モードでは label が数値(ms)なので日付文字列へ戻してから整形
              const labelStr = useTimeAxis ? tsToDateStr(Number(label)) : String(label)
              const formattedLabel = tooltipLabelFormatter
                ? tooltipLabelFormatter(labelStr)
                : formatMonthLabel(labelStr)

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
                  {payload.map((item, index) => {
                    const numericValue = typeof item.value === 'number' ? item.value : Number(item.value)
                    const formatted = tooltipFormatter
                      ? tooltipFormatter(numericValue)
                      : `${Math.round(numericValue)}`
                    const itemColor = item.color || '#f1f5f9'

                    return (
                      <div
                        key={index}
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
                              backgroundColor: itemColor,
                              marginRight: 6,
                            }}
                          />
                          {item.name}
                        </span>
                        <span style={{ fontWeight: 500, color: itemColor }}>
                          {formatted}
                        </span>
                      </div>
                    )
                  })}
                </div>
              )
            }}
          />
        )}
        {!hideLegend && (
          <Legend
            onClick={(e) => {
              if (e && typeof e === 'object' && 'dataKey' in e) {
                const dKey = e.dataKey
                if (typeof dKey === 'string') {
                  setHiddenLines((prev) => {
                    const newSet = new Set(prev)
                    if (newSet.has(dKey)) {
                      newSet.delete(dKey)
                    } else {
                      newSet.add(dKey)
                    }
                    return newSet
                  })

                  if (onLegendClick) {
                    onLegendClick(dKey)
                  }
                }
              }
            }}
            wrapperStyle={{ cursor: 'pointer' }}
          />
        )}

        {showZeroLine && (
          <ReferenceLine y={zeroLineValue} stroke={DARK_THEME.referenceLine} strokeWidth={1.5} yAxisId="left" />
        )}

        {showFiftyLine && (
          <ReferenceLine y={fiftyLineValue} stroke={DARK_THEME.referenceLine} strokeWidth={1.5} yAxisId="left" />
        )}

        {!hideMainLine && chartType === 'line' && (
          <Line
            type="monotone"
            dataKey={dataKey}
            stroke={color}
            strokeWidth={strokeWidth}
            dot={false}
            name={name || dataKey}
            yAxisId="left"
            connectNulls={connectNulls}
            hide={hiddenLines.has(dataKey)}
            isAnimationActive={false}
          />
        )}

        {!hideMainLine && chartType === 'bar' && (
          <Bar
            dataKey={dataKey}
            fill={color}
            name={name || dataKey}
            yAxisId="left"
            hide={hiddenLines.has(dataKey)}
            isAnimationActive={false}
          />
        )}

        {additionalLines?.map((line, index) => {
          if (line.seriesType === 'bar') {
            return (
              <Bar
                key={`additional-bar-${index}`}
                dataKey={line.dataKey}
                fill={line.color}
                name={line.name}
                yAxisId={line.yAxisId || 'left'}
                hide={hiddenLines.has(line.dataKey)}
                isAnimationActive={false}
                barSize={10}
              />
            )
          }

          return (
            <Line
              key={`additional-line-${index}`}
              type={line.type || 'monotone'}
              dataKey={line.dataKey}
              stroke={line.color}
              strokeWidth={line.strokeWidth || 2}
              strokeDasharray={line.strokeDasharray}
              dot={false}
              name={line.name}
              yAxisId={line.yAxisId || 'left'}
              connectNulls={connectNulls}
              hide={hiddenLines.has(line.dataKey)}
              isAnimationActive={false}
            />
          )
        })}

        {refAreaData && (
          <ReferenceArea
            x1={useTimeAxis ? Number(refAreaData.x1) : refAreaData.x1}
            x2={useTimeAxis ? Number(refAreaData.x2) : refAreaData.x2}
            strokeOpacity={0.3}
            fillOpacity={0.1}
          />
        )}

        {React.Children.map(children, (child) => {
          if (React.isValidElement(child) && child.type === Line) {
            const childProps = child.props as Record<string, unknown>
            const childDataKey = childProps.dataKey
            if (typeof childDataKey === 'string' && hiddenLines.has(childDataKey)) {
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              return React.cloneElement(child as any, { ...childProps, hide: true })
            }
          }
          return child
        })}
      </ComposedChart>
    </ResponsiveContainer>
  )
}
