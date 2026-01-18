/**
 * ドイツ小売売上高チャートコンポーネント
 *
 * データ:
 * - 小売売上高前年比 (YoY) - 45212-0004から取得
 * - 小売売上高前月比 (MoM) - 45212-0005の季節調整済み指数から計算
 *
 * データソース:
 * - Destatis GENESIS API (45212-0004, 45212-0005)
 * - keh331テーブルと同等のデータ
 *
 * 注意:
 * - MoMはX13 JDemetra+ 季節調整済み指数から計算
 * - プレスリリース発表から約2週間後にGENESIS/keh331テーブル更新
 *
 * 発表スケジュール:
 * - 毎月（不定期）
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
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { GermanyRetailSalesData } from '../../../../hooks/useDashboardData'

interface GermanyRetailSalesChartProps {
  data: GermanyRetailSalesData | null
}

interface ChartDataPoint {
  date: string
  yoy: number
  mom: number
  [key: string]: unknown
}

type ViewMode = 'yoy' | 'mom_table' | 'mom_chart'

// グラフの色
const COLORS = {
  yoy: '#1890ff',
  mom: '#52c41a',
}

export default function GermanyRetailSalesChart({ data }: GermanyRetailSalesChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom_table: 'default',
    mom_chart: 3,
  })

  // propsのデータをチャート用に変換（前年比と前月比をマージ）
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const dateMap = new Map<string, ChartDataPoint>()

    // 前年比データをマージ
    if (data.retail_sales_yoy) {
      data.retail_sales_yoy.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, { date: point.date, yoy: 0, mom: 0 })
        }
        const existing = dateMap.get(point.date)!
        existing.yoy = point.value
      })
    }

    // 前月比データをマージ
    if (data.retail_sales_mom) {
      data.retail_sales_mom.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, { date: point.date, yoy: 0, mom: 0 })
        }
        const existing = dateMap.get(point.date)!
        existing.mom = point.value
      })
    }

    return Array.from(dateMap.values()).sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
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
    return <LoadingChart title="小売売上高（ドイツ）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="小売売上高（ドイツ）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="germany-retail-sales-chart">
      <ChartContainer
        title="小売売上高（ドイツ）"
        showPeriodSelector={false}
        dataSource="Destatis"
        sourceUrl="https://www.destatis.de/DE/Themen/Wirtschaft/Grosshandel-Einzelhandel/_inhalt.html"
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
                  <ViewModeButtonGroup
                    currentMode={viewMode}
                    onChange={(mode) => setViewMode(mode)}
                    options={[
                      { mode: 'yoy', label: '前年比' },
                      { mode: 'mom_table', label: '前月比テーブル（季節調整済）' },
                      { mode: 'mom_chart', label: '前月比グラフ（季節調整済）' },
                    ]}
                  />

                  {/* 期間セレクター */}
                  {(viewMode === 'yoy' || viewMode === 'mom_chart') && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <Tooltip title="比較ページを開く">
                        <Button
                          icon={<AreaChartOutlined />}
                          onClick={() => window.open('/compare?s=germany_retail_sales_yoy&s=ecb_retail_trade_yoy', '_blank')}
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
                        { dataKey: 'yoy', color: COLORS.yoy, name: '小売売上高（前年比）', hide: hiddenSeries.has('yoy') },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      onLegendClick={handleLegendClick}
                    />
                  )}

                  {viewMode === 'mom_chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'mom', color: COLORS.mom, name: '小売売上高（前月比・季節調整済）' },
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
                <MarketImpactTab indicatorId="germany_retail_sales" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
