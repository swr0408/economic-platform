/**
 * GDPNow（リアルタイムGDP予測）チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { GDPNowData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../common/chartConstants'
import { usePeriodFiltering, type PeriodType } from '../common/useChartData'
import { NoDataMessage } from '../common/ChartComponents'

interface GDPNowChartProps {
  data: GDPNowData | null
}

export default function GDPNowChart({ data }: GDPNowChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    )
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="GDPNow（リアルタイムGDP予測）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="GDPNow（リアルタイムGDP予測）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const formatPercentage = (value: number) => {
    const sign = value >= 0 ? '+' : ''
    return `${sign}${value.toFixed(2)}%`
  }

  const formatDateLabel = (dateStr: string): string => {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`
  }

  // グラフの色
  const CHART_COLOR = '#9346ff' // 紫（GDPNowの特徴的な色）

  return (
    <div id="gdpnow-chart">
      <ChartContainer
        title="GDPNow"
        showPeriodSelector={false}
        dataSource="Atlanta Fed"
        sourceUrl="https://www.atlantafed.org/cqer/research/gdpnow"
      >
        {/* 最新値表示 */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>現在の予測: </span>
            {data.latest && (
              <>
                <span
                  style={{
                    fontSize: 20,
                    fontWeight: 'bold',
                    color: CHART_COLOR,
                  }}
                >
                  {formatPercentage(data.latest.value)}
                </span>
                <span style={{ fontSize: 12, color: TEXT_COLORS.tertiary, marginLeft: 8 }}>
                  ({data.latest.quarter} / {formatDateLabel(data.latest.date)})
                </span>
              </>
            )}
          </div>
        </div>

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color={CHART_COLOR}
          name="GDPNow"
          height={450}
          tickFormatter={formatPercentage}
          tooltipFormatter={formatPercentage}
          tooltipLabelFormatter={(dateStr: string) => {
            const item = filteredData.find(d => d.date === dateStr)
            if (item) {
              return `${item.quarter} (${formatDateLabel(dateStr)})`
            }
            return formatDateLabel(dateStr)
          }}
          xAxisTickFormatter={(dateStr: string) => {
            const date = new Date(dateStr)
            return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
          }}
          enableDynamicTicks={true}
          showZeroLine={true}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={true}
        />
      </ChartContainer>
    </div>
  )
}
