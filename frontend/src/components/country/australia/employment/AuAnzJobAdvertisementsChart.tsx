/**
 * AU ANZ Job Advertisements Chart Component
 * オーストラリア ANZ求人広告チャート
 *
 * データ項目:
 * - value: ANZ-Indeed Job Advertisements Index (Seasonally Adjusted, 2019=100)
 * - mom: 前月比 (%)
 * - yoy: 前年比 (%)
 *
 * データソース: ANZ-Indeed
 */

import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  CHART_COLORS,
} from '../../usa/common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useHiddenSeries,
  useMonthlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  ViewModeButtonGroup,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { AuAnzJobAdvertisementsData, AuAnzJobAdvertisementsDataPoint } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface ChartDataPoint {
  date: string
  value: number | null
  mom: number | null
  yoy: number | null
}

interface AuAnzJobAdvertisementsChartProps {
  data: AuAnzJobAdvertisementsData | null
}

// ビューモード
type AnzViewMode = 'yoy' | 'mom_change' | 'mom_table' | 'index'

const VIEW_MODE_OPTIONS: { mode: AnzViewMode; label: string }[] = [
  { mode: 'mom_change', label: '前月比' },
  { mode: 'mom_table', label: '前月比（テーブル）' },
  { mode: 'yoy', label: '前年比' },
  { mode: 'index', label: '指数' },
]

// カラー設定
const COLORS = {
  index: '#8E44AD',
  mom: CHART_COLORS.primary,
  yoy: CHART_COLORS.primary,
}

// =============================================================================
// 日付フォーマット
// =============================================================================

const formatDateLabel = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}/${String(date.getMonth() + 1).padStart(2, '0')}`
}

const formatDateLabelJP = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}年${date.getMonth() + 1}月`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function AuAnzJobAdvertisementsChart({ data }: AuAnzJobAdvertisementsChartProps) {
  const [viewMode, setViewMode] = useState<AnzViewMode>('mom_change')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom_table: 'default',
    mom_change: 3,
    index: 'default',
  })

  // データを変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((d: AuAnzJobAdvertisementsDataPoint) =>
        d.value !== null || d.mom !== null || d.yoy !== null
      )
      .map((d: AuAnzJobAdvertisementsDataPoint) => ({
        date: d.date,
        value: d.value,
        mom: d.mom,
        yoy: d.yoy,
      }))
  }, [data])

  // データを日付昇順にソート
  const sortedData = useSortedData(chartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ
  const momTableData = useMonthlyTableData(sortedData, (item: ChartDataPoint) => item.mom)

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="ANZ求人広告" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="ANZ求人広告" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  return (
    <div id="au-anz-job-advertisements-chart">
      <ChartContainer
        title="ANZ求人広告"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="ANZ-Indeed"
        sourceUrl="https://www.anz.com.au/newsroom/media/release-dates/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: 'ANZ求人広告（MoM）',
              value: latest?.mom,
              color: COLORS.mom,
              format: 'percent',
            },
            {
              label: 'ANZ求人広告（YoY）',
              value: latest?.yoy,
              color: COLORS.yoy,
              format: 'percent',
            },
          ]}
          date={latest?.date}
          dateFormatter={formatDateLabelJP}
          nextRelease={data?.next_release ?? undefined}
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=au_anz_job_advertisements', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 前月比グラフ（棒グラフ） */}
                  {viewMode === 'mom_change' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'mom', color: COLORS.mom, name: 'ANZ求人広告（前月比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
                      />
                    </>
                  )}

                  {/* 前年比グラフ（折れ線グラフ） */}
                  {viewMode === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'yoy', color: COLORS.yoy, name: 'ANZ求人広告（前年比）', hide: hiddenSeries.has('yoy') },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 5', 'dataMax + 5']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
                        onLegendClick={handleLegendClick}
                      />
                    </>
                  )}

                  {/* 前月比テーブル */}
                  {viewMode === 'mom_table' && (
                    <MonthlyTable
                      data={momTableData}
                      decimals={1}
                      helperText="※ 直近10年間の前月比データ（単位: %）"
                    />
                  )}

                  {/* 指数（折れ線グラフ） */}
                  {viewMode === 'index' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'value', color: COLORS.index, name: 'ANZ求人広告指数（2019=100）', hide: hiddenSeries.has('value') },
                        ]}
                        yAxisFormatter={(v) => `${v}`}
                        yDomain={['dataMin - 10', 'dataMax + 10']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateLabelJP}
                        tooltipValueFormatter={(v) => `${v.toFixed(1)}`}
                        onLegendClick={handleLegendClick}
                      />
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="au_anz_job_advertisements" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
