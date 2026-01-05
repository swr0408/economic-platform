/**
 * 消費者物価指数（CPI）チャートコンポーネント
 *
 * CPI（総合）とコアCPIを同一チャートに表示
 * 前年比: 折れ線グラフ
 * 前月比: 棒グラフ / テーブル
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { CPIData, CoreCPIData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  STANDARD_VIEW_MODE_OPTIONS,
  type StandardViewMode,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useHiddenSeries,
  useMultiValueMonthlyTableData,
  formatDateLabelJP,
  createPercentFormatter,
  type PeriodType,
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

interface CPIChartProps {
  cpiData: CPIData | null
  coreCpiData: CoreCPIData | null
}

// CPIデータタイプ
type CPIDataType = 'cpi' | 'core_cpi'

// CPIデータタイプ設定
const CPI_DATA_TYPE_OPTIONS: { type: CPIDataType; label: string }[] = [
  { type: 'cpi', label: 'CPI（総合）' },
  { type: 'core_cpi', label: 'コアCPI' },
]

// カラー設定
const COLORS = {
  cpi_yoy: CHART_COLORS.primary,
  cpi_mom: CHART_COLORS.primary,
  core_cpi_yoy: CHART_COLORS.purple,
  core_cpi_mom: CHART_COLORS.purple,
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CPIChart({ cpiData, coreCpiData }: CPIChartProps) {
  const [viewMode, setViewMode] = useState<StandardViewMode>('yoy')
  const [dataType, setDataType] = useState<CPIDataType>('cpi')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理（共通フック使用）
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom_table: 'default',
    mom_chart: 3,
  })

  // データを日付昇順にソート
  const cpiChartData = useSortedData(cpiData?.data)
  const coreCpiChartData = useSortedData(coreCpiData?.data)

  // データをマージ（同じ日付のCPIとコアCPIを結合）
  const mergedData = useMemo(() => {
    const dataMap = new Map<string, {
      date: string
      cpi_yoy: number | null
      cpi_mom: number | null
      core_cpi_yoy: number | null
      core_cpi_mom: number | null
    }>()

    // CPIデータを追加
    for (const item of cpiChartData) {
      dataMap.set(item.date, {
        date: item.date,
        cpi_yoy: item.yoy ?? item.value ?? null,
        cpi_mom: item.mom ?? null,
        core_cpi_yoy: null,
        core_cpi_mom: null,
      })
    }

    // コアCPIデータを追加
    for (const item of coreCpiChartData) {
      const existing = dataMap.get(item.date)
      if (existing) {
        existing.core_cpi_yoy = item.yoy ?? item.value ?? null
        existing.core_cpi_mom = item.mom ?? null
      } else {
        dataMap.set(item.date, {
          date: item.date,
          cpi_yoy: null,
          cpi_mom: null,
          core_cpi_yoy: item.yoy ?? item.value ?? null,
          core_cpi_mom: item.mom ?? null,
        })
      }
    }

    // 日付順にソート
    return Array.from(dataMap.values()).sort((a, b) => a.date.localeCompare(b.date))
  }, [cpiChartData, coreCpiChartData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(mergedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // テーブル用データ（共通フックを使用）
  const momTableData = useMultiValueMonthlyTableData(
    mergedData,
    {
      cpi: (item) => item.cpi_mom,
      core_cpi: (item) => item.core_cpi_mom,
    },
    10
  )

  const hasData = mergedData.length > 0

  // ローディング状態
  if (cpiData === null && coreCpiData === null) {
    return <LoadingChart title="消費者物価指数（CPI）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="消費者物価指数（CPI）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const cpiLatest = cpiData?.latest
  const coreCpiLatest = coreCpiData?.latest

  return (
    <div id="cpi">
      <ChartContainer
        title="消費者物価指数（CPI）"
        showPeriodSelector={false}
        dataSource="FRED (BLS)"
        sourceUrl="https://www.bls.gov/cpi/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: 'CPI（総合）',
              value: viewMode === 'yoy' ? cpiLatest?.yoy : cpiLatest?.mom,
              color: COLORS.cpi_yoy,
              format: 'percent',
            },
            {
              label: 'コアCPI',
              value: viewMode === 'yoy' ? coreCpiLatest?.yoy : coreCpiLatest?.mom,
              color: COLORS.core_cpi_yoy,
              format: 'percent',
            },
          ]}
          date={cpiLatest?.date}
          nextRelease={cpiData?.next_release}
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
                    <ViewModeButtonGroup options={STANDARD_VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />
                    <Tooltip title="比較ページを開く（CPI・コアCPI）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=us_cpi_yoy&s=us_core_cpi_yoy', '_blank')}
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
                          { dataKey: 'cpi_yoy', color: COLORS.cpi_yoy, name: 'CPI（前年比）', hide: hiddenSeries.has('cpi_yoy') },
                          { dataKey: 'core_cpi_yoy', color: COLORS.core_cpi_yoy, name: 'コアCPI（前年比）', hide: hiddenSeries.has('core_cpi_yoy') },
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
                      dataTypes={CPI_DATA_TYPE_OPTIONS}
                      selectedType={dataType}
                      onTypeChange={setDataType}
                    />
                  )}

                  {/* 前月比グラフ（棒グラフ） */}
                  {viewMode === 'mom_chart' && (
                    <>
                      <DataTypeButtonGroup options={CPI_DATA_TYPE_OPTIONS} currentType={dataType} onChange={setDataType} />
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          dataType === 'cpi'
                            ? { dataKey: 'cpi_mom', color: COLORS.cpi_mom, name: 'CPI（前月比）' }
                            : { dataKey: 'core_cpi_mom', color: COLORS.core_cpi_mom, name: 'コアCPI（前月比）' },
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
                <MarketImpactTab indicatorId="us_cpi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
