/**
 * 欧州経済政策不確実性指数チャートコンポーネント
 *
 * FREDから European Policy Uncertainty Index データを取得し、表示
 *
 * データ:
 * - European Economic Policy Uncertainty Index
 *
 * データソース:
 * - FRED (Federal Reserve Economic Data)
 * - 元データ: Economic Policy Uncertainty Project (policyuncertainty.com)
 *
 * 発表スケジュール:
 * - 日次更新（毎日 2:00 JST）
 */
import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'

import { type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, ChartControlRow } from '../../usa/common/ChartComponents'
import { TEXT_COLORS, LATEST_VALUE_BOX_STYLE } from '../../usa/common/chartConstants'

import type { EuroPolicyUncertaintyData } from '../../../../hooks/useDashboardData'

interface EuroPolicyUncertaintyChartProps {
  data: EuroPolicyUncertaintyData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

// 月次形式（2024-01-01）用のフォーマッター
const formatMonthLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  // YYYY-MM-01 -> YYYY/MM
  const match = dateStr.match(/^(\d{4})-(\d{2})/)
  if (match) {
    return `${match[1]}/${match[2]}`
  }
  return dateStr
}

// 月次形式から年を抽出
const getYearFromMonth = (dateStr: string): number => {
  const match = dateStr.match(/^(\d{4})-\d{2}/)
  return match ? parseInt(match[1], 10) : 0
}

export default function EuroPolicyUncertaintyChart({ data }: EuroPolicyUncertaintyChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data || !data.data) return []

    return data.data.map(point => ({
      date: point.date,
      value: point.value,
    }))
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    if (!chartData.length) return []

    const now = new Date()
    const currentYear = now.getFullYear()

    let startYear: number
    if (selectedPeriod === 'all') {
      return chartData
    } else if (selectedPeriod === 'default') {
      startYear = 2020
    } else if (typeof selectedPeriod === 'number') {
      startYear = currentYear - selectedPeriod
    } else {
      startYear = 2020
    }

    return chartData.filter(item => {
      const year = getYearFromMonth(item.date)
      return year >= startYear
    })
  }, [chartData, selectedPeriod])

  // 最新値を取得
  const latestData = useMemo(() => {
    if (!filteredData.length) return null
    return filteredData[filteredData.length - 1]
  }, [filteredData])

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="欧州経済政策不確実性指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="欧州経済政策不確実性指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 値フォーマッター
  const formatValue = (value: number): string => {
    return `${value.toFixed(1)}`
  }

  return (
    <div id="euro-policy-uncertainty-chart">
      <ChartContainer
        title="欧州経済政策不確実性指数"
        showPeriodSelector={false}
        dataSource="Economic Policy Uncertainty"
        sourceUrl="https://www.policyuncertainty.com/europe_monthly.html"
      >
        {/* 最新値表示 */}
        {latestData && (
          <div style={LATEST_VALUE_BOX_STYLE}>
            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
              <div>
                <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>最新値: </span>
                <span
                  style={{
                    fontSize: 18,
                    fontWeight: 'bold',
                    color: TEXT_COLORS.primary,
                  }}
                >
                  {latestData.value !== null ? formatValue(latestData.value) : '-'}
                </span>
              </div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.tertiary }}>
                ({formatMonthLabel(latestData.date)})
              </span>
            </div>
          </div>
        )}

        {/* 期間セレクター + 比較ボタン */}
        <ChartControlRow
          selectedPeriod={selectedPeriod}
          onPeriodChange={setSelectedPeriod}
          indicatorId="euro_policy_uncertainty"
        />

        {/* チャート */}
        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color="#1890ff"
          name="欧州経済政策不確実性指数"
          height={450}
          tickFormatter={formatValue}
          tooltipFormatter={formatValue}
          tooltipLabelFormatter={formatMonthLabel}
          xAxisTickFormatter={formatMonthLabel}
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
