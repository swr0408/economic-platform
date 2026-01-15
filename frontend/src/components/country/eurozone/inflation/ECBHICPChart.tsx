/**
 * ECB HICP チャートコンポーネント
 *
 * ECB Data APIからユーロ圏消費者物価調和指数(HICP)データを取得し、表示
 *
 * データ:
 * - Total HICP (前年比/前月比)
 * - Core HICP (前年比/前月比)
 * - Core excl. unprocessed food (前年比)
 *
 * データソース:
 * - European Central Bank (ECB)
 *
 * 発表スケジュール:
 * - 速報: 毎月28日〜翌月7日 18:00-18:10 CET
 * - 改定: 毎月14日〜25日 18:00-18:10 CET
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMultiValueMonthlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
  StandardBarChart,
  ViewModeButtonGroup,
  DataTypeButtonGroup,
} from '../../usa/common/ChartComponents'
import { MonthlyTableWithDataTypes } from '../../usa/common/MonthlyTable'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { ECBHICPData } from '../../../../hooks/useDashboardData'

interface ECBHICPChartProps {
  data: ECBHICPData | null
}

interface ChartDataPoint {
  date: string
  total: number | null
  core: number | null
  coreExclUnprocessedFood: number | null
  total_mom: number | null
  core_mom: number | null
  [key: string]: unknown
}

// 表示モード
type ViewMode = 'yoy' | 'mom_table' | 'mom_chart'

const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom_table', label: '前月比テーブル' },
  { mode: 'mom_chart', label: '前月比グラフ' },
]

// データタイプ
type DataType = 'total' | 'core'

const DATA_TYPE_OPTIONS: { type: DataType; label: string }[] = [
  { type: 'total', label: 'HICP（総合）' },
  { type: 'core', label: 'HICP（コア：除エネルギー・食品）' },
]

// グラフの色
const COLORS = {
  total: '#1890ff',
  core: '#ff7875',
  coreExclUnprocessedFood: '#52c41a',
}

export default function ECBHICPChart({ data }: ECBHICPChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')
  const [dataType, setDataType] = useState<DataType>('total')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom_table: 'default',
    mom_chart: 3,
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data || !data.annual_rates) return []

    const totalData = data.annual_rates.total_hicp || []
    const coreData = data.annual_rates.core_hicp || []
    const coreExclUnprocessedFoodData = data.annual_rates.core_excl_unprocessed_food || []
    const totalMomData = data.monthly_changes?.total_hicp || []
    const coreMomData = data.monthly_changes?.core_hicp || []

    // 日付をキーにしたマップを作成
    const dateMap = new Map<string, ChartDataPoint>()

    const initPoint = (date: string): ChartDataPoint => ({
      date,
      total: null,
      core: null,
      coreExclUnprocessedFood: null,
      total_mom: null,
      core_mom: null,
    })

    totalData.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      dateMap.get(point.date)!.total = point.value
    })

    coreData.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      dateMap.get(point.date)!.core = point.value
    })

    coreExclUnprocessedFoodData.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      dateMap.get(point.date)!.coreExclUnprocessedFood = point.value
    })

    totalMomData.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      dateMap.get(point.date)!.total_mom = point.value
    })

    coreMomData.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      dateMap.get(point.date)!.core_mom = point.value
    })

    return Array.from(dateMap.values())
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  // テーブル用データ
  const momTableData = useMultiValueMonthlyTableData(
    chartData,
    {
      total: (item) => item.total_mom,
      core: (item) => item.core_mom,
    },
    10
  )

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  // 前月比の最新値を取得
  const latestMom = useMemo(() => {
    if (!chartData.length) return null
    // 前月比データがある最新のポイントを探す
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].total_mom !== null || chartData[i].core_mom !== null) {
        return chartData[i]
      }
    }
    return null
  }, [chartData])

  if (data === null) {
    return <LoadingChart title="HICP（ユーロ圏・前年比）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="HICP（ユーロ圏・前年比）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ecb-hicp-chart">
      <ChartContainer
        title="HICP（ユーロ圏・前年比）"
        showPeriodSelector={false}
        dataSource="European Central Bank (ECB)"
        sourceUrl="https://ec.europa.eu/eurostat/en/web/main/news/euro-indicators?p_p_id=estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageNumber=1&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_action=search&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageSize=11&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_text=Unemployment&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_collection=CAT_PREREL&p_auth=ZIoPsCO4&text=inflation"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={
            viewMode === 'yoy'
              ? [
                  {
                    label: '総合',
                    value: latest?.total,
                    color: COLORS.total,
                    format: 'percent',
                  },
                  {
                    label: 'コア（除エネ食品）',
                    value: latest?.core,
                    color: COLORS.core,
                    format: 'percent',
                  },
                  {
                    label: 'コア(除非加工食品)',
                    value: latest?.coreExclUnprocessedFood,
                    color: COLORS.coreExclUnprocessedFood,
                    format: 'percent',
                  },
                ]
              : [
                  {
                    label: '総合（前月比）',
                    value: latestMom?.total_mom,
                    color: COLORS.total,
                    format: 'percent',
                  },
                  {
                    label: 'コア（除エネ食品・前月比）',
                    value: latestMom?.core_mom,
                    color: COLORS.core,
                    format: 'percent',
                  },
                ]
          }
          date={viewMode === 'yoy' ? latest?.date : latestMom?.date}
          nextRelease={data.next_release}
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
                  {/* ビューモード切り替え */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />
                    <Tooltip title="比較ページを開く（HICP総合・コア）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=eurozone_hicp_total&s=eurozone_hicp_core', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 前年比グラフ */}
                  {viewMode === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'total', color: COLORS.total, name: 'HICP（総合）' },
                          { dataKey: 'core', color: COLORS.core, name: 'HICP（除くエネルギー・食品）' },
                          { dataKey: 'coreExclUnprocessedFood', color: COLORS.coreExclUnprocessedFood, name: 'HICP（除くエネルギー・非加工食品）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        showZeroLine={true}
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
                          dataType === 'total'
                            ? { dataKey: 'total_mom', color: COLORS.total, name: 'HICP（総合・前月比）' }
                            : { dataKey: 'core_mom', color: COLORS.core, name: 'HICP（コア：除エネ食品・前月比）' },
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
                <MarketImpactTab indicatorId="ecb_hicp" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
