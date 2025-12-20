import { useState, useMemo } from 'react'
import { Tooltip } from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { FCIData } from '../../../../hooks/useDashboardData'

interface FCIChartProps {
  data: FCIData | null
}

interface ChartDataPoint {
  date: string
  value: number
  baseline: number | null
  oneyear: number | null
  [key: string]: string | number | null | undefined
}

export default function FCIChart({ data }: FCIChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')

  // 両シリーズのデータを統合
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const baselineData = data.baseline?.data || []
    const oneyearData = data.oneyear?.data || []

    // 全ての日付を収集
    const allDates = new Set<string>()
    baselineData.forEach((d) => allDates.add(d.date))
    oneyearData.forEach((d) => allDates.add(d.date))

    // 日付でソート
    const sortedDates = Array.from(allDates).sort(
      (a, b) => new Date(a).getTime() - new Date(b).getTime()
    )

    // データをマージ
    return sortedDates.map((date) => {
      const baselinePoint = baselineData.find((d) => d.date === date)
      const oneyearPoint = oneyearData.find((d) => d.date === date)

      return {
        date,
        value: baselinePoint?.value ?? 0, // ZoomableChartのdataKey用
        baseline: baselinePoint?.value ?? null,
        oneyear: oneyearPoint?.value ?? null,
      }
    })
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all' || chartData.length === 0) {
      return chartData
    }

    const cutoffDate = new Date()

    if (selectedPeriod === 'default') {
      // デフォルトは2010年から
      cutoffDate.setFullYear(2010, 0, 1)
    } else {
      // 指定年数前から
      cutoffDate.setFullYear(cutoffDate.getFullYear() - selectedPeriod)
    }

    return chartData.filter((item) => {
      const itemDate = new Date(item.date)
      return itemDate >= cutoffDate
    })
  }, [chartData, selectedPeriod])

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="FCI-G（金融情勢指数）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="FCI-G（金融情勢指数）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestBaseline = data.baseline?.latest
  const latestOneyear = data.oneyear?.latest

  const formatValue = (value: number | null) => {
    if (value === null || value === undefined) return '-'
    return value.toFixed(2)
  }

  const formatMonthLabel = (dateStr: string): string => {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
  }

  // カスタムツールチップ
  const CustomTooltip = ({
    active,
    payload,
    label,
  }: {
    active?: boolean
    payload?: Array<{
      name: string
      value: number | null
      color: string
      dataKey: string
    }>
    label?: string
  }) => {
    if (!active || !payload || payload.length === 0) return null

    return (
      <div
        style={{
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          border: '1px solid #ddd',
          borderRadius: 8,
          padding: '12px 16px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        }}
      >
        <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14 }}>
          {formatMonthLabel(label || '')}
        </div>
        {payload.map((item, index) => {
          const seriesName = item.dataKey === 'baseline' ? 'Baseline (3-year)' : 'One-year lookback'
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
              <span style={{ display: 'flex', alignItems: 'center', marginRight: 16 }}>
                <span
                  style={{
                    display: 'inline-block',
                    width: 10,
                    height: 10,
                    borderRadius: 2,
                    backgroundColor: item.color,
                    marginRight: 6,
                  }}
                />
                {seriesName}
              </span>
              <span style={{ fontWeight: 500 }}>
                {formatValue(item.value)}
              </span>
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div id="fci-chart">
      <ChartContainer
        title="FCI-G（金融情勢指数）"
        showPeriodSelector={false}
        dataSource="Federal Reserve"
        sourceUrl="https://www.federalreserve.gov/econres/notes/feds-notes/a-new-index-to-measure-us-financial-conditions-20230630.html"
      >
        {/* 最新値表示 */}
        <div
          style={{
            display: 'flex',
            gap: 16,
            marginBottom: 12,
            padding: '12px 16px',
            background: '#f5f5f5',
            borderRadius: 8,
          }}
        >
          {/* Baseline (3-year) */}
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>
              Baseline (3-year)
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
              <span
                style={{
                  fontSize: 20,
                  fontWeight: 'bold',
                  color: '#1890ff',
                }}
              >
                {latestBaseline ? formatValue(latestBaseline.value) : '-'}
              </span>
              {latestBaseline && (
                <span style={{ fontSize: 11, color: '#999' }}>
                  ({formatMonthLabel(latestBaseline.date)})
                </span>
              )}
            </div>
          </div>

          {/* One-year lookback */}
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>
              One-year lookback
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
              <span
                style={{
                  fontSize: 20,
                  fontWeight: 'bold',
                  color: '#52c41a',
                }}
              >
                {latestOneyear ? formatValue(latestOneyear.value) : '-'}
              </span>
              {latestOneyear && (
                <span style={{ fontSize: 11, color: '#999' }}>
                  ({formatMonthLabel(latestOneyear.date)})
                </span>
              )}
            </div>
          </div>
        </div>

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

        <ZoomableChart
          data={filteredData}
          dataKey="baseline"
          color="#1890ff"
          name="Baseline (3-year)"
          height={450}
          tickFormatter={(v) => v.toFixed(1)}
          xAxisTickFormatter={formatMonthLabel}
          enableDynamicTicks={true}
          showZeroLine={true}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={false}
          showDefaultTooltip={false}
          additionalLines={[
            {
              dataKey: 'oneyear',
              color: '#52c41a',
              name: 'One-year lookback',
              strokeWidth: 2,
            },
          ]}
        >
          <Tooltip content={<CustomTooltip />} />
        </ZoomableChart>
      </ChartContainer>
    </div>
  )
}
