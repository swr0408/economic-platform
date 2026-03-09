/**
 * スイスPPI（生産者・輸入物価指数）チャートコンポーネント
 *
 * BFS（スイス連邦統計局）からスイス生産者・輸入物価指数データを取得し、表示
 *
 * データ:
 * - PPI 前年比 (YoY)
 * - PPI 前月比 (MoM)
 *
 * データソース:
 * - Swiss Federal Statistical Office (BFS)
 *
 * 発表スケジュール:
 * - 毎月中旬（BFS発表）
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
  useMonthlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
  StandardBarChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { ChPPIData } from '../../../../hooks/useDashboardData'

interface ChPPIChartProps {
  data: ChPPIData | null
}

interface ChartDataPoint {
  date: string
  ppi_yoy: number | null
  ppi_mom: number | null
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

// グラフの色
const COLORS = {
  ppi: '#DC143C', // スイス赤
}

export default function ChPPIChart({ data }: ChPPIChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

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
      ppi_yoy: item.ppi_yoy,
      ppi_mom: item.ppi_mom,
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
  const momTableData = useMonthlyTableData(
    chartData,
    (item) => item.ppi_mom,
    10
  )

  const hasData = chartData.length > 0

  // 最新値を取得（前年比）
  const latestYoy = useMemo(() => {
    if (!chartData.length) return null
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].ppi_yoy !== null) {
        return chartData[i]
      }
    }
    return null
  }, [chartData])

  // 前月比の最新値を取得
  const latestMom = useMemo(() => {
    if (!chartData.length) return null
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].ppi_mom !== null) {
        return chartData[i]
      }
    }
    return null
  }, [chartData])

  if (data === null) {
    return <LoadingChart title="PPI（スイス）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="PPI（スイス）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ch-ppi-chart">
      <ChartContainer
        title="PPI"
        showPeriodSelector={false}
        dataSource="Swiss Federal Statistical Office (BFS)"
        sourceUrl="https://www.bfs.admin.ch/bfs/en/home/statistics/prices/producer-prices-import-prices.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="PPI"
          value={dataKind === 'yoy' ? latestYoy?.ppi_yoy : latestMom?.ppi_mom}
          date={dataKind === 'yoy' ? latestYoy?.date : latestMom?.date}
          format="percent"
          valueColor={COLORS.ppi}
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
                    <Tooltip title="比較ページを開く（スイスPPI）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=ch_ppi_yoy', '_blank')}
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
                          { dataKey: 'ppi_yoy', color: COLORS.ppi, name: 'PPI' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        showZeroLine={true}
                      />
                    </>
                  )}

                  {/* 前月比ヒートマップ */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTable data={momTableData} />
                  )}

                  {/* 前月比グラフ */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'ppi_mom', color: COLORS.ppi, name: 'PPI' },
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
                <MarketImpactTab indicatorId="ch_ppi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
