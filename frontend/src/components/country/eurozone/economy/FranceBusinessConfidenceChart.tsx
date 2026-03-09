/**
 * フランス企業信頼感チャートコンポーネント
 *
 * データ:
 * - 企業信頼感（Business Confidence）
 *
 * データソース:
 * - INSEE (https://www.insee.fr/)
 * - DB: economic_calendar_events（FMP蓄積データ）
 *
 * 発表スケジュール:
 * - 月次（FMPカレンダーから取得）
 */
import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'

import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabel,
  formatDateLabelJP,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
  ChartControlRow,
} from '../../usa/common/ChartComponents'
import { CHART_COLORS } from '../../usa/common/chartConstants'

import type { FranceBusinessConfidenceData } from '../../../../hooks/useDashboardData'
import type { PeriodValue } from '../../../common/PeriodSelector'

interface FranceBusinessConfidenceChartProps {
  data: FranceBusinessConfidenceData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

// カラー設定
const COLORS = {
  confidence: CHART_COLORS.primary,
}

export default function FranceBusinessConfidenceChart({ data }: FranceBusinessConfidenceChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)

  // データを変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []
    return data.data.map(item => ({
      date: item.date,
      value: item.value,
    }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  const hasData = (data?.data?.length ?? 0) > 0

  // 最新値を取得
  const latestValue = data?.latest
  const nextRelease = data?.next_release ?? null

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="企業信頼感（フランス）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="企業信頼感（フランス）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="france-business-confidence-chart">
      <ChartContainer
        title="フランスINSEE企業景況感（フランス）"
        showPeriodSelector={false}
        dataSource="INSEE"
        sourceUrl="https://www.insee.fr/en/recherche?q=Business+indicator&debut=0"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '企業信頼感',
              value: latestValue?.value !== undefined ? latestValue.value.toFixed(1) : undefined,
              color: COLORS.confidence,
            },
          ]}
          date={latestValue?.date}
          nextRelease={nextRelease}
        />

        {/* 期間セレクタとデータ比較ボタン */}
        <ChartControlRow
          selectedPeriod={currentPeriod}
          onPeriodChange={setCurrentPeriod}
          indicatorId="france_business_confidence"
        />

        {/* チャート表示 */}
        <StandardLineChart
          data={filteredData}
          lines={[
            {
              dataKey: 'value',
              color: COLORS.confidence,
              name: '企業信頼感',
            },
          ]}
          xAxisFormatter={formatDateLabel}
          yAxisFormatter={(v) => v.toFixed(0)}
          tooltipValueFormatter={(v) => v.toFixed(1)}
          tooltipLabelFormatter={formatDateLabelJP}
          showZeroLine={false}
          showLegend={false}
          yDomain={['dataMin - 5', 'dataMax + 5']}
        />
      </ChartContainer>
    </div>
  )
}
