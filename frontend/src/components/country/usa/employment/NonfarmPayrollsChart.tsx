/**
 * 非農業部門雇用者数チャートコンポーネント
 *
 * FRED データを使用して雇用者数を表示
 * - 非農業部門雇用者数（Total Nonfarm Payrolls: PAYEMS）
 * - 民間雇用者数（Civilian Employment: CE16OV）
 *
 * 共通コンポーネントを使用
 */
import { useState } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { NonfarmPayrollsData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabelJP,
  createUnitFormatter,
  useHiddenSeries,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  StandardLineChart,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface NonfarmPayrollsChartProps {
  data: NonfarmPayrollsData | null
}

// カラー設定（サービスから取得したものを優先、フォールバック用）
const DEFAULT_COLORS = {
  nonfarm: '#1890ff',
  civilian: '#52c41a',
}

// 系列名（日本語）
const SERIES_NAMES = {
  nonfarm: '非農業部門雇用者数',
  civilian: '民間雇用者数',
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function NonfarmPayrollsChart({ data }: NonfarmPayrollsChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

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
    return <LoadingChart title="非農業部門雇用者数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="非農業部門雇用者数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release
  const seriesConfig = data.series_config || {}

  // 色を取得（サービス設定 > デフォルト）
  const getColor = (key: string): string => {
    return seriesConfig[key]?.color || DEFAULT_COLORS[key as keyof typeof DEFAULT_COLORS] || '#1890ff'
  }

  // 最新値の表示用アイテム
  const latestItems = latest ? [
    { label: SERIES_NAMES.nonfarm, value: latest.nonfarm, color: getColor('nonfarm'), format: 'number' as const, unit: 'k', decimals: 0 },
    { label: SERIES_NAMES.civilian, value: latest.civilian, color: getColor('civilian'), format: 'number' as const, unit: 'k', decimals: 0 },
  ] : []

  return (
    <div id="nonfarm-payrolls">
      <ChartContainer
        title="非農業部門雇用者数"
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

        {/* 折れ線グラフ */}
        <StandardLineChart
          data={filteredData}
          lines={[
            {
              dataKey: 'nonfarm',
              color: getColor('nonfarm'),
              name: SERIES_NAMES.nonfarm,
              hide: hiddenSeries.has('nonfarm'),
            },
            {
              dataKey: 'civilian',
              color: getColor('civilian'),
              name: SERIES_NAMES.civilian,
              hide: hiddenSeries.has('civilian'),
            },
          ]}
          yAxisFormatter={(v) => `${v.toLocaleString()}`}
          yDomain={['dataMin - 1000', 'dataMax + 1000']}
          tooltipLabelFormatter={formatDateLabelJP}
          tooltipFormatter={createUnitFormatter('k', 0)}
          showZeroLine={false}
          onLegendClick={handleLegendClick}
        />
      </ChartContainer>
    </div>
  )
}
