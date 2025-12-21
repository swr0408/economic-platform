import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { ISMNonManufacturingData } from '../../../../hooks/useDashboardData'

interface ISMNonManufacturingChartProps {
  data: ISMNonManufacturingData | null
}

export default function ISMNonManufacturingChart({ data }: ISMNonManufacturingChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')

  // データを日付昇順にソートしてDataPoint型に変換
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        value: item.value,
      }))
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all' || chartData.length === 0) {
      return chartData
    }

    const cutoffDate = new Date()

    if (selectedPeriod === 'default') {
      // デフォルトは2020年から
      cutoffDate.setFullYear(2020, 0, 1)
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
    return <LoadingChart title="ISM非製造業景況指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="ISM非製造業景況指数" showPeriodSelector={false} showDataSource={false}>
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

  const formatDateTime = (isoString: string | null): string => {
    if (!isoString) return ''
    try {
      const date = new Date(isoString)
      return date.toLocaleString('ja-JP', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return ''
    }
  }

  // グラフの色（緑系、製造業の青と区別）
  const CHART_COLOR = '#52c41a'

  return (
    <div id="ism-non-manufacturing-chart">
      <ChartContainer
        title="ISM非製造業景況指数"
        showPeriodSelector={false}
        dataSource="ISM / DBnomics"
        sourceUrl="https://www.ismworld.org/supply-management-news-and-reports/reports/ism-report-on-business/"
      >
        {/* 最新値表示 */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
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
            {data.last_updated && (
              <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>
                取得日時: {formatDateTime(data.last_updated)}
              </div>
            )}
          </div>
          {data.next_release && (
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 11, color: '#999' }}>次回発表:</div>
              <div style={{ fontSize: 12, color: '#666', fontWeight: 500 }}>
                {data.next_release.date}
              </div>
              <div style={{ fontSize: 11, color: '#1890ff' }}>
                {data.next_release.label}
              </div>
            </div>
          )}
        </div>

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color={CHART_COLOR}
          name="ISM非製造業PMI"
          height={450}
          tickFormatter={formatValue}
          tooltipFormatter={(value: number) => formatValue(value)}
          tooltipLabelFormatter={(dateStr: string) => formatDateLabel(dateStr)}
          xAxisTickFormatter={(dateStr: string) => {
            const date = new Date(dateStr)
            return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
          }}
          enableDynamicTicks={true}
          showZeroLine={false}
          showFiftyLine={true}
          fiftyLineValue={50}
          connectNulls={true}
          hideLegend={true}
        />
      </ChartContainer>
    </div>
  )
}
