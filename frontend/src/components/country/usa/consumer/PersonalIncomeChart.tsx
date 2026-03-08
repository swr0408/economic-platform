/**
 * 個人所得チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PersonalIncomeData } from '../../../../hooks/useDashboardData'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  NOMINAL_REAL_DATA_TYPE_OPTIONS,
  type NominalRealDataType,
} from '../common/chartConstants'
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

// カラー設定
const COLORS = {
  nominal: CHART_COLORS.primary,
  real: CHART_COLORS.positive,
}

// =============================================================================
// メインコンポーネント
// =============================================================================

// 指標種別
type DataKind = 'yoy' | 'mom'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
]
// 表示形式
type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

export default function PersonalIncomeChart({ data }: PersonalIncomeChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [dataType, setDataType] = useState<NominalRealDataType>('nominal')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // 指標種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 'default',
    mom: 3,
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
          viewMode={dataKind}
          nextRelease={nextRelease}
        />

        {/* タブ切替 */}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* 上段: 指標種別 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=personal_income_mom', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 下段: 表示形式（前月比のときのみ） */}
                  {dataKind === 'mom' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 前年比グラフ */}
                  {dataKind === 'yoy' && (
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

                  {/* 前月比ヒートマップ */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTableWithDataTypes
                      data={momTableData}
                      dataTypes={NOMINAL_REAL_DATA_TYPE_OPTIONS}
                      selectedType={dataType}
                      onTypeChange={setDataType}
                    />
                  )}

                  {/* 前月比チャート */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <DataTypeButtonGroup options={NOMINAL_REAL_DATA_TYPE_OPTIONS} currentType={dataType} onChange={setDataType} />
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
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="personal_income_mom" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
