/**
 * フィラデルフィア連銀製造業景気指数チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PhiladelphiaFedData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  usePeriodFiltering,
  formatDateLabel,
  useHiddenSeries,
  createNumberFormatter,
  type PeriodType,
} from '../common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface PhiladelphiaFedChartProps {
  data: PhiladelphiaFedData | null
}

// シリーズ設定（10シリーズ）
const SERIES_CONFIG = {
  general_activity_current: { name: '一般活動', color: '#0958D9', strokeWidth: 2 },
  general_activity_future: { name: '一般活動期待', color: '#91CAFF', strokeWidth: 2 },
  new_orders_current: { name: '新規受注', color: '#389e0d', strokeWidth: 2 },
  new_orders_future: { name: '新規受注期待', color: '#b7eb8f', strokeWidth: 2 },
  prices_paid_current: { name: '支払価格', color: '#cf1322', strokeWidth: 2 },
  prices_paid_future: { name: '支払価格期待', color: '#ffa39e', strokeWidth: 2 },
  employment_current: { name: '雇用', color: '#d46b08', strokeWidth: 2 },
  employment_future: { name: '雇用期待', color: '#ffd591', strokeWidth: 2 },
  capex_current: { name: '設備投資（ソフトウェア・機械設備）', color: '#531dab', strokeWidth: 2 },
  capex_future: { name: '設備投資期待', color: '#d3adf7', strokeWidth: 2 },
}

// 初期非表示シリーズ（一般活動指数のみ表示）
const INITIAL_HIDDEN_SERIES = new Set([
  'general_activity_future',
  'new_orders_current',
  'new_orders_future',
  'prices_paid_current',
  'prices_paid_future',
  'employment_current',
  'employment_future',
  'capex_current',
  'capex_future',
])

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function PhiladelphiaFedChart({ data }: PhiladelphiaFedChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries(INITIAL_HIDDEN_SERIES)

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        general_activity_current: item.general_activity_current,
        general_activity_future: item.general_activity_future,
        new_orders_current: item.new_orders_current,
        new_orders_future: item.new_orders_future,
        prices_paid_current: item.prices_paid_current,
        prices_paid_future: item.prices_paid_future,
        employment_current: item.employment_current,
        employment_future: item.employment_future,
        capex_current: item.capex_current,
        capex_future: item.capex_future,
      }))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="フィラデルフィア連銀製造業景気指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="フィラデルフィア連銀製造業景気指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestData = data.latest

  // StandardLineChart用のlines配列を生成
  const lines = Object.entries(SERIES_CONFIG).map(([key, config]) => ({
    dataKey: key,
    color: config.color,
    name: config.name,
    hide: hiddenSeries.has(key),
    strokeWidth: config.strokeWidth,
  }))

  return (
    <div id="philadelphia-fed-chart">
      <ChartContainer
        title="フィラデルフィア連銀製造業景気指数 現況 / 期待（今後6か月）"
        showPeriodSelector={false}
        dataSource="Federal Reserve Bank of Philadelphia / FRED"
        sourceUrl="https://www.philadelphiafed.org/surveys-and-data/regional-economic-analysis/manufacturing-business-outlook-survey"
      >
        {/* 最新値表示 */}
        {latestData && (
          <LatestValueBox
            items={[
              { label: '一般活動', value: latestData.general_activity_current, format: 'number', decimals: 1, color: SERIES_CONFIG.general_activity_current.color },
              { label: '期待指数', value: latestData.general_activity_future, format: 'number', decimals: 1, color: SERIES_CONFIG.general_activity_future.color },
            ]}
            date={latestData.date}
            nextRelease={data.next_release}
          />
        )}

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

        <StandardLineChart
          data={filteredData}
          lines={lines}
          yDomain={['dataMin - 5', 'dataMax + 5']}
          yAxisFormatter={(v) => v.toFixed(0)}
          tooltipLabelFormatter={formatDateLabel}
          tooltipFormatter={createNumberFormatter(1)}
          onLegendClick={handleLegendClick}
        />
      </ChartContainer>
    </div>
  )
}
