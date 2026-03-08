/**
 * 住宅着工件数・建設許可件数チャートコンポーネント
 *
 * FREDから取得した住宅着工件数(HOUST)と建設許可件数(PERMIT)を表示
 * データソース: FRED
 *
 * タブ切り替え:
 * - 時系列: 現数値グラフ（2系列）、前年比グラフ、前月比テーブル、前月比グラフ
 * - マーケットインパクト: 発表時の市場への影響分析
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { HousingStartsPermitsData } from '../../../../hooks/useDashboardData'
import type { PeriodValue } from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import {
  HOUSING_STARTS_PERMITS_DATA_TYPE_OPTIONS,
  type HousingStartsPermitsDataType,
} from '../common/chartConstants'
import {
  usePeriodFiltering,
  useHiddenSeries,
  useViewModePeriodManagement,
} from '../common/useChartData'
import {
  ViewModeButtonGroup,
  DataTypeButtonGroup,
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
  StandardBarChart,
} from '../common/ChartComponents'
import { MonthlyTableWithDataTypes } from '../common/MonthlyTable'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// =============================================================================
// 型定義
// =============================================================================

interface HousingStartsPermitsChartProps {
  housingStartsPermitsData: HousingStartsPermitsData | null
}

// 指標種別
type DataKind = 'value' | 'yoy' | 'mom'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'value', label: '現数値' },
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// カラー設定
const COLORS = {
  housingStarts: '#1890ff',  // 青（住宅着工件数）
  buildingPermits: '#52c41a', // 緑（建設許可件数）
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function HousingStartsPermitsChart({ housingStartsPermitsData }: HousingStartsPermitsChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('value')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataType, setDataType] = useState<HousingStartsPermitsDataType>('housing_starts')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // 指標種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    value: 'default',
    yoy: 'default',
    mom: 3,
  })

  // 両シリーズを結合したデータを作成
  const combinedData = useMemo(() => {
    if (!housingStartsPermitsData) return []

    const startsData = housingStartsPermitsData.housing_starts?.data || []
    const permitsData = housingStartsPermitsData.building_permits?.data || []

    // 日付をキーにしたマップを作成
    const startsMap = new Map(startsData.map(d => [d.date, d]))
    const permitsMap = new Map(permitsData.map(d => [d.date, d]))

    // 全ての日付を取得してソート
    const allDates = Array.from(
      new Set([...startsData.map(d => d.date), ...permitsData.map(d => d.date)])
    ).sort((a, b) => new Date(a).getTime() - new Date(b).getTime())

    return allDates.map(date => {
      const starts = startsMap.get(date)
      const permits = permitsMap.get(date)
      return {
        date,
        housingStarts: starts?.value ?? null,
        buildingPermits: permits?.value ?? null,
        housingStartsYoy: starts?.yoy ?? null,
        buildingPermitsYoy: permits?.yoy ?? null,
        housingStartsMom: starts?.mom ?? null,
        buildingPermitsMom: permits?.mom ?? null,
      }
    })
  }, [housingStartsPermitsData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(combinedData, {
    selectedPeriod: currentPeriod as PeriodValue,
    defaultStartYear: 2015,
  })

  // テーブル用データ（年別×月別のマトリックス - 2系列分）
  const momTableData = useMemo(() => {
    if (combinedData.length === 0) return { years: [], monthlyData: {} }

    const currentYear = new Date().getFullYear()
    const startYear = currentYear - 9  // 10年分

    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) {
      years.push(y)
    }

    const monthlyData: Record<number, Record<number, Record<HousingStartsPermitsDataType, number | null> | null>> = {}

    combinedData.forEach((item) => {
      const date = new Date(item.date)
      const year = date.getFullYear()
      const month = date.getMonth()

      if (year >= startYear && year <= currentYear) {
        if (!monthlyData[year]) {
          monthlyData[year] = {}
        }
        monthlyData[year][month] = {
          housing_starts: item.housingStartsMom,
          building_permits: item.buildingPermitsMom,
        }
      }
    })

    return { years, monthlyData }
  }, [combinedData])

  const hasData = combinedData.length > 0

  // ローディング状態
  if (housingStartsPermitsData === null) {
    return <LoadingChart title="住宅着工件数・建設許可件数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="住宅着工件数・建設許可件数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const startsLatest = housingStartsPermitsData.housing_starts?.latest
  const permitsLatest = housingStartsPermitsData.building_permits?.latest

  // 最新値表示の内容を決定
  const getLatestItems = () => {
    if (dataKind === 'value') {
      return [
        {
          label: '住宅着工件数',
          value: startsLatest?.value,
          unit: 'k',
          color: COLORS.housingStarts,
          decimals: 1,
        },
        {
          label: '建設許可件数',
          value: permitsLatest?.value,
          unit: 'k',
          color: COLORS.buildingPermits,
          decimals: 1,
        },
      ]
    } else if (dataKind === 'yoy') {
      return [
        {
          label: '住宅着工件数（前年比）',
          value: startsLatest?.yoy,
          unit: '%',
          color: COLORS.housingStarts,
          decimals: 1,
        },
        {
          label: '建設許可件数（前年比）',
          value: permitsLatest?.yoy,
          unit: '%',
          color: COLORS.buildingPermits,
          decimals: 1,
        },
      ]
    } else {
      return [
        {
          label: '住宅着工件数（前月比）',
          value: startsLatest?.mom,
          unit: '%',
          color: COLORS.housingStarts,
          decimals: 1,
        },
        {
          label: '建設許可件数（前月比）',
          value: permitsLatest?.mom,
          unit: '%',
          color: COLORS.buildingPermits,
          decimals: 1,
        },
      ]
    }
  }

  return (
    <div id="housing-starts-permits">
      <ChartContainer
        title="住宅着工件数 / 建設許可件数"
        showPeriodSelector={false}
        dataSource="Census Bureau"
        sourceUrl="https://www.census.gov/construction/nrc/index.html"
      >
        {/* 最新値表示（2系列） */}
        <LatestValueBox
          items={getLatestItems()}
          date={startsLatest?.date}
          nextRelease={housingStartsPermitsData?.next_release}
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
                    <Tooltip title="比較ページを開く（住宅着工件数）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=housing_starts&s=building_permits', '_blank')}
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

                  {/* 現数値グラフ */}
                  {dataKind === 'value' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod as PeriodValue} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'housingStarts', color: COLORS.housingStarts, name: '住宅着工件数', hide: hiddenSeries.has('housingStarts') },
                          { dataKey: 'buildingPermits', color: COLORS.buildingPermits, name: '建設許可件数', hide: hiddenSeries.has('buildingPermits') },
                        ]}
                        yAxisFormatter={(v) => `${v}`}
                        tooltipValueFormatter={(v) => `${v.toFixed(1)}k`}
                        onLegendClick={handleLegendClick}
                        showZeroLine={false}
                        yDomain={['dataMin - 50', 'dataMax + 50']}
                      />
                    </>
                  )}

                  {/* 前年比グラフ */}
                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod as PeriodValue} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'housingStartsYoy', color: COLORS.housingStarts, name: '住宅着工件数（前年比）', hide: hiddenSeries.has('housingStartsYoy') },
                          { dataKey: 'buildingPermitsYoy', color: COLORS.buildingPermits, name: '建設許可件数（前年比）', hide: hiddenSeries.has('buildingPermitsYoy') },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        onLegendClick={handleLegendClick}
                        yDomain={['dataMin - 5', 'dataMax + 5']}
                      />
                    </>
                  )}

                  {/* 前月比ヒートマップ */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTableWithDataTypes
                      data={momTableData}
                      dataTypes={HOUSING_STARTS_PERMITS_DATA_TYPE_OPTIONS}
                      selectedType={dataType}
                      onTypeChange={setDataType}
                    />
                  )}

                  {/* 前月比チャート */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <DataTypeButtonGroup
                        options={HOUSING_STARTS_PERMITS_DATA_TYPE_OPTIONS}
                        currentType={dataType}
                        onChange={setDataType}
                      />
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod as PeriodValue} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          dataType === 'housing_starts'
                            ? { dataKey: 'housingStartsMom', color: COLORS.housingStarts, name: '住宅着工件数（前月比）' }
                            : { dataKey: 'buildingPermitsMom', color: COLORS.buildingPermits, name: '建設許可件数（前月比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
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
                <MarketImpactTab indicatorId="housing_starts" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
