/**
 * 個人所得チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PersonalIncomeData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { CHART_COLORS } from '../common/chartConstants'
import {
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMergedNominalRealData,
  useMultiValueMonthlyTableData,
  formatDateLabelJP,
  useHiddenSeries,
} from '../common/useChartData'
import {
  ViewModeButtonGroup,
  DataTypeButtonGroup,
  NoDataMessage,
  LatestValueBoxDual,
  StandardLineChart,
  StandardBarChart,
} from '../common/ChartComponents'
import { MonthlyTableWithDataTypes } from '../common/MonthlyTable'

// =============================================================================
// 型定義
// =============================================================================

interface PersonalIncomeChartProps {
  data: PersonalIncomeData | null
}

type ViewMode = 'yoy' | 'mom_table' | 'mom_chart'
type DataType = 'nominal' | 'real'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom_table', label: '前月比テーブル' },
  { mode: 'mom_chart', label: '前月比グラフ' },
]

// データタイプ設定
const DATA_TYPE_OPTIONS: { type: DataType; label: string }[] = [
  { type: 'nominal', label: '名目' },
  { type: 'real', label: '実質' },
]

// カラー設定
const COLORS = {
  nominal: CHART_COLORS.primary,
  real: CHART_COLORS.positive,
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function PersonalIncomeChart({ data }: PersonalIncomeChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')
  const [dataType, setDataType] = useState<DataType>('nominal')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理（共通フック使用）
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom_table: 'default',
    mom_chart: 3,
  })

  // 名目・実質データをマージ（共通フックを使用）
  const chartData = useMergedNominalRealData(data?.nominal?.data, data?.real?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // テーブル用データ（共通フックを使用）
  const momTableData = useMultiValueMonthlyTableData(
    chartData,
    {
      nominal: (item) => item.nominal_mom,
      real: (item) => item.real_mom,
    },
    10
  )

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="個人所得（Personal Income）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="個人所得（Personal Income）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const nominalLatest = data.nominal?.latest
  const realLatest = data.real?.latest
  const nextRelease = data.next_release

  return (
    <div id="personal-income">
      <ChartContainer
        title="個人所得"
        showPeriodSelector={false}
        dataSource="FRED / BEA"
        sourceUrl="https://fred.stlouisfed.org/series/PI"
      >
        {/* 最新値表示 */}
        <LatestValueBoxDual
          primary={{ label: '名目', data: nominalLatest, color: COLORS.nominal }}
          secondary={{ label: '実質', data: realLatest, color: COLORS.real }}
          viewMode={viewMode}
          nextRelease={nextRelease}
        />

        <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />

        {/* 前年比グラフ */}
        {viewMode === 'yoy' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardLineChart
              data={filteredData}
              lines={[
                { dataKey: 'nominal_yoy', color: COLORS.nominal, name: '名目（前年比）', hide: hiddenSeries.has('nominal_yoy') },
                { dataKey: 'real_yoy', color: COLORS.real, name: '実質（前年比）', hide: hiddenSeries.has('real_yoy') },
              ]}
              yAxisFormatter={(v) => `${v}%`}
              yDomain={['dataMin - 2', 'dataMax + 2']}
              tooltipLabelFormatter={formatDateLabelJP}
              onLegendClick={handleLegendClick}
            />
          </>
        )}

        {/* 前月比テーブル */}
        {viewMode === 'mom_table' && (
          <MonthlyTableWithDataTypes
            data={momTableData}
            dataTypes={DATA_TYPE_OPTIONS}
            selectedType={dataType}
            onTypeChange={setDataType}
          />
        )}

        {/* 前月比グラフ */}
        {viewMode === 'mom_chart' && (
          <>
            <DataTypeButtonGroup options={DATA_TYPE_OPTIONS} currentType={dataType} onChange={setDataType} />
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardBarChart
              data={filteredData}
              bars={[
                dataType === 'nominal'
                  ? { dataKey: 'nominal_mom', color: COLORS.nominal, name: '名目（前月比）' }
                  : { dataKey: 'real_mom', color: COLORS.real, name: '実質（前月比）' },
              ]}
              yAxisFormatter={(v) => `${v}%`}
              yDomain={['dataMin - 1', 'dataMax + 1']}
              tooltipLabelFormatter={formatDateLabelJP}
            />
          </>
        )}
      </ChartContainer>
    </div>
  )
}
