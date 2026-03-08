/**
 * スペインHICP/CPI チャートコンポーネント
 *
 * INE (Instituto Nacional de Estadística) からスペイン消費者物価指数データを取得し、表示
 *
 * データ:
 * - CPI 前年比 (YoY)
 * - CPI 前月比 (MoM)
 * - コアCPI 前年比 (YoY)
 * - コアCPI 前月比 (MoM)
 * - HICP 前年比 (YoY)
 * - HICP 前月比 (MoM)
 *
 * データソース:
 * - INE (Instituto Nacional de Estadística)
 *
 * 発表スケジュール:
 * - 速報: 毎月月末頃
 * - 確定: 翌月中旬頃
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

import type { SpainHICPCPIData } from '../../../../hooks/useDashboardData'

interface SpainHICPCPIChartProps {
  data: SpainHICPCPIData | null
}

interface ChartDataPoint {
  date: string
  cpi_yoy: number | null
  cpi_mom: number | null
  core_cpi_yoy: number | null
  core_cpi_mom: number | null
  hicp_yoy: number | null
  hicp_mom: number | null
  [key: string]: unknown
}

// 表示モード
type DataKind = 'yoy' | 'mom'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
]

type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// データタイプ
type DataType = 'cpi' | 'core_cpi' | 'hicp'

const DATA_TYPE_OPTIONS: { type: DataType; label: string }[] = [
  { type: 'cpi', label: 'CPI' },
  { type: 'core_cpi', label: 'コアCPI' },
  { type: 'hicp', label: 'HICP' },
]

// グラフの色
const COLORS = {
  cpi: '#1890ff',
  core_cpi: '#52c41a',
  hicp: '#ff7875',
}

export default function SpainHICPCPIChart({ data }: SpainHICPCPIChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [dataType, setDataType] = useState<DataType>('cpi')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 'default',
    mom: 3,
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const cpiYoyData = data.cpi_yoy || []
    const cpiMomData = data.cpi_mom || []
    const coreCpiYoyData = data.core_cpi_yoy || []
    const coreCpiMomData = data.core_cpi_mom || []
    const hicpYoyData = data.hicp_yoy || []
    const hicpMomData = data.hicp_mom || []

    // 日付をキーにしたマップを作成
    const dateMap = new Map<string, ChartDataPoint>()

    const initPoint = (date: string): ChartDataPoint => ({
      date,
      cpi_yoy: null,
      cpi_mom: null,
      core_cpi_yoy: null,
      core_cpi_mom: null,
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

    coreCpiYoyData.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      dateMap.get(point.date)!.core_cpi_yoy = point.value
    })

    coreCpiMomData.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      dateMap.get(point.date)!.core_cpi_mom = point.value
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
      core_cpi: (item) => item.core_cpi_mom,
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
      if (chartData[i].cpi_yoy !== null || chartData[i].core_cpi_yoy !== null || chartData[i].hicp_yoy !== null) {
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
      if (chartData[i].cpi_mom !== null || chartData[i].core_cpi_mom !== null || chartData[i].hicp_mom !== null) {
        return chartData[i]
      }
    }
    return null
  }, [chartData])

  if (data === null) {
    return <LoadingChart title="CPI / HICP（スペイン）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="CPI / HICP（スペイン）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="spain-hicp-cpi-chart">
      <ChartContainer
        title="CPI / HICP（スペイン）"
        showPeriodSelector={false}
        dataSource="INE"
        sourceUrl="https://www.ine.es/en/prensa/ipc_prensa_en.htm"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={
            dataKind === 'yoy'
              ? [
                  {
                    label: 'CPI',
                    value: latestYoy?.cpi_yoy,
                    color: COLORS.cpi,
                    format: 'percent',
                  },
                  {
                    label: 'コアCPI',
                    value: latestYoy?.core_cpi_yoy,
                    color: COLORS.core_cpi,
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
                    label: 'コアCPI（前月比）',
                    value: latestMom?.core_cpi_mom,
                    color: COLORS.core_cpi,
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
          date={dataKind === 'yoy' ? latestYoy?.date : latestMom?.date}
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
                  {/* 上段: 指標種別 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />
                    <Tooltip title="比較ページを開く（スペインCPI・HICP）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=spain_cpi_yoy&s=spain_hicp_yoy', '_blank')}
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
                          { dataKey: 'cpi_yoy', color: COLORS.cpi, name: 'CPI（前年比）' },
                          { dataKey: 'core_cpi_yoy', color: COLORS.core_cpi, name: 'コアCPI（前年比）' },
                          { dataKey: 'hicp_yoy', color: COLORS.hicp, name: 'HICP（前年比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        showZeroLine={true}
                      />
                    </>
                  )}

                  {/* 前月比テーブル */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTableWithDataTypes
                      data={momTableData}
                      dataTypes={DATA_TYPE_OPTIONS}
                      selectedType={dataType}
                      onTypeChange={setDataType}
                    />
                  )}

                  {/* 前月比グラフ */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <DataTypeButtonGroup options={DATA_TYPE_OPTIONS} currentType={dataType} onChange={setDataType} />
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          dataType === 'cpi'
                            ? { dataKey: 'cpi_mom', color: COLORS.cpi, name: 'CPI（前月比）' }
                            : dataType === 'core_cpi'
                              ? { dataKey: 'core_cpi_mom', color: COLORS.core_cpi, name: 'コアCPI（前月比）' }
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
                <MarketImpactTab indicatorId="spain_hicp_cpi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
