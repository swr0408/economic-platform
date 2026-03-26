/**
 * ECB経常収支チャートコンポーネント
 *
 * データ:
 * - 経常収支（Current Account Balance）
 *
 * データソース:
 * - ECB Data API (BPS - Balance of Payments)
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
  StandardBarChart,
  ChartControlRow,
} from '../../usa/common/ChartComponents'
import { CHART_COLORS } from '../../usa/common/chartConstants'

import type { ECBCurrentAccountData } from '../../../../hooks/useDashboardData'
import type { PeriodValue } from '../../../common/PeriodSelector'

interface ECBCurrentAccountChartProps {
  data: ECBCurrentAccountData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

// カラー設定
const COLORS = {
  balance: CHART_COLORS.primary,
}

export default function ECBCurrentAccountChart({ data }: ECBCurrentAccountChartProps) {
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
    return <LoadingChart title="経常収支（ユーロ圏）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="経常収支（ユーロ圏）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ecb-current-account-chart">
      <ChartContainer
        title="経常収支（ユーロ圏）"
        showPeriodSelector={false}
        dataSource="ECB"
        sourceUrl="https://www.ecb.europa.eu/press/stats/bop/html/index.en.html"
        handbookId="current-account"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '経常収支',
              value: latestValue?.value !== undefined ? `${latestValue.value.toFixed(2)}B€` : undefined,
              color: COLORS.balance,
            },
          ]}
          date={latestValue?.date}
          nextRelease={nextRelease}
        />

        {/* 期間セレクタとデータ比較ボタン */}
        <ChartControlRow
          selectedPeriod={currentPeriod}
          onPeriodChange={setCurrentPeriod}
          indicatorId="eu_current_account_balance"
        />

        {/* チャート表示 */}
        <StandardBarChart
          data={filteredData}
          bars={[
            {
              dataKey: 'value',
              color: COLORS.balance,
              name: '経常収支',
            },
          ]}
          xAxisFormatter={formatDateLabel}
          yAxisFormatter={(v) => `${v.toFixed(0)}B€`}
          tooltipValueFormatter={(v) => `${v.toFixed(2)}B€`}
          tooltipLabelFormatter={formatDateLabelJP}
        />
      </ChartContainer>
    </div>
  )
}
