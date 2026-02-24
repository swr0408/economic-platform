/**
 * AU Westpac Consumer Confidence Index Chart Component
 * オーストラリア Westpac消費者信頼感指数チャート
 *
 * データ項目:
 * - value: 消費者信頼感指数
 * - change: 前月比 (%)
 *
 * データソース: Westpac-Melbourne Institute
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

import type { AuWestpacConsumerConfidenceData, AuWestpacConsumerConfidenceDataPoint } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface ChartDataPoint {
  date: string
  value: number | null
  change: number | null
}

interface AuWestpacConsumerConfidenceChartProps {
  data: AuWestpacConsumerConfidenceData | null
}

// ビューモード
type WccViewMode = 'change' | 'change_table' | 'index'

const VIEW_MODE_OPTIONS: { mode: WccViewMode; label: string }[] = [
  { mode: 'index', label: '指数' },
  { mode: 'change', label: '前月比' },
  { mode: 'change_table', label: '前月比（テーブル）' },
]

// カラー設定
const COLORS = {
  index: '#2E86C1',
  change: CHART_COLORS.primary,
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

export default function AuWestpacConsumerConfidenceChart({ data }: AuWestpacConsumerConfidenceChartProps) {
  const [viewMode, setViewMode] = useState<WccViewMode>('index')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    index: 'default',
    change: 3,
    change_table: 'default',
  })

  // データを変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((d: AuWestpacConsumerConfidenceDataPoint) =>
        d.value !== null || d.change !== null
      )
      .map((d: AuWestpacConsumerConfidenceDataPoint) => ({
        date: d.date,
        value: d.value,
        change: d.change,
      }))
  }, [data])

  // データを日付昇順にソート
  const sortedData = useSortedData(chartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2016,
  })

  // テーブル用データ
  const changeTableData = useMonthlyTableData(sortedData, (item: ChartDataPoint) => item.change)

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="Westpac消費者信頼感指数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="Westpac消費者信頼感指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  return (
    <div id="au-westpac-consumer-confidence-chart">
      <ChartContainer
        title="Westpac消費者信頼感指数"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="Westpac-Melbourne Institute"
        sourceUrl="https://www.westpaciq.com.au/topic.consumersentiment.html"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '消費者信頼感（MoM）',
              value: latest?.change,
              color: COLORS.change,
              format: 'percent',
            },
            {
              label: '消費者信頼感指数',
              value: latest?.value,
              color: COLORS.index,
              format: 'number',
              decimals: 1,
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
                        onClick={() => window.open('/compare?s=au_westpac_consumer_confidence_index', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 前月比グラフ（棒グラフ） */}
                  {viewMode === 'change' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'change', color: COLORS.change, name: '消費者信頼感（前月比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                      />
                    </>
                  )}

                  {/* 前月比テーブル */}
                  {viewMode === 'change_table' && (
                    <MonthlyTable
                      data={changeTableData}
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
                          { dataKey: 'value', color: COLORS.index, name: 'Westpac消費者信頼感指数', hide: hiddenSeries.has('value') },
                        ]}
                        yAxisFormatter={(v) => `${v}`}
                        yDomain={['dataMin - 5', 'dataMax + 5']}
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
                <MarketImpactTab indicatorId="au_westpac_consumer_confidence_index" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
