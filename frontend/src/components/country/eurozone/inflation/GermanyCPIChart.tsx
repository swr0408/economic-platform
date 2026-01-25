/**
 * ドイツCPI/HICP チャートコンポーネント
 *
 * FMPデータベースからドイツ消費者物価指数データを取得し、表示
 *
 * データ:
 * - CPI 前年比 (YoY)
 * - CPI 前月比 (MoM)
 * - HICP 前年比 (YoY)
 * - HICP 前月比 (MoM)
 *
 * データソース:
 * - FMP Database (Destatis)
 *
 * 発表スケジュール:
 * - 速報: 毎月8-16日頃
 * - 確定: 毎月20-28日頃
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

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { GermanyCPIData } from '../../../../hooks/useDashboardData'

interface GermanyCPIChartProps {
  data: GermanyCPIData | null
}

interface ChartDataPoint {
  date: string
  cpi_yoy: number | null
  cpi_mom: number | null
  hicp_yoy: number | null
  hicp_mom: number | null
  [key: string]: unknown
}

// 表示モード
type ViewMode = 'yoy' | 'mom_table' | 'mom_chart'

const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom_chart', label: '前月比' },
  { mode: 'mom_table', label: '前月比（テーブル）' },
]

// データタイプ
type DataType = 'cpi' | 'hicp'

const DATA_TYPE_OPTIONS: { type: DataType; label: string }[] = [
  { type: 'cpi', label: 'CPI（国内基準）' },
  { type: 'hicp', label: 'HICP（EU調和基準）' },
]

// グラフの色
const COLORS = {
  cpi: '#1890ff',
  hicp: '#ff7875',
}

export default function GermanyCPIChart({ data }: GermanyCPIChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')
  const [dataType, setDataType] = useState<DataType>('cpi')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom_table: 'default',
    mom_chart: 3,
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const cpiYoyData = data.cpi_yoy || []
    const cpiMomData = data.cpi_mom || []
    const hicpYoyData = data.hicp_yoy || []
    const hicpMomData = data.hicp_mom || []

    // 日付をキーにしたマップを作成
    const dateMap = new Map<string, ChartDataPoint>()

    const initPoint = (date: string): ChartDataPoint => ({
      date,
      cpi_yoy: null,
      cpi_mom: null,
      hicp_yoy: null,
      hicp_mom: null,
    })

    cpiYoyData.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      dateMap.get(point.date)!.cpi_yoy = point.value
    })

    cpiMomData.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      dateMap.get(point.date)!.cpi_mom = point.value
    })

    hicpYoyData.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      dateMap.get(point.date)!.hicp_yoy = point.value
    })

    hicpMomData.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      dateMap.get(point.date)!.hicp_mom = point.value
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
      cpi: (item) => item.cpi_mom,
      hicp: (item) => item.hicp_mom,
    },
    10
  )

  const hasData = chartData.length > 0

  // 最新値を取得（前年比）
  const latestYoy = useMemo(() => {
    if (!chartData.length) return null
    // 前年比データがある最新のポイントを探す
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].cpi_yoy !== null || chartData[i].hicp_yoy !== null) {
        return chartData[i]
      }
    }
    return null
  }, [chartData])

  // 前月比の最新値を取得
  const latestMom = useMemo(() => {
    if (!chartData.length) return null
    // 前月比データがある最新のポイントを探す
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].cpi_mom !== null || chartData[i].hicp_mom !== null) {
        return chartData[i]
      }
    }
    return null
  }, [chartData])

  if (data === null) {
    return <LoadingChart title="CPI / HICP（ドイツ）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="CPI / HICP（ドイツ）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="germany-cpi-chart">
      <ChartContainer
        title="CPI / HICP（ドイツ）"
        showPeriodSelector={false}
        dataSource="Destatis"
        sourceUrl="https://www.destatis.de/SiteGlobals/Forms/Suche/Presse/DE/Pressesuche_Formular_2.html?resourceId=245598&input_=250572&pageLocale=de&templateQueryString=Inflationsrate+&submit.x=0&submit.y=0"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={
            viewMode === 'yoy'
              ? [
                  {
                    label: 'CPI',
                    value: latestYoy?.cpi_yoy,
                    color: COLORS.cpi,
                    format: 'percent',
                  },
                  {
                    label: 'HICP',
                    value: latestYoy?.hicp_yoy,
                    color: COLORS.hicp,
                    format: 'percent',
                  },
                ]
              : [
                  {
                    label: 'CPI（前月比）',
                    value: latestMom?.cpi_mom,
                    color: COLORS.cpi,
                    format: 'percent',
                  },
                  {
                    label: 'HICP（前月比）',
                    value: latestMom?.hicp_mom,
                    color: COLORS.hicp,
                    format: 'percent',
                  },
                ]
          }
          date={viewMode === 'yoy' ? latestYoy?.date : latestMom?.date}
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
                    <Tooltip title="比較ページを開く（ドイツCPI・HICP）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=germany_cpi_yoy&s=germany_hicp_yoy', '_blank')}
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
                          { dataKey: 'cpi_yoy', color: COLORS.cpi, name: 'CPI（前年比）' },
                          { dataKey: 'hicp_yoy', color: COLORS.hicp, name: 'HICP（前年比）' },
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
                          dataType === 'cpi'
                            ? { dataKey: 'cpi_mom', color: COLORS.cpi, name: 'CPI（前月比）' }
                            : { dataKey: 'hicp_mom', color: COLORS.hicp, name: 'HICP（前月比）' },
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
                <MarketImpactTab indicatorId="germany_cpi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
