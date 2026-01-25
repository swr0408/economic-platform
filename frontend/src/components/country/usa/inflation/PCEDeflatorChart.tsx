/**
 * PCEデフレーターチャートコンポーネント
 *
 * PCEデフレーター（総合）とコアPCEデフレーターを同一チャートに表示
 * 前年比: 折れ線グラフ
 * 前月比: 棒グラフ / テーブル
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PCEDeflatorData, CorePCEDeflatorData } from '../../../../hooks/useDashboardData'

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

interface PCEDeflatorChartProps {
  pceData: PCEDeflatorData | null
  corePceData: CorePCEDeflatorData | null
}

// PCE表示モード
type PCEViewMode = 'yoy' | 'mom_table' | 'mom_chart' | 'annualized'

// PCEビューモードオプション
const PCE_VIEW_MODE_OPTIONS: { mode: PCEViewMode; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom_chart', label: '前月比' },
  { mode: 'mom_table', label: '前月比（テーブル）' },
  { mode: 'annualized', label: '年率' },
]

// PCEデータタイプ
type PCEDataType = 'pce' | 'core_pce'

// PCEデータタイプ設定
const PCE_DATA_TYPE_OPTIONS: { type: PCEDataType; label: string }[] = [
  { type: 'pce', label: 'PCEデフレーター' },
  { type: 'core_pce', label: 'コアPCE' },
]

// カラー設定
const COLORS = {
  pce_yoy: CHART_COLORS.primary,
  pce_mom: CHART_COLORS.primary,
  core_pce_yoy: CHART_COLORS.purple,
  core_pce_mom: CHART_COLORS.purple,
  // 年率用カラー
  annualized_3m: CHART_COLORS.positive,  // 3か月年率（緑）
  annualized_6m: CHART_COLORS.orange,    // 6か月年率（オレンジ）
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function PCEDeflatorChart({ pceData, corePceData }: PCEDeflatorChartProps) {
  const [viewMode, setViewMode] = useState<PCEViewMode>('yoy')
  const [dataType, setDataType] = useState<PCEDataType>('pce')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理（共通フック使用）
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom_table: 'default',
    mom_chart: 3,
    annualized: 'default',  // 年率は直近3年
  })

  // データを日付昇順にソート
  const pceChartData = useSortedData(pceData?.data)
  const corePceChartData = useSortedData(corePceData?.data)

  // データをマージ（同じ日付のPCEとコアPCEを結合）
  const mergedData = useMemo(() => {
    const dataMap = new Map<string, {
      date: string
      pce_yoy: number | null
      pce_mom: number | null
      core_pce_yoy: number | null
      core_pce_mom: number | null
      pce_annualized_3m: number | null
      pce_annualized_6m: number | null
      core_pce_annualized_3m: number | null
      core_pce_annualized_6m: number | null
    }>()

    // PCEデータを追加
    for (const item of pceChartData) {
      dataMap.set(item.date, {
        date: item.date,
        pce_yoy: item.yoy ?? item.value ?? null,
        pce_mom: item.mom ?? null,
        pce_annualized_3m: item.annualized_3m ?? null,
        pce_annualized_6m: item.annualized_6m ?? null,
        core_pce_yoy: null,
        core_pce_mom: null,
        core_pce_annualized_3m: null,
        core_pce_annualized_6m: null,
      })
    }

    // コアPCEデータを追加
    for (const item of corePceChartData) {
      const existing = dataMap.get(item.date)
      if (existing) {
        existing.core_pce_yoy = item.yoy ?? item.value ?? null
        existing.core_pce_mom = item.mom ?? null
        existing.core_pce_annualized_3m = item.annualized_3m ?? null
        existing.core_pce_annualized_6m = item.annualized_6m ?? null
      } else {
        dataMap.set(item.date, {
          date: item.date,
          pce_yoy: null,
          pce_mom: null,
          pce_annualized_3m: null,
          pce_annualized_6m: null,
          core_pce_yoy: item.yoy ?? item.value ?? null,
          core_pce_mom: item.mom ?? null,
          core_pce_annualized_3m: item.annualized_3m ?? null,
          core_pce_annualized_6m: item.annualized_6m ?? null,
        })
      }
    }

    // 日付順にソート
    return Array.from(dataMap.values()).sort((a, b) => a.date.localeCompare(b.date))
  }, [pceChartData, corePceChartData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(mergedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // テーブル用データ（共通フックを使用）
  const momTableData = useMultiValueMonthlyTableData(
    mergedData,
    {
      pce: (item) => item.pce_mom,
      core_pce: (item) => item.core_pce_mom,
    },
    10
  )

  const hasData = mergedData.length > 0

  // ローディング状態
  if (pceData === null && corePceData === null) {
    return <LoadingChart title="PCEデフレーター" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="PCEデフレーター" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const pceLatest = pceData?.latest
  const corePceLatest = corePceData?.latest

  return (
    <div id="pce-deflator">
      <ChartContainer
        title="PCEデフレーター"
        showPeriodSelector={false}
        dataSource="FRED (BEA)"
        sourceUrl="https://www.bea.gov/data/personal-consumption-expenditures-price-index"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={
            viewMode === 'annualized'
              ? [
                  {
                    label: dataType === 'pce' ? 'PCE 3か月年率' : 'コアPCE 3か月年率',
                    value: dataType === 'pce' ? pceLatest?.annualized_3m : corePceLatest?.annualized_3m,
                    color: COLORS.annualized_3m,
                    format: 'percent',
                  },
                  {
                    label: dataType === 'pce' ? 'PCE 6か月年率' : 'コアPCE 6か月年率',
                    value: dataType === 'pce' ? pceLatest?.annualized_6m : corePceLatest?.annualized_6m,
                    color: COLORS.annualized_6m,
                    format: 'percent',
                  },
                ]
              : [
                  {
                    label: 'PCEデフレーター',
                    value: viewMode === 'yoy' ? pceLatest?.yoy : pceLatest?.mom,
                    color: COLORS.pce_yoy,
                    format: 'percent',
                  },
                  {
                    label: 'コアPCE',
                    value: viewMode === 'yoy' ? corePceLatest?.yoy : corePceLatest?.mom,
                    color: COLORS.core_pce_yoy,
                    format: 'percent',
                  },
                ]
          }
          date={pceLatest?.date}
          nextRelease={pceData?.next_release}
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
                    <ViewModeButtonGroup options={PCE_VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />
                    <Tooltip title="比較ページを開く（PCEデフレーター・コアPCE）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=us_pce_deflator_yoy&s=us_core_pce_deflator_yoy', '_blank')}
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
                          { dataKey: 'pce_yoy', color: COLORS.pce_yoy, name: 'PCEデフレーター（前年比）', hide: hiddenSeries.has('pce_yoy') },
                          { dataKey: 'core_pce_yoy', color: COLORS.core_pce_yoy, name: 'コアPCE（前年比）', hide: hiddenSeries.has('core_pce_yoy') },
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
                      dataTypes={PCE_DATA_TYPE_OPTIONS}
                      selectedType={dataType}
                      onTypeChange={setDataType}
                    />
                  )}

                  {/* 前月比グラフ（棒グラフ） */}
                  {viewMode === 'mom_chart' && (
                    <>
                      <DataTypeButtonGroup options={PCE_DATA_TYPE_OPTIONS} currentType={dataType} onChange={setDataType} />
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          dataType === 'pce'
                            ? { dataKey: 'pce_mom', color: COLORS.pce_mom, name: 'PCEデフレーター（前月比）' }
                            : { dataKey: 'core_pce_mom', color: COLORS.core_pce_mom, name: 'コアPCE（前月比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                      />
                    </>
                  )}

                  {/* 年率グラフ（3か月年率・6か月年率を折れ線グラフで表示） */}
                  {viewMode === 'annualized' && (
                    <>
                      <DataTypeButtonGroup options={PCE_DATA_TYPE_OPTIONS} currentType={dataType} onChange={setDataType} />
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          dataType === 'pce'
                            ? { dataKey: 'pce_annualized_3m', color: COLORS.annualized_3m, name: 'PCE 3か月年率', hide: hiddenSeries.has('pce_annualized_3m') }
                            : { dataKey: 'core_pce_annualized_3m', color: COLORS.annualized_3m, name: 'コアPCE 3か月年率', hide: hiddenSeries.has('core_pce_annualized_3m') },
                          dataType === 'pce'
                            ? { dataKey: 'pce_annualized_6m', color: COLORS.annualized_6m, name: 'PCE 6か月年率', hide: hiddenSeries.has('pce_annualized_6m') }
                            : { dataKey: 'core_pce_annualized_6m', color: COLORS.annualized_6m, name: 'コアPCE 6か月年率', hide: hiddenSeries.has('core_pce_annualized_6m') },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                        onLegendClick={handleLegendClick}
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
                <MarketImpactTab indicatorId="core_pce" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
