import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { NFIBData } from '../../../../hooks/useDashboardData'

interface NFIBOptimismChartProps {
  data: NFIBData | null
}

export default function NFIBOptimismChart({ data }: NFIBOptimismChartProps) {
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
    return <LoadingChart title="NFIB中小企業楽観指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="NFIB中小企業楽観指数" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  const formatValue = (value: number) => {
    return value.toFixed(1)
  }

  const formatDateLabel = (dateStr: string): string => {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
  }

  // グラフの色
  const CHART_COLOR = '#722ed1'

  return (
    <div id="nfib-chart">
      <ChartContainer
        title="NFIB中小企業楽観指数"
        showPeriodSelector={false}
        dataSource="NFIB"
        sourceUrl="https://www.nfib.com/surveys/small-business-economic-trends/"
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
            {data.latest && (
              <>
                <span
                  style={{
                    fontSize: 20,
                    fontWeight: 'bold',
                    color: CHART_COLOR,
                  }}
                >
                  {formatValue(data.latest.value)}
                </span>
                <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>
                  ({formatDateLabel(data.latest.date)})
                </span>
              </>
            )}
          </div>
          <div style={{ fontSize: 11, color: '#888', textAlign: 'right' }}>
            {data.next_release && (
              <div>次回発表: {data.next_release.date}</div>
            )}
            <div>毎月第2火曜日発表</div>
          </div>
        </div>

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color={CHART_COLOR}
          name="NFIB楽観指数"
          height={450}
          tickFormatter={formatValue}
          tooltipFormatter={formatValue}
          tooltipLabelFormatter={formatDateLabel}
          xAxisTickFormatter={(dateStr: string) => {
            const date = new Date(dateStr)
            return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
          }}
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
