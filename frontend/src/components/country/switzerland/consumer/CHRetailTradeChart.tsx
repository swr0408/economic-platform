/**
 * スイス小売売上高 チャートコンポーネント
 *
 * BFS（スイス連邦統計局）から小売売上高データを取得し、表示
 *
 * データ:
 * - 小売売上高 前月比（Retail Sales MoM）
 * - 小売売上高 前年比（Retail Sales YoY）
 *
 * データソース:
 * - BFS (Swiss Federal Statistical Office)
 *
 * 発表スケジュール:
 * - 毎月（FMPから次回発表日時取得）
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

import type { CHRetailTradeData } from '../../../../hooks/useDashboardData'

interface CHRetailTradeChartProps {
  data: CHRetailTradeData | null
}

interface ChartDataPoint {
  date: string
  yoy: number
  mom: number
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  yoy: '#DC143C', // スイス赤
  mom: '#52c41a', // 緑
}

type ViewMode = 'yoy' | 'mom_chart' | 'mom_table'

export default function CHRetailTradeChart({ data }: CHRetailTradeChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom_chart: 3,
    mom_table: 'default',
  })

  // propsのデータをチャート用に変換（前年比と前月比をマージ）
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((item) => ({
      date: item.date,
      yoy: item.yoy ?? 0,
      mom: item.mom ?? 0,
    }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ（年別×月別のマトリックス）
  const momTableData = useMonthlyTableData(chartData, (item) => item.mom)

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  if (data === null) {
    return <LoadingChart title="小売売上高" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="小売売上高" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ch-retail-trade-chart">
      <ChartContainer
        title="小売売上高"
        showPeriodSelector={false}
        dataSource="BFS (Swiss Federal Statistical Office)"
        sourceUrl="https://www.bfs.admin.ch/bfs/en/home/statistics/industry-services/production-orders-turnover.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={viewMode === 'yoy' ? latest?.yoy : latest?.mom}
          valueColor={viewMode === 'yoy' ? COLORS.yoy : COLORS.mom}
          date={latest?.date}
          nextRelease={data.next_release}
          format="percent"
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
                  {/* YoY/MoM切替 */}
                  <ViewModeButtonGroup
                    currentMode={viewMode}
                    onChange={(mode) => setViewMode(mode as ViewMode)}
                    options={[
                      { mode: 'yoy', label: '前年比' },
                      { mode: 'mom_chart', label: '前月比（グラフ）' },
                      { mode: 'mom_table', label: '前月比（テーブル）' },
                    ]}
                  />

                  {/* 期間セレクター */}
                  {(viewMode === 'yoy' || viewMode === 'mom_chart') && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <Tooltip title="比較ページを開く">
                        <Button
                          icon={<AreaChartOutlined />}
                          onClick={() => window.open('/compare?s=ch_retail_trade_yoy', '_blank')}
                        >
                          データ比較
                        </Button>
                      </Tooltip>
                    </div>
                  )}

                  {/* コンテンツ表示 */}
                  {viewMode === 'mom_table' && <MonthlyTable data={momTableData} />}

                  {viewMode === 'yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'yoy', color: COLORS.yoy, name: '小売売上高（前年比）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
                      yDomain={['dataMin - 2', 'dataMax + 2']}
                      showZeroLine={true}
                    />
                  )}

                  {viewMode === 'mom_chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'mom', color: COLORS.mom, name: '小売売上高（前月比）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ch_retail_trade" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
