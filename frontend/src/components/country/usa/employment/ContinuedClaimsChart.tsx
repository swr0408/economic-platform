/**
 * 継続失業保険申請件数チャートコンポーネント
 *
 * FRED CCSA / CC4WSA データを使用して継続失業保険申請件数を表示
 *
 * 表示モード:
 * - 現数値（レベル）: 継続申請件数と4週移動平均を折れ線グラフで表示
 *
 * 共通コンポーネントを使用
 */
import { useState } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'
import type { ContinuedClaimsData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  StandardLineChart,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface ContinuedClaimsChartProps {
  data: ContinuedClaimsData | null
}

// カラー設定
const CCSA_COLOR = CHART_COLORS.primary       // 継続申請件数
const CC4WSA_COLOR = CHART_COLORS.orange      // 4週移動平均

// =============================================================================
// ヘルパー関数
// =============================================================================

/** 日付をYYYY年MM月DD日形式にフォーマット */
function formatDateFullJP(dateStr: string): string {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function ContinuedClaimsChart({ data }: ContinuedClaimsChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(3)

  // データのソート
  const sortedData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="継続失業保険申請件数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="継続失業保険申請件数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release

  // 千人単位でフォーマット（1,923,000 → 1,923k）
  const formatThousands = (value: number | null) => {
    if (value === null) return 'N/A'
    return `${(value / 1000).toFixed(0)}k`
  }

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latest) return []

    return [
      { label: '継続申請件数', value: formatThousands(latest.ccsa), color: CCSA_COLOR },
      { label: '4週移動平均', value: formatThousands(latest.cc4wsa), color: CC4WSA_COLOR },
    ]
  }

  return (
    <div id="continued-claims">
      <ChartContainer
        title="継続失業保険申請件数"
        showPeriodSelector={false}
        dataSource="FRED / DOL"
        sourceUrl="https://www.dol.gov/sites/dolgov/files/OPA/newsreleases/ui-claims/20251644.pdf"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latest?.date}
          nextRelease={nextRelease}
        />

        {/* 現数値グラフ */}
        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
        <StandardLineChart
          data={filteredData}
          lines={[
            {
              dataKey: 'ccsa',
              color: CCSA_COLOR,
              name: '継続失業保険申請件数',
            },
            {
              dataKey: 'cc4wsa',
              color: CC4WSA_COLOR,
              name: '4週移動平均',
            },
          ]}
          yAxisFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
          yDomain={['dataMin - 20000', 'dataMax + 20000']}
          tooltipLabelFormatter={formatDateFullJP}
          tooltipFormatter={(value: unknown, name: string) => {
            const v = value as number
            // 4週移動平均は小数点第2位まで表示
            if (name === '4週移動平均') {
              return [`${(v / 1000).toFixed(2)}k`, name]
            }
            return [`${(v / 1000).toFixed(0)}k`, name]
          }}
          showZeroLine={false}
        />
      </ChartContainer>
    </div>
  )
}
