/**
 * アトランタ連銀賃金トラッカーチャートコンポーネント
 *
 * Atlanta Fed Wage Growth Tracker データを使用して賃金上昇率を表示
 * - Overall: 全体の賃金上昇率（12ヶ月移動中央値）
 * - Full-time: フルタイム労働者
 * - Paid Hourly: 時給労働者
 * - Job Stayer: 在職者
 * - Job Switcher: 転職者
 *
 * 共通コンポーネントを使用
 */
import { useState } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { AtlantaFedWageData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabelJP,
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

interface AtlantaFedWageGrowthChartProps {
  data: AtlantaFedWageData | null
}

// カラー設定
const COLORS = {
  overall: '#1890ff',     // 全体 - 青
  fulltime: '#52c41a',    // フルタイム - 緑
  paid_hourly: '#faad14', // 時給 - 黄
  job_stayer: '#ff4d4f',  // 在職者 - 赤
  job_switcher: '#722ed1', // 転職者 - 紫
}

// 系列名（日本語）
const SERIES_NAMES = {
  overall: 'アトランタ連銀賃金トラッカー',
  fulltime: 'フルタイム',
  paid_hourly: 'パートタイム',
  job_stayer: '在職者',
  job_switcher: '転職者',
}

// =============================================================================
// メインコンポーネント
// =============================================================================

// 初期非表示の系列（Overallのみ表示）
const INITIAL_HIDDEN = ['fulltime', 'paid_hourly', 'job_stayer', 'job_switcher']

export default function AtlantaFedWageGrowthChart({ data }: AtlantaFedWageGrowthChartProps) {
  const [period, setPeriod] = useState<'default' | 'all' | number>(10)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries(INITIAL_HIDDEN)

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
    return <LoadingChart title="アトランタ連銀賃金トラッカー" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="アトランタ連銀賃金トラッカー" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latest) return []

    return [
      { label: SERIES_NAMES.overall, value: latest.overall, color: COLORS.overall, format: 'number' as const, unit: '%', decimals: 1 },
      { label: SERIES_NAMES.fulltime, value: latest.fulltime, color: COLORS.fulltime, format: 'number' as const, unit: '%', decimals: 1 },
      { label: SERIES_NAMES.paid_hourly, value: latest.paid_hourly, color: COLORS.paid_hourly, format: 'number' as const, unit: '%', decimals: 1 },
      { label: SERIES_NAMES.job_switcher, value: latest.job_switcher, color: COLORS.job_switcher, format: 'number' as const, unit: '%', decimals: 1 },
      { label: SERIES_NAMES.job_stayer, value: latest.job_stayer, color: COLORS.job_stayer, format: 'number' as const, unit: '%', decimals: 1 },
    ]
  }

  return (
    <div id="atlanta-fed-wage">
      <ChartContainer
        title="アトランタ連銀賃金トラッカー"
        showPeriodSelector={false}
        dataSource="Atlanta Fed - Wage Growth Tracker"
        sourceUrl="https://www.atlantafed.org/chcs/wage-growth-tracker"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latest?.date}
          nextRelease={nextRelease}
        />

        {/* 期間セレクター */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setPeriod} selectedPeriod={period} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=atlanta_fed_wage', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 折れ線グラフ */}
        <StandardLineChart
          data={filteredData}
          lines={[
            {
              dataKey: 'overall',
              color: COLORS.overall,
              name: SERIES_NAMES.overall,
              hide: hiddenSeries.has('overall'),
            },
            {
              dataKey: 'fulltime',
              color: COLORS.fulltime,
              name: SERIES_NAMES.fulltime,
              hide: hiddenSeries.has('fulltime'),
            },
            {
              dataKey: 'paid_hourly',
              color: COLORS.paid_hourly,
              name: SERIES_NAMES.paid_hourly,
              hide: hiddenSeries.has('paid_hourly'),
            },
            {
              dataKey: 'job_stayer',
              color: COLORS.job_stayer,
              name: SERIES_NAMES.job_stayer,
              hide: hiddenSeries.has('job_stayer'),
            },
            {
              dataKey: 'job_switcher',
              color: COLORS.job_switcher,
              name: SERIES_NAMES.job_switcher,
              hide: hiddenSeries.has('job_switcher'),
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
          onLegendClick={handleLegendClick}
        />
      </ChartContainer>
    </div>
  )
}
