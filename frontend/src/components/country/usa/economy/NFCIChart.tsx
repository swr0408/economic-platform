/**
 * シカゴ連銀金融環境指数（NFCI）チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { NFCIData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../common/chartConstants'
import { usePeriodFiltering, type PeriodType } from '../common/useChartData'
import { NoDataMessage } from '../common/ChartComponents'

interface NFCIChartProps {
  data: NFCIData | null
}

export default function NFCIChart({ data }: NFCIChartProps) {
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
    defaultStartYear: 2010,
  })

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="シカゴ連銀金融環境指数（NFCI）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="シカゴ連銀金融環境指数（NFCI）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const formatValue = (value: number) => {
    const sign = value >= 0 ? '+' : ''
    return `${sign}${value.toFixed(2)}`
  }

  const formatWeekLabel = (dateStr: string): string => {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`
  }

  // グラフの色と統一
  const CHART_COLOR = '#1890ff'

  return (
    <div id="nfci-chart">
      <ChartContainer
        title="シカゴ連銀金融環境指数（NFCI）"
        showPeriodSelector={false}
        dataSource="FRED (Chicago Fed)"
        sourceUrl="https://www.chicagofed.org/research/data/nfci/current-data"
      >
        {/* 最新値表示 */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>最新値: </span>
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
                <span style={{ fontSize: 12, color: TEXT_COLORS.tertiary, marginLeft: 8 }}>
                  ({formatWeekLabel(data.latest.date)})
                </span>
              </>
            )}
          </div>
          <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, textAlign: 'right' }}>
            <div>正値: 金融引き締め / 負値: 金融緩和</div>
            <div>毎週水曜日更新</div>
          </div>
        </div>

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color="#1890ff"
          name="NFCI"
          height={450}
          tickFormatter={formatValue}
          tooltipFormatter={formatValue}
          tooltipLabelFormatter={formatWeekLabel}
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
