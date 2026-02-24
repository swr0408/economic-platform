/**
 * AU NAB Business Confidence Index Chart Component
 * オーストラリア NAB企業信頼感指数チャート
 *
 * データ項目:
 * - value: NAB Business Confidence Index
 * - mom: 前月比（ポイント差分）
 *
 * データソース: National Australia Bank
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

import type { AuNabBusinessConfidenceData, AuNabBusinessConfidenceDataPoint } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface ChartDataPoint {
  date: string
  value: number | null
  mom: number | null
}

interface AuNabConfidenceIndexChartProps {
  data: AuNabBusinessConfidenceData | null
}

// ビューモード
type NabViewMode = 'mom' | 'mom_table' | 'index'

const VIEW_MODE_OPTIONS: { mode: NabViewMode; label: string }[] = [
  { mode: 'index', label: '指数' },
  { mode: 'mom', label: '前月比' },
  { mode: 'mom_table', label: '前月比（テーブル）' },
]

// カラー設定
const COLORS = {
  index: '#D4AC0D',
  mom: CHART_COLORS.primary,
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

export default function AuNabConfidenceIndexChart({ data }: AuNabConfidenceIndexChartProps) {
  const [viewMode, setViewMode] = useState<NabViewMode>('index')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    mom: 3,
    mom_table: 'default',
    index: 'default',
  })

  // データを変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((d: AuNabBusinessConfidenceDataPoint) =>
        d.value !== null || d.mom !== null
      )
      .map((d: AuNabBusinessConfidenceDataPoint) => ({
        date: d.date,
        value: d.value,
        mom: d.mom,
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
    return <LoadingChart title="NAB企業信頼感指数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="NAB企業信頼感指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  return (
    <div id="au-nab-business-confidence-chart">
      <ChartContainer
        title="NAB企業信頼感指数"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="National Australia Bank"
        sourceUrl="https://news.nab.com.au/tag/economic-market"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: 'NAB企業信頼感（MoM）',
              value: latest?.mom,
              color: COLORS.mom,
              format: 'number',
              decimals: 1,
            },
            {
              label: 'NAB企業信頼感指数',
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
                        onClick={() => window.open('/compare?s=au_nab_business_confidence_index', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 前月比グラフ（棒グラフ） */}
                  {viewMode === 'mom' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'mom', color: COLORS.mom, name: 'NAB企業信頼感（前月比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}`}
                        yDomain={['dataMin - 2', 'dataMax + 2']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}pt`}
                      />
                    </>
                  )}

                  {/* 前月比テーブル */}
                  {viewMode === 'mom_table' && (
                    <MonthlyTable
                      data={momTableData}
                      decimals={1}
                      helperText="※ 直近10年間の前月比データ（単位: ポイント）"
                    />
                  )}

                  {/* 指数（折れ線グラフ） */}
                  {viewMode === 'index' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'value', color: COLORS.index, name: 'NAB企業信頼感指数', hide: hiddenSeries.has('value') },
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
                <MarketImpactTab indicatorId="au_nab_business_confidence_index" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
