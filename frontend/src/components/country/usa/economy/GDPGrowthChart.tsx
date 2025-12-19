import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// Props型定義
interface GDPGrowthItem {
  date: string
  value: number
}

interface GDPGrowthChartProps {
  data: GDPGrowthItem[] | null
  nextRelease?: {
    date: string
    title: string
    estimate_type: string
    quarter: number
    year: number
  } | null
}

interface GDPChartData {
  date: string
  value: number
  [key: string]: string | number | null | undefined
}

export default function GDPGrowthChart({ data, nextRelease }: GDPGrowthChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')

  // propsのデータをチャート用に変換
  const gdpData = useMemo<GDPChartData[]>(() => {
    if (!data || data.length === 0) return []

    const chartData: GDPChartData[] = data.map((item) => ({
      date: item.date,
      value: item.value,
    }))

    // 日付でソート（古い順）
    chartData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return chartData
  }, [data])

  const formatPercentage = (value: number) => {
    const sign = value >= 0 ? '+' : ''
    return `${sign}${value.toFixed(1)}%`
  }

  const formatQuarterLabel = (dateStr: string): string => {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    const year = date.getFullYear()
    const quarter = Math.floor(date.getMonth() / 3) + 1
    return `${year}Q${quarter}`
  }

  // 期間に基づいてデータをフィルタリング
  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all' || gdpData.length === 0) {
      return gdpData
    }

    const cutoffDate = new Date()

    if (selectedPeriod === 'default') {
      // デフォルトは2020年から
      cutoffDate.setFullYear(2020, 0, 1)
    } else {
      // 指定年数前から
      cutoffDate.setFullYear(cutoffDate.getFullYear() - selectedPeriod)
    }

    return gdpData.filter((item) => {
      const itemDate = new Date(item.date)
      return itemDate >= cutoffDate
    })
  }, [gdpData, selectedPeriod])

  const hasData = gdpData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="GDP成長率（前期比年率）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="GDP成長率（前期比年率）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestValue = filteredData.length > 0 ? filteredData[filteredData.length - 1] : null

  return (
    <div id="gdp-growth-chart">
      <ChartContainer
        title="GDP成長率（前期比年率）"
        showPeriodSelector={false}
        dataSource="BEA / FRED"
      >
        {/* 最新値表示 */}
        {latestValue && (
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 12,
              padding: '8px 12px',
              background: '#f5f5f5',
              borderRadius: 8,
            }}
          >
            <div>
              <span style={{ fontSize: 12, color: '#666' }}>最新値: </span>
              <span
                style={{
                  fontSize: 18,
                  fontWeight: 'bold',
                  color: latestValue.value >= 0 ? '#52c41a' : '#ff4d4f',
                }}
              >
                {formatPercentage(latestValue.value)}
              </span>
              <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>
                ({formatQuarterLabel(latestValue.date)})
              </span>
            </div>
            {nextRelease && (
              <div style={{ fontSize: 11, color: '#666', textAlign: 'right' }}>
                <div>次回発表: {nextRelease.date}</div>
                <div style={{ color: '#1890ff' }}>
                  Q{nextRelease.quarter}/{nextRelease.year} ({nextRelease.estimate_type})
                </div>
              </div>
            )}
          </div>
        )}

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color="#1890ff"
          name="GDP成長率"
          height={450}
          tickFormatter={formatPercentage}
          tooltipFormatter={formatPercentage}
          tooltipLabelFormatter={formatQuarterLabel}
          xAxisTickFormatter={formatQuarterLabel}
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
