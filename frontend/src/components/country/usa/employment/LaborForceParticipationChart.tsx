/**
 * 労働参加率チャートコンポーネント
 *
 * FRED CIVPART データを使用して労働参加率を表示
 *
 * 表示モード:
 * - 水準値のみ（前年比・前月比なし）
 *
 * 共通コンポーネントを使用
 */
import { useState } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { LaborForceParticipationData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabelJP,
  type PeriodType,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  StandardLineChart,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface LaborForceParticipationChartProps {
  data: LaborForceParticipationData | null
}

// カラー設定
const DEFAULT_COLOR = '#1890ff'

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function LaborForceParticipationChart({ data }: LaborForceParticipationChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')

  // データのソート
  const sortedData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="労働参加率" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="労働参加率" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release

  // 最新値の表示用アイテム
  const latestItems = latest ? [
    { label: '労働参加率', value: latest.value, color: DEFAULT_COLOR, format: 'number' as const, unit: '%', decimals: 1 },
  ] : []

  return (
    <div id="labor-force-participation">
      <ChartContainer
        title="労働参加率"
        showPeriodSelector={false}
        dataSource="FRED / BLS"
        sourceUrl="https://www.bls.gov/news.release/empsit.toc.htm"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={latestItems}
          date={latest?.date}
          nextRelease={nextRelease}
        />

        {/* 期間セレクター */}
        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

        {/* 水準グラフ */}
        <StandardLineChart
          data={filteredData}
          lines={[
            {
              dataKey: 'value',
              color: DEFAULT_COLOR,
              name: '労働参加率',
            },
          ]}
          yAxisFormatter={(v) => `${v.toFixed(1)}%`}
          yDomain={['dataMin - 0.3', 'dataMax + 0.3']}
          tooltipLabelFormatter={formatDateLabelJP}
          tooltipFormatter={(value: unknown, name: string) => [
            `${(value as number).toFixed(1)}%`,
            name,
          ]}
          showZeroLine={false}
        />
      </ChartContainer>
    </div>
  )
}
