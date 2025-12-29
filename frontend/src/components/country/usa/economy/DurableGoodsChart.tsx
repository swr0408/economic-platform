/**
 * 耐久財受注チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { DurableGoodsData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  STANDARD_VIEW_MODE_OPTIONS,
  DURABLE_GOODS_DATA_TYPE_OPTIONS,
  type StandardViewMode,
  type DurableGoodsDataType,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMultiValueMonthlyTableData,
  useHiddenSeries,
} from '../common/useChartData'
import {
  ViewModeButtonGroup,
  DataTypeButtonGroup,
  NoDataMessage,
  LatestValueBoxWithSub,
  StandardLineChart,
  StandardBarChart,
} from '../common/ChartComponents'
import { MonthlyTableWithDataTypes } from '../common/MonthlyTable'

// =============================================================================
// 型定義
// =============================================================================

interface DurableGoodsChartProps {
  data: DurableGoodsData | null
}

// カラー設定
const COLORS = {
  yoy: CHART_COLORS.primary,
  yoy_ex: CHART_COLORS.purple,
  mom: CHART_COLORS.positive,
  mom_ex: CHART_COLORS.cyan,
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function DurableGoodsChart({ data }: DurableGoodsChartProps) {
  const [viewMode, setViewMode] = useState<StandardViewMode>('yoy')
  const [dataType, setDataType] = useState<DurableGoodsDataType>('total')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理（共通フック使用）
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom_table: 'default',
    mom_chart: 3,
  })

  // データを日付昇順にソート
  const chartData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // テーブル用データ（共通フックを使用）
  const momTableData = useMultiValueMonthlyTableData(
    chartData,
    {
      total: (item) => item.mom,
      ex_transport: (item) => item.ex_transport_mom,
    },
    10
  )

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="耐久財受注（Durable Goods Orders）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="耐久財受注（Durable Goods Orders）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="durable-goods-chart">
      <ChartContainer
        title="耐久財受注"
        showPeriodSelector={false}
        dataSource="FRED (Census Bureau)"
        sourceUrl="https://www.census.gov/manufacturing/m3/release_schedule.html"
      >
        {/* 最新値表示 */}
        <LatestValueBoxWithSub
          main={{
            label: '総合',
            yoyValue: latest?.yoy,
            momValue: latest?.mom,
            color: COLORS.yoy,
          }}
          sub={{
            label: '輸送除外',
            yoyValue: latest?.ex_transport_yoy,
            momValue: latest?.ex_transport_mom,
            color: COLORS.yoy_ex,
          }}
          date={latest?.date}
          viewMode={viewMode}
          nextRelease={data.next_release}
        />

        <ViewModeButtonGroup options={STANDARD_VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />

        {/* 前年比グラフ */}
        {viewMode === 'yoy' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardLineChart
              data={filteredData}
              lines={[
                { dataKey: 'yoy', color: COLORS.yoy, name: '耐久財受注（前年比）', hide: hiddenSeries.has('yoy') },
                { dataKey: 'ex_transport_yoy', color: COLORS.yoy_ex, name: '輸送除外（前年比）', hide: hiddenSeries.has('ex_transport_yoy') },
              ]}
              yAxisFormatter={(v) => `${v}%`}
              yDomain={['dataMin - 5', 'dataMax + 5']}
              onLegendClick={handleLegendClick}
            />
          </>
        )}

        {/* 前月比テーブル */}
        {viewMode === 'mom_table' && (
          <MonthlyTableWithDataTypes
            data={momTableData}
            dataTypes={DURABLE_GOODS_DATA_TYPE_OPTIONS}
            selectedType={dataType}
            onTypeChange={setDataType}
          />
        )}

        {/* 前月比グラフ */}
        {viewMode === 'mom_chart' && (
          <>
            <DataTypeButtonGroup options={DURABLE_GOODS_DATA_TYPE_OPTIONS} currentType={dataType} onChange={setDataType} />
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardBarChart
              data={filteredData}
              bars={[
                dataType === 'total'
                  ? { dataKey: 'mom', color: COLORS.mom, name: '耐久財受注（前月比）' }
                  : { dataKey: 'ex_transport_mom', color: COLORS.mom_ex, name: '輸送除外（前月比）' },
              ]}
              yAxisFormatter={(v) => `${v}%`}
              yDomain={['dataMin - 2', 'dataMax + 2']}
            />
          </>
        )}
      </ChartContainer>
    </div>
  )
}
