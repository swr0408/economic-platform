/**
 * AU Household Spending Chart Component
 * オーストラリア 家計支出チャート
 *
 * データ項目:
 * - mom: 前月比 (%)
 * - yoy: 前年比 (%)
 *
 * データソース: Australian Bureau of Statistics (ABS)
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

import type { AuHouseholdSpendingData, AuHouseholdSpendingDataPoint } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface ChartDataPoint {
  date: string
  mom: number | null
  yoy: number | null
}

interface AuHouseholdSpendingChartProps {
  data: AuHouseholdSpendingData | null
}

// データ種別
type DataKind = 'yoy' | 'mom'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'mom', label: '前月比' },
  { mode: 'yoy', label: '前年比' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// カラー設定
const COLORS = {
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

export default function AuHouseholdSpendingChart({ data }: AuHouseholdSpendingChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('mom')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 20,
    mom: 3,
  })

  // データを変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((d: AuHouseholdSpendingDataPoint) =>
        d.mom !== null || d.yoy !== null
      )
      .map((d: AuHouseholdSpendingDataPoint) => ({
        date: d.date,
        mom: d.mom,
        yoy: d.yoy,
      }))
  }, [data])

  // データを日付昇順にソート
  const sortedData = useSortedData(chartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  // テーブル用データ
  const momTableData = useMonthlyTableData(sortedData, (item: ChartDataPoint) => item.mom)

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="家計支出" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="家計支出" showPeriodSelector={false} showDataSource={false} handbookId="household-spending">
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  return (
    <div id="au-household-spending-chart">
      <ChartContainer
        title="家計支出"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="Australian Bureau of Statistics"
        sourceUrl="https://www.abs.gov.au/statistics/economy/finance/monthly-household-spending-indicator"
        handbookId="household-spending"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '家計支出（MoM）',
              value: latest?.mom,
              color: COLORS.mom,
              format: 'percent',
            },
            {
              label: '家計支出（YoY）',
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
                  {/* 上段: 指標種別 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(`/compare?s=au_household_spending_${dataKind}`, '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
                  {/* 下段: 表示形式（変動系のときのみ） */}
                  {dataKind === 'mom' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 前月比グラフ（棒グラフ） */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'mom', color: COLORS.mom, name: '家計支出（前月比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                      />
                    </>
                  )}

                  {/* 前月比ヒートマップ */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTable
                      data={momTableData}
                      decimals={1}
                      helperText="※ 直近10年間の前月比データ（単位: %）"
                    />
                  )}

                  {/* 前年比グラフ（折れ線グラフ） */}
                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'yoy', color: COLORS.yoy, name: '家計支出（前年比）', hide: hiddenSeries.has('yoy') },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
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
                <MarketImpactTab indicatorId="au_household_spending" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
