/**
 * 新規失業保険申請件数チャートコンポーネント
 *
 * FRED ICSA / IC4WSA データを使用して新規失業保険申請件数を表示
 *
 * 表示モード:
 * - 現数値（レベル）: 新規申請件数と4週移動平均を折れ線グラフで表示
 *
 * 共通コンポーネントを使用
 */
import { useState } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'
import type { InitialClaimsData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabelFullJP,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  StandardLineChart,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface InitialClaimsChartProps {
  data: InitialClaimsData | null
}

// カラー設定
const ICSA_COLOR = CHART_COLORS.primary       // 新規申請件数
const IC4WSA_COLOR = CHART_COLORS.orange      // 4週移動平均

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function InitialClaimsChart({ data }: InitialClaimsChartProps) {
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
    return <LoadingChart title="新規失業保険申請件数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="新規失業保険申請件数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release

  // 千人単位でフォーマット（214000 → 214k）
  const formatThousands = (value: number | null) => {
    if (value === null) return 'N/A'
    return `${(value / 1000).toFixed(0)}k`
  }

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latest) return []

    return [
      { label: '新規申請件数', value: formatThousands(latest.icsa), color: ICSA_COLOR },
      { label: '4週移動平均', value: formatThousands(latest.ic4wsa), color: IC4WSA_COLOR },
    ]
  }

  return (
    <div id="initial-claims">
      <ChartContainer
        title="新規失業保険申請件数"
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
              dataKey: 'icsa',
              color: ICSA_COLOR,
              name: '新規失業保険申請件数',
            },
            {
              dataKey: 'ic4wsa',
              color: IC4WSA_COLOR,
              name: '4週移動平均',
            },
          ]}
          yAxisFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
          yDomain={['dataMin - 20000', 'dataMax + 20000']}
          tooltipLabelFormatter={formatDateLabelFullJP}
          tooltipValueFormatter={(v, dataKey) => {
            // 4週移動平均は小数点第2位まで表示
            if (dataKey === 'ic4wsa') {
              return `${(v / 1000).toFixed(2)}k`
            }
            return `${(v / 1000).toFixed(0)}k`
          }}
          showZeroLine={false}
        />
      </ChartContainer>
    </div>
  )
}
