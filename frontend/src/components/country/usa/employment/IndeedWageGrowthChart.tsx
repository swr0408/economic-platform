/**
 * Indeed賃金トラッカーチャートコンポーネント
 *
 * Indeed Hiring Lab データを使用して求人掲載賃金の成長率を表示
 * - value: 原数値（前年同月比）
 * - ma3: 3ヶ月移動平均
 *
 * 共通コンポーネントを使用
 */
import { useState } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { IndeedWageTrackerData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabelJP,
} from '../common/useChartData'
import {
  SimpleLatestValueBox,
  NoDataMessage,
  StandardLineChart,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface IndeedWageGrowthChartProps {
  data: IndeedWageTrackerData | null
}

// カラー設定
const COLORS = {
  value: '#1890ff',     // 原数値 - 青
  ma3: '#52c41a',       // 3ヶ月平均 - 緑
}

// 系列名（日本語）
const SERIES_NAMES = {
  value: 'Indeed賃金トラッカー',
  ma3: '3ヶ月移動平均',
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function IndeedWageGrowthChart({ data }: IndeedWageGrowthChartProps) {
  const [period, setPeriod] = useState<'default' | 'all' | number>('default')

  // データのソート
  const sortedData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: period,
    defaultStartYear: 2020,
  })

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="Indeed賃金トラッカー" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="Indeed賃金トラッカー" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release

  return (
    <div id="indeed-wage-tracker">
      <ChartContainer
        title="Indeed賃金トラッカー"
        showPeriodSelector={false}
        dataSource="Indeed Hiring Lab"
        sourceUrl="https://www.hiringlab.org/jp/"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="Indeed賃金トラッカー"
          value={latest?.value}
          subValue={latest?.ma3}
          subLabel="3ヶ月平均"
          valueColor={COLORS.value}
          subValueColor={COLORS.ma3}
          date={latest?.date}
          nextRelease={nextRelease}
          format="number"
          unit="%"
          decimals={2}

        />

        {/* 期間セレクター */}
        <PeriodSelector onPeriodChange={setPeriod} selectedPeriod={period} />

        {/* 折れ線グラフ */}
        <StandardLineChart
          data={filteredData}
          lines={[
            {
              dataKey: 'value',
              color: COLORS.value,
              name: SERIES_NAMES.value,
            },
            {
              dataKey: 'ma3',
              color: COLORS.ma3,
              name: SERIES_NAMES.ma3,
            },
          ]}
          yAxisFormatter={(v) => `${v.toFixed(1)}%`}
          yDomain={['dataMin - 0.3', 'dataMax + 0.3']}
          tooltipLabelFormatter={formatDateLabelJP}
          tooltipFormatter={(value: unknown, name: string) => [
            `${(value as number).toFixed(2)}%`,
            name,
          ]}
          showZeroLine={true}
        />
      </ChartContainer>
    </div>
  )
}
