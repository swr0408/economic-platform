import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { TSACheckpointData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../common/chartConstants'
import { usePeriodFiltering, formatDateLabelFull, useHiddenSeries, type PeriodType } from '../common/useChartData'
import { NoDataMessage, StandardLineChart } from '../common/ChartComponents'

interface TSACheckpointChartProps {
  data: TSACheckpointData | null
}

// チャートの色設定
const COLORS = {
  value: '#1890ff',    // 旅客数（青）
  ma30: '#ff7300',     // 30日移動平均（オレンジ）
}

export default function TSACheckpointChart({ data }: TSACheckpointChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    )
  }, [data])

  // 期間フィルタリング（デフォルト2年）
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: new Date().getFullYear() - 2,
  })

  // Y軸のドメインを計算（余白を持たせてスケール調整）
  const yAxisDomain = useMemo(() => {
    if (filteredData.length === 0) return [0, 'auto'] as [number, 'auto']

    const values = filteredData
      .flatMap((d) => [d.value, d.ma30])
      .filter((v): v is number => v !== null && v !== undefined)

    if (values.length === 0) return [0, 'auto'] as [number, 'auto']

    const minValue = Math.min(...values)
    const maxValue = Math.max(...values)

    // 最小値から10%の余白、最大値から5%の余白を持たせる
    const padding = (maxValue - minValue) * 0.1
    const adjustedMin = Math.max(0, minValue - padding)
    const adjustedMax = maxValue + padding * 0.5

    return [adjustedMin, adjustedMax] as [number, number]
  }, [filteredData])

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="米航空機旅客者数（TSA Checkpoint）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="米航空機旅客者数（TSA Checkpoint）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 値のフォーマット（百万人単位）
  const formatValue = (value: number | null | undefined): string => {
    if (value === null || value === undefined) return 'N/A'
    return `${(value / 1000000).toFixed(2)}M`
  }

  // ツールチップ用フォーマット
  const formatTooltipValue = (value: unknown, name: string): [string, string] => {
    const displayName = name === 'value' ? '旅客数' : name === 'ma30' ? '30日移動平均' : name
    if (value === null || value === undefined || typeof value !== 'number') return ['N/A', displayName]
    return [`${value.toLocaleString()} 人`, displayName]
  }

  // 最新値
  const latest = data.latest

  return (
    <div id="tsa-checkpoint-chart">
      <ChartContainer
        title="米航空機旅客者数"
        showPeriodSelector={false}
        dataSource="TSA"
        sourceUrl="https://www.tsa.gov/travel/passenger-volumes"
      >
        {/* 最新値表示 */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>最新値: </span>
            {latest && (
              <>
                <span
                  style={{
                    fontSize: 20,
                    fontWeight: 'bold',
                    color: COLORS.value,
                  }}
                >
                  {latest.value !== null ? `${latest.value.toLocaleString()} 人` : 'N/A'}
                </span>
                <span style={{ fontSize: 12, color: TEXT_COLORS.tertiary, marginLeft: 8 }}>
                  ({formatDateLabelFull(latest.date)})
                </span>
              </>
            )}
          </div>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            {latest?.mom_pct !== null && latest?.mom_pct !== undefined && (
              <div style={{ fontSize: 12 }}>
                <span style={{ color: TEXT_COLORS.secondary }}>前月比: </span>
                <span
                  style={{
                    fontWeight: 'bold',
                    color: latest.mom_pct >= 0 ? '#52c41a' : '#ff4d4f',
                  }}
                >
                  {latest.mom_pct >= 0 ? '+' : ''}
                  {latest.mom_pct.toFixed(1)}%
                </span>
              </div>
            )}
            {latest?.yoy_pct !== null && latest?.yoy_pct !== undefined && (
              <div style={{ fontSize: 12 }}>
                <span style={{ color: TEXT_COLORS.secondary }}>前年同月比: </span>
                <span
                  style={{
                    fontWeight: 'bold',
                    color: latest.yoy_pct >= 0 ? '#52c41a' : '#ff4d4f',
                  }}
                >
                  {latest.yoy_pct >= 0 ? '+' : ''}
                  {latest.yoy_pct.toFixed(1)}%
                </span>
              </div>
            )}
          </div>
        </div>

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'value', color: COLORS.value, name: '旅客数', strokeWidth: 1, hide: hiddenSeries.has('value') },
            { dataKey: 'ma30', color: COLORS.ma30, name: '30日移動平均', strokeWidth: 2, hide: hiddenSeries.has('ma30') },
          ]}
          yAxisFormatter={formatValue}
          yDomain={yAxisDomain}
          tooltipLabelFormatter={formatDateLabelFull}
          tooltipFormatter={formatTooltipValue}
          onLegendClick={handleLegendClick}
          showZeroLine={false}
        />
      </ChartContainer>
    </div>
  )
}
