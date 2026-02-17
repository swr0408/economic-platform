/**
 * AU Wage Price Index Chart Component
 * オーストラリア 賃金物価指数チャート
 *
 * データ項目:
 * - qoq: WPI 前期比 (%)
 * - yoy: WPI 前年比 (%)
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
  useQuarterlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  ViewModeButtonGroup,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { QuarterlyTable } from '../../usa/common/QuarterlyTable'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { AuWagePriceIndexData, AuWagePriceIndexDataPoint } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface ChartDataPoint {
  date: string
  qoq: number | null
  yoy: number | null
}

interface AuWagePriceIndexChartProps {
  data: AuWagePriceIndexData | null
}

// ビューモード
type WpiViewMode = 'yoy' | 'qoq_chart' | 'qoq_table'

const WPI_VIEW_MODE_OPTIONS: { mode: WpiViewMode; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'qoq_chart', label: '前期比' },
  { mode: 'qoq_table', label: '前期比（テーブル）' },
]

// カラー設定
const COLORS = {
  yoy: CHART_COLORS.primary,
  qoq: CHART_COLORS.primary,
}

// =============================================================================
// 日付フォーマット
// =============================================================================

const formatDateLabel = (dateStr: string): string => {
  // YYYY-QN format from ABS
  const match = dateStr.match(/^(\d{4})-Q(\d)$/)
  if (match) return `${match[1]}/Q${match[2]}`
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  const month = date.getMonth() + 1
  const quarter = Math.ceil(month / 3)
  return `${date.getFullYear()}/Q${quarter}`
}

const formatDateLabelJP = (dateStr: string): string => {
  const match = dateStr.match(/^(\d{4})-Q(\d)$/)
  if (match) return `${match[1]}年 Q${match[2]}`
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  const month = date.getMonth() + 1
  const quarter = Math.ceil(month / 3)
  return `${date.getFullYear()}年 Q${quarter}`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function AuWagePriceIndexChart({ data }: AuWagePriceIndexChartProps) {
  const [viewMode, setViewMode] = useState<WpiViewMode>('yoy')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    qoq_table: 'default',
    qoq_chart: 'default',
  })

  // データを変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((d: AuWagePriceIndexDataPoint) =>
        d.qoq !== null || d.yoy !== null
      )
      .map((d: AuWagePriceIndexDataPoint) => ({
        date: d.date,
        qoq: d.qoq,
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
  const qoqTableData = useQuarterlyTableData(
    sortedData,
    (item: ChartDataPoint) => item.qoq,
    10
  )

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="賃金物価指数（WPI）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="賃金物価指数（WPI）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  // 次回発表日のフォーマット
  const formatNextRelease = () => {
    if (!data?.next_release) return null
    const nr = data.next_release
    if (nr.date) {
      const dt = new Date(nr.date)
      return `${dt.getMonth() + 1}/${dt.getDate()}`
    }
    return null
  }

  return (
    <div id="au-wage-price-index-chart">
      <ChartContainer
        title="賃金物価指数"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="Australian Bureau of Statistics"
        sourceUrl="https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/wage-price-index-australia"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '賃金物価指数（QoQ）',
              value: latest?.qoq,
              color: COLORS.qoq,
              format: 'percent',
            },
            {
              label: '賃金物価指数（YoY）',
              value: latest?.yoy,
              color: COLORS.yoy,
              format: 'percent',
            },
          ]}
          date={latest?.date}
          dateFormatter={formatDateLabelJP}
          nextRelease={data?.next_release ? { date: formatNextRelease() || '' } : undefined}
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
                    <ViewModeButtonGroup options={WPI_VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=au_wage_price_index_yoy', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 前年比グラフ（折れ線グラフ） */}
                  {viewMode === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'yoy', color: COLORS.yoy, name: '賃金物価指数（前年比）', hide: hiddenSeries.has('yoy') },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                        onLegendClick={handleLegendClick}
                      />
                    </>
                  )}

                  {/* テーブル */}
                  {viewMode === 'qoq_table' && (
                    <QuarterlyTable
                      data={qoqTableData}
                      decimals={1}
                      helperText="※ 直近10年間のデータ（単位: %）"
                    />
                  )}

                  {/* 前期比グラフ（棒グラフ） */}
                  {viewMode === 'qoq_chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'qoq', color: COLORS.qoq, name: '賃金物価指数（前期比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
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
                <MarketImpactTab indicatorId="au_wage_price_index" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
