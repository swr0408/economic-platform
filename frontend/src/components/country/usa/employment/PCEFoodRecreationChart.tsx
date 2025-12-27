/**
 * PCEデフレーター飲食宿泊・娯楽チャートコンポーネント
 *
 * BEA NIPA Table 2.4.4U から取得したPCE価格指数を表示
 * - food_services_yoy: 飲食宿泊（Food services and accommodations）前年比
 * - recreation_yoy: 娯楽（Recreation services）前年比
 * - avg_hourly_earnings_yoy: 平均時給 前年比
 *
 * 共通コンポーネントを使用
 */
import { useState } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PCEFoodRecreationData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabelJP,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  StandardLineChart,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface PCEFoodRecreationChartProps {
  data: PCEFoodRecreationData | null
}

// カラー設定
const COLORS = {
  food_services: '#1890ff',       // 飲食宿泊 - 青
  recreation: '#52c41a',          // 娯楽 - 緑
  avg_hourly_earnings: '#fa8c16', // 平均時給 - オレンジ
}

// 系列名（日本語）
const SERIES_NAMES = {
  food_services: '飲食宿泊',
  recreation: '娯楽',
  avg_hourly_earnings: '平均時給',
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function PCEFoodRecreationChart({ data }: PCEFoodRecreationChartProps) {
  const [period, setPeriod] = useState<'default' | 'all' | number>('default')

  // データのソート
  const sortedData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: period,
    defaultStartYear: 2018,
  })

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="PCEデフレーター飲食宿泊・娯楽" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="PCEデフレーター飲食宿泊・娯楽" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release

  // 最新値の配列を作成
  const latestItems = [
    {
      label: SERIES_NAMES.food_services,
      value: latest?.food_services_yoy,
      color: COLORS.food_services,
      format: 'number' as const,
      unit: '%',
      decimals: 2,
    },
    {
      label: SERIES_NAMES.recreation,
      value: latest?.recreation_yoy,
      color: COLORS.recreation,
      format: 'number' as const,
      unit: '%',
      decimals: 2,
    },
    {
      label: SERIES_NAMES.avg_hourly_earnings,
      value: latest?.avg_hourly_earnings_yoy,
      color: COLORS.avg_hourly_earnings,
      format: 'number' as const,
      unit: '%',
      decimals: 2,
    },
  ]

  return (
    <div id="pce-food-recreation">
      <ChartContainer
        title="PCEデフレーター飲食宿泊・娯楽 / 平均時給（前年比）"
        showPeriodSelector={false}
        dataSource="BEA NIPA / FRED"
        sourceUrl="https://www.bea.gov/data/income-saving/personal-income"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={latestItems}
          date={latest?.date}
          nextRelease={nextRelease}
        />

        {/* 期間セレクター */}
        <PeriodSelector onPeriodChange={setPeriod} selectedPeriod={period} />

        {/* 折れ線グラフ */}
        <StandardLineChart
          data={filteredData}
          lines={[
            {
              dataKey: 'food_services_yoy',
              color: COLORS.food_services,
              name: SERIES_NAMES.food_services,
            },
            {
              dataKey: 'recreation_yoy',
              color: COLORS.recreation,
              name: SERIES_NAMES.recreation,
            },
            {
              dataKey: 'avg_hourly_earnings_yoy',
              color: COLORS.avg_hourly_earnings,
              name: SERIES_NAMES.avg_hourly_earnings,
            },
          ]}
          yAxisFormatter={(v) => `${v.toFixed(1)}%`}
          yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
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
