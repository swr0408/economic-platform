/**
 * Median CPI チャートコンポーネント
 *
 * Cleveland Fed から取得した Median CPI データを表示
 * - Median CPI: FRB Cleveland Median CPI（前年比）
 * - 16% Trimmed Mean: 16%トリムド平均CPI（前年比）
 * - CPI: CPI-U All Items（前年比）
 * - Core CPI: CPI-U Less Food and Energy（前年比）
 *
 * データソース: Cleveland Fed
 * https://www.clevelandfed.org/research/data/us-inflation/median-cpi
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { MedianCPIData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { CHART_COLORS } from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
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

interface MedianCPIChartProps {
  data: MedianCPIData | null
}

// カラー設定
const COLORS = {
  median_cpi: CHART_COLORS.purple,
  trimmed_mean_16: CHART_COLORS.orange,
  cpi: CHART_COLORS.primary,
  core_cpi: CHART_COLORS.positive,
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function MedianCPIChart({ data }: MedianCPIChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データを日付昇順にソート
  const sortedData = useSortedData(data?.data)

  // チャート用データに変換
  const chartData = useMemo(() => {
    return sortedData.map((item) => ({
      date: item.date,
      median_cpi: item.median_cpi,
      trimmed_mean_16: item.trimmed_mean_16,
      cpi: item.cpi,
      core_cpi: item.core_cpi,
    }))
  }, [sortedData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  const hasData = chartData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="Median CPI / 16% Trimmed Mean CPI" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="Median CPI / 16% Trimmed Mean CPI" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="median-cpi">
      <ChartContainer
        title="Median CPI / 16% Trimmed Mean CPI"
        showPeriodSelector={false}
        dataSource="Cleveland Fed"
        sourceUrl="https://www.clevelandfed.org/research/data/us-inflation/median-cpi"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: 'Median CPI',
              value: latest?.median_cpi,
              color: COLORS.median_cpi,
              format: 'percent',
            },
            {
              label: '16% Trimmed Mean',
              value: latest?.trimmed_mean_16,
              color: COLORS.trimmed_mean_16,
              format: 'percent',
            },
            {
              label: 'CPI',
              value: latest?.cpi,
              color: COLORS.cpi,
              format: 'percent',
            },
            {
              label: 'Core CPI',
              value: latest?.core_cpi,
              color: COLORS.core_cpi,
              format: 'percent',
            },
          ]}
          date={latest?.date}
          nextRelease={data.next_release}
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=median_cpi&s=trimmed_mean_16_cpi&s=us_cpi_yoy&s=us_core_cpi_yoy', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* チャート表示 */}
        <StandardLineChart
          data={filteredData}
          lines={[
            {
              dataKey: 'median_cpi',
              color: COLORS.median_cpi,
              name: 'Median CPI（前年比）',
              hide: hiddenSeries.has('median_cpi'),
            },
            {
              dataKey: 'trimmed_mean_16',
              color: COLORS.trimmed_mean_16,
              name: '16% Trimmed Mean（前年比）',
              hide: hiddenSeries.has('trimmed_mean_16'),
            },
            {
              dataKey: 'cpi',
              color: COLORS.cpi,
              name: 'CPI（前年比）',
              hide: hiddenSeries.has('cpi'),
            },
            {
              dataKey: 'core_cpi',
              color: COLORS.core_cpi,
              name: 'Core CPI（前年比）',
              hide: hiddenSeries.has('core_cpi'),
            },
          ]}
          yAxisFormatter={(v) => `${v}%`}
          yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
          onLegendClick={handleLegendClick}
        />
      </ChartContainer>
    </div>
  )
}
