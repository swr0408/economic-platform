/**
 * スイスCPI チャートコンポーネント
 *
 * BFS（スイス連邦統計局）からスイス消費者物価指数データを取得し、表示
 *
 * データ:
 * - CPI Total 前年比 (YoY)
 * - CPI Total 前月比 (MoM)
 * - Kerninflation 1 (コアインフレ1: 生鮮食品・エネルギー除く)
 * - Kerninflation 2 (コアインフレ2: 生鮮食品・季節品・エネルギー除く)
 *
 * データソース:
 * - Swiss Federal Statistical Office (BFS)
 *
 * 発表スケジュール:
 * - 毎月初旬（BFS発表）
 * - 発表時刻: 08:30 チューリッヒ時間（16:30 JST）
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

import type { ChCPIData } from '../../../../hooks/useDashboardData'

interface ChCPIChartProps {
  data: ChCPIData | null
}

interface ChartDataPoint {
  date: string
  cpi_yoy: number | null
  cpi_mom: number | null
  core1_yoy: number | null
  core1_mom: number | null
  core2_yoy: number | null
  core2_mom: number | null
  [key: string]: unknown
}

// 指標種別
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
type DataType = 'total' | 'core1' | 'core2'

const DATA_TYPE_OPTIONS: { type: DataType; label: string }[] = [
  { type: 'total', label: 'CPI' },
  { type: 'core1', label: 'コアCPI（生鮮・季節品・エネルギー・燃料除く）' },
  { type: 'core2', label: 'コアCPI（生鮮・季節品・エネルギー・燃料・管理価格除く）' },
]

// グラフの色
const COLORS = {
  cpi: '#DC143C', // スイス赤
  core1: '#1890ff', // 青
  core2: '#52c41a', // 緑
}

export default function ChCPIChart({ data }: ChCPIChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [dataType, setDataType] = useState<DataType>('total')

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 10,
    mom: 3,
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((item) => ({
      date: item.date,
      cpi_yoy: item.cpi_yoy,
      cpi_mom: item.cpi_mom,
      core1_yoy: item.core1_yoy ?? null,
      core1_mom: item.core1_mom ?? null,
      core2_yoy: item.core2_yoy ?? null,
      core2_mom: item.core2_mom ?? null,
    }))
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
      total: (item) => item.cpi_mom,
      core1: (item) => item.core1_mom,
      core2: (item) => item.core2_mom,
    },
    10
  )

  const hasData = chartData.length > 0

  // 最新値を取得（前年比）
  const latestYoy = useMemo(() => {
    if (!chartData.length) return null
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].cpi_yoy !== null) {
        return chartData[i]
      }
    }
    return null
  }, [chartData])

  // 前月比の最新値を取得
  const latestMom = useMemo(() => {
    if (!chartData.length) return null
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].cpi_mom !== null) {
        return chartData[i]
      }
    }
    return null
  }, [chartData])

  if (data === null) {
    return <LoadingChart title="CPI（スイス）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="CPI（スイス）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 選択されたデータタイプに応じたMoMキーを取得
  const getMomDataKey = () => {
    switch (dataType) {
      case 'core1':
        return 'core1_mom'
      case 'core2':
        return 'core2_mom'
      default:
        return 'cpi_mom'
    }
  }

  // 選択されたデータタイプに応じた色を取得
  const getColor = () => {
    switch (dataType) {
      case 'core1':
        return COLORS.core1
      case 'core2':
        return COLORS.core2
      default:
        return COLORS.cpi
    }
  }

  // 選択されたデータタイプに応じた名前を取得
  const getDataTypeName = () => {
    switch (dataType) {
      case 'core1':
        return 'コアCPI（生鮮・季節品・エネルギー・燃料除く）'
      case 'core2':
        return 'コアCPI（生鮮・季節品・エネルギー・燃料・管理価格除く）'
      default:
        return 'CPI'
    }
  }

  return (
    <div id="ch-cpi-chart">
      <ChartContainer
        title="CPI"
        showPeriodSelector={false}
        dataSource="Swiss Federal Statistical Office (BFS)"
        sourceUrl="https://www.bfs.admin.ch/bfs/en/home/statistics/prices/consumer-price-index.html"
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
                    label: 'コアCPI（生鮮・季節品・エネルギー・燃料除く）',
                    value: latestYoy?.core1_yoy,
                    color: COLORS.core1,
                    format: 'percent',
                  },
                  {
                    label: 'コアCPI（生鮮・季節品・エネルギー・燃料・管理価格除く）',
                    value: latestYoy?.core2_yoy,
                    color: COLORS.core2,
                    format: 'percent',
                  },
                ]
              : [
                  {
                    label: 'CPI',
                    value: latestMom?.cpi_mom,
                    color: COLORS.cpi,
                    format: 'percent',
                  },
                  {
                    label: 'コアCPI（生鮮・季節品・エネルギー・燃料除く）',
                    value: latestMom?.core1_mom,
                    color: COLORS.core1,
                    format: 'percent',
                  },
                  {
                    label: 'コアCPI（生鮮・季節品・エネルギー・燃料・管理価格除く）',
                    value: latestMom?.core2_mom,
                    color: COLORS.core2,
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
                    <Tooltip title="比較ページを開く（スイスCPI）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=ch_cpi_yoy', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
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
                          { dataKey: 'cpi_yoy', color: COLORS.cpi, name: 'CPI' },
                          { dataKey: 'core1_yoy', color: COLORS.core1, name: 'コアCPI（生鮮・季節品・エネルギー・燃料除く）' },
                          { dataKey: 'core2_yoy', color: COLORS.core2, name: 'コアCPI（生鮮・季節品・エネルギー・燃料・管理価格除く）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        showZeroLine={true}
                      />
                    </>
                  )}

                  {/* 前月比ヒートマップ */}
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
                          { dataKey: getMomDataKey(), color: getColor(), name: `${getDataTypeName()}` },
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
                <MarketImpactTab indicatorId="ch_cpi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
