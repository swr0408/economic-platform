import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { CapacityUtilizationData } from '../../../../hooks/useDashboardData'

interface CapacityUtilizationChartProps {
  data: CapacityUtilizationData | null
}

export default function CapacityUtilizationChart({ data }: CapacityUtilizationChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    )
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    if (chartData.length === 0) return []

    if (selectedPeriod === 'all') {
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
    return <LoadingChart title="設備稼働率（Capacity Utilization）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="設備稼働率（Capacity Utilization）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  const formatValue = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'N/A'
    return `${value.toFixed(1)}%`
  }

  const formatDateLabel = (dateStr: string): string => {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
  }

  // 最新値
  const latest = data.latest

  return (
    <div id="capacity-utilization-chart">
      <ChartContainer
        title="設備稼働率（Capacity Utilization）"
        showPeriodSelector={false}
        dataSource="FRED (FRB)"
        sourceUrl="https://www.federalreserve.gov/releases/G17/default.htm"
      >
        {/* 最新値表示 */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 12,
            padding: '12px 16px',
            background: '#f5f5f5',
            borderRadius: 8,
          }}
        >
          <div>
            <span style={{ fontSize: 12, color: '#666' }}>最新値: </span>
            {latest && (
              <>
                <span
                  style={{
                    fontSize: 20,
                    fontWeight: 'bold',
                    color: '#1890ff',
                  }}
                >
                  {formatValue(latest.value)}
                </span>
                <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>
                  ({formatDateLabel(latest.date)})
                </span>
              </>
            )}
          </div>
          <div style={{ fontSize: 11, color: '#888', textAlign: 'right' }}>
            {data.next_release && (
              <div>次回発表: {data.next_release.date}</div>
            )}
          </div>
        </div>

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color="#1890ff"
          name="設備稼働率"
          height={450}
          tickFormatter={formatValue}
          tooltipFormatter={formatValue}
          tooltipLabelFormatter={formatDateLabel}
          xAxisTickFormatter={formatDateLabel}
          enableDynamicTicks={true}
          showZeroLine={false}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={true}
        />
      </ChartContainer>
    </div>
  )
}
