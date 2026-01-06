/**
 * 生産者物価指数（PPI）チャートコンポーネント
 *
 * PPI（総合）とコアPPIを同一チャートに表示
 * 前年比: 折れ線グラフ
 * 前月比: 棒グラフ / テーブル
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PPIData, CorePPIData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useHiddenSeries,
  useMultiValueMonthlyTableData,
} from '../common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  ViewModeButtonGroup,
  DataTypeButtonGroup,
  StandardLineChart,
  StandardBarChart,
} from '../common/ChartComponents'
import { MonthlyTableWithDataTypes } from '../common/MonthlyTable'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// =============================================================================
// 型定義
// =============================================================================

interface PPIChartProps {
  ppiData: PPIData | null
  corePpiData: CorePPIData | null
}

// PPI表示モード
type PPIViewMode = 'yoy' | 'mom_table' | 'mom_chart'

// PPIビューモードオプション
const PPI_VIEW_MODE_OPTIONS: { mode: PPIViewMode; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom_table', label: '前月比テーブル' },
  { mode: 'mom_chart', label: '前月比グラフ' },
]

// PPIデータタイプ
type PPIDataType = 'ppi' | 'core_ppi'

// PPIデータタイプ設定
const PPI_DATA_TYPE_OPTIONS: { type: PPIDataType; label: string }[] = [
  { type: 'ppi', label: 'PPI' },
  { type: 'core_ppi', label: 'コアPPI' },
]

// カラー設定
const COLORS = {
  ppi_yoy: CHART_COLORS.primary,
  ppi_mom: CHART_COLORS.primary,
  core_ppi_yoy: CHART_COLORS.purple,
  core_ppi_mom: CHART_COLORS.purple,
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function PPIChart({ ppiData, corePpiData }: PPIChartProps) {
  const [viewMode, setViewMode] = useState<PPIViewMode>('yoy')
  const [dataType, setDataType] = useState<PPIDataType>('ppi')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理（共通フック使用）
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom_table: 'default',
    mom_chart: 3,
  })

  // データを日付昇順にソート
  const ppiChartData = useSortedData(ppiData?.data)
  const corePpiChartData = useSortedData(corePpiData?.data)

  // データをマージ（同じ日付のPPIとコアPPIを結合）
  const mergedData = useMemo(() => {
    const dataMap = new Map<string, {
      date: string
      ppi_yoy: number | null
      ppi_mom: number | null
      core_ppi_yoy: number | null
      core_ppi_mom: number | null
    }>()

    // PPIデータを追加
    for (const item of ppiChartData) {
      dataMap.set(item.date, {
        date: item.date,
        ppi_yoy: item.yoy ?? item.value ?? null,
        ppi_mom: item.mom ?? null,
        core_ppi_yoy: null,
        core_ppi_mom: null,
      })
    }

    // コアPPIデータを追加
    for (const item of corePpiChartData) {
      const existing = dataMap.get(item.date)
      if (existing) {
        existing.core_ppi_yoy = item.yoy ?? item.value ?? null
        existing.core_ppi_mom = item.mom ?? null
      } else {
        dataMap.set(item.date, {
          date: item.date,
          ppi_yoy: null,
          ppi_mom: null,
          core_ppi_yoy: item.yoy ?? item.value ?? null,
          core_ppi_mom: item.mom ?? null,
        })
      }
    }

    // 日付順にソート
    return Array.from(dataMap.values()).sort((a, b) => a.date.localeCompare(b.date))
  }, [ppiChartData, corePpiChartData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(mergedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // テーブル用データ（共通フックを使用）
  const momTableData = useMultiValueMonthlyTableData(
    mergedData,
    {
      ppi: (item) => item.ppi_mom,
      core_ppi: (item) => item.core_ppi_mom,
    },
    10
  )

  const hasData = mergedData.length > 0

  // ローディング状態
  if (ppiData === null && corePpiData === null) {
    return <LoadingChart title="生産者物価指数（PPI）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="生産者物価指数（PPI）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const ppiLatest = ppiData?.latest
  const corePpiLatest = corePpiData?.latest

  return (
    <div id="ppi">
      <ChartContainer
        title="生産者物価指数（PPI）"
        showPeriodSelector={false}
        dataSource="FRED (BLS)"
        sourceUrl="https://www.bls.gov/ppi/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: 'PPI',
              value: viewMode === 'yoy' ? ppiLatest?.yoy : ppiLatest?.mom,
              color: COLORS.ppi_yoy,
              format: 'percent',
            },
            {
              label: 'コアPPI',
              value: viewMode === 'yoy' ? corePpiLatest?.yoy : corePpiLatest?.mom,
              color: COLORS.core_ppi_yoy,
              format: 'percent',
            },
          ]}
          date={ppiLatest?.date}
          nextRelease={ppiData?.next_release}
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={PPI_VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />
                    <Tooltip title="比較ページを開く（PPI・コアPPI）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=us_ppi_yoy&s=us_core_ppi_yoy', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 前年比グラフ（折れ線グラフ） */}
                  {viewMode === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'ppi_yoy', color: COLORS.ppi_yoy, name: 'PPI（前年比）', hide: hiddenSeries.has('ppi_yoy') },
                          { dataKey: 'core_ppi_yoy', color: COLORS.core_ppi_yoy, name: 'コアPPI（前年比）', hide: hiddenSeries.has('core_ppi_yoy') },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                        onLegendClick={handleLegendClick}
                      />
                    </>
                  )}

                  {/* 前月比テーブル */}
                  {viewMode === 'mom_table' && (
                    <MonthlyTableWithDataTypes
                      data={momTableData}
                      dataTypes={PPI_DATA_TYPE_OPTIONS}
                      selectedType={dataType}
                      onTypeChange={setDataType}
                    />
                  )}

                  {/* 前月比グラフ（棒グラフ） */}
                  {viewMode === 'mom_chart' && (
                    <>
                      <DataTypeButtonGroup options={PPI_DATA_TYPE_OPTIONS} currentType={dataType} onChange={setDataType} />
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          dataType === 'ppi'
                            ? { dataKey: 'ppi_mom', color: COLORS.ppi_mom, name: 'PPI（前月比）' }
                            : { dataKey: 'core_ppi_mom', color: COLORS.core_ppi_mom, name: 'コアPPI（前月比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
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
                <MarketImpactTab indicatorId="ppi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
