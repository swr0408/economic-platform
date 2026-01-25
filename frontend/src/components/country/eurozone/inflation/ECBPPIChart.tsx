/**
 * ECB PPI チャートコンポーネント
 *
 * ECB Data APIからユーロ圏生産者物価指数(PPI)データを取得し、表示
 *
 * データ:
 * - PPI (前年比/前月比)
 *
 * データソース:
 * - European Central Bank (ECB)
 *
 * 発表スケジュール:
 * - 発表: 毎月1日〜8日 18:00-18:10 CET (冬時間: 19:00-19:10 JST)
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
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { ECBPPIData } from '../../../../hooks/useDashboardData'

interface ECBPPIChartProps {
  data: ECBPPIData | null
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
  { mode: 'mom_chart', label: '前月比' },
  { mode: 'mom_table', label: '前月比（テーブル）' },
]

// グラフの色
const COLORS = {
  ppi: '#1890ff',
}

export default function ECBPPIChart({ data }: ECBPPIChartProps) {
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
    if (!data || !data.annual_rates) return []

    const ppiYoyData = data.annual_rates.ppi || []
    const ppiMomData = data.monthly_changes?.ppi || []

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

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    // 前年比データがある最新のポイントを探す
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].ppi_yoy !== null) {
        return chartData[i]
      }
    }
    return chartData[chartData.length - 1]
  }, [chartData])

  // 前月比の最新値を取得
  const latestMom = useMemo(() => {
    if (!chartData.length) return null
    // 前月比データがある最新のポイントを探す
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].ppi_mom !== null) {
        return chartData[i]
      }
    }
    return null
  }, [chartData])

  if (data === null) {
    return <LoadingChart title="PPI（ユーロ圏・生産者物価指数）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="PPI（ユーロ圏・生産者物価指数）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ecb-ppi-chart">
      <ChartContainer
        title="PPI（ユーロ圏・生産者物価指数）"
        showPeriodSelector={false}
        dataSource="Eurostat"
        sourceUrl="https://ec.europa.eu/eurostat/en/web/main/news/euro-indicators?p_p_id=estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageNumber=1&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_action=search&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageSize=11&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_collection=CAT_PREREL&p_auth=ZIoPsCO4&text=Industrial+producer+prices"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={
            viewMode === 'yoy'
              ? [
                  {
                    label: 'PPI（前年比）',
                    value: latest?.ppi_yoy,
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
                    <Tooltip title="比較ページを開く（PPI）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=eurozone_ppi_yoy', '_blank')}
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
                          { dataKey: 'ppi_yoy', color: COLORS.ppi, name: 'PPI（前年比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                        showZeroLine={true}
                      />
                    </>
                  )}

                  {/* 前月比テーブル */}
                  {viewMode === 'mom_table' && (
                    <MonthlyTable
                      data={momTableData}
                      helperText="※ 直近10年間の前月比データ（単位: %）"
                    />
                  )}

                  {/* 前月比グラフ */}
                  {viewMode === 'mom_chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'ppi_mom', color: COLORS.ppi, name: 'PPI（前月比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
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
                <MarketImpactTab indicatorId="ecb_ppi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
