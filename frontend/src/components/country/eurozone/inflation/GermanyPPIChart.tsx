/**
 * ドイツPPI チャートコンポーネント
 *
 * FMPデータベースからドイツ生産者物価指数データを取得し、表示
 *
 * データ:
 * - PPI 前年比 (YoY)
 * - PPI 前月比 (MoM)
 *
 * データソース:
 * - FMP Database (Destatis)
 *
 * 発表スケジュール:
 * - 毎月4日〜23日頃
 * - 15:00-16:10 CET
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
  LatestValueBox,
  StandardLineChart,
  StandardBarChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { GermanyPPIData } from '../../../../hooks/useDashboardData'

interface GermanyPPIChartProps {
  data: GermanyPPIData | null
}

interface ChartDataPoint {
  date: string
  ppi_yoy: number | null
  ppi_mom: number | null
  [key: string]: unknown
}

// 表示モード
type ViewMode = 'yoy' | 'mom_table' | 'mom_chart'

const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom_table', label: '前月比テーブル' },
  { mode: 'mom_chart', label: '前月比グラフ' },
]

// グラフの色
const COLORS = {
  ppi: '#faad14',
}

export default function GermanyPPIChart({ data }: GermanyPPIChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom_table: 'default',
    mom_chart: 3,
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const ppiYoyData = data.ppi_yoy || []
    const ppiMomData = data.ppi_mom || []

    // 日付をキーにしたマップを作成
    const dateMap = new Map<string, ChartDataPoint>()

    const initPoint = (date: string): ChartDataPoint => ({
      date,
      ppi_yoy: null,
      ppi_mom: null,
    })

    ppiYoyData.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      dateMap.get(point.date)!.ppi_yoy = point.value
    })

    ppiMomData.forEach((point) => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      dateMap.get(point.date)!.ppi_mom = point.value
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
  const momTableData = useMonthlyTableData(chartData, (item) => item.ppi_mom, 10)

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
    return <LoadingChart title="PPI（ドイツ）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="PPI（ドイツ）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="germany-ppi-chart">
      <ChartContainer
        title="PPI（ドイツ）"
        showPeriodSelector={false}
        dataSource="Destatis"
        sourceUrl="https://www.destatis.de/SiteGlobals/Forms/Suche/Presse/DE/Pressesuche_Formular_2.html?resourceId=245598&input_=250572&pageLocale=de&templateQueryString=Erzeugerpreise+&submit.x=0&submit.y=0"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={
            viewMode === 'yoy'
              ? [
                  {
                    label: 'PPI（前年比）',
                    value: latestYoy?.ppi_yoy,
                    color: COLORS.ppi,
                    format: 'percent',
                  },
                ]
              : [
                  {
                    label: 'PPI（前月比）',
                    value: latestMom?.ppi_mom,
                    color: COLORS.ppi,
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
                    <Tooltip title="比較ページを開く（ドイツPPI）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=germany_ppi_yoy', '_blank')}
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
                        lines={[{ dataKey: 'ppi_yoy', color: COLORS.ppi, name: 'PPI（前年比）' }]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        showZeroLine={true}
                      />
                    </>
                  )}

                  {/* 前月比テーブル */}
                  {viewMode === 'mom_table' && <MonthlyTable data={momTableData} />}

                  {/* 前月比グラフ */}
                  {viewMode === 'mom_chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[{ dataKey: 'ppi_mom', color: COLORS.ppi, name: 'PPI（前月比）' }]}
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
                <MarketImpactTab indicatorId="germany_ppi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
