/**
 * 中国 社会融資総量（Aggregate Financing to the Real Economy）チャートコンポーネント
 *
 * ビューモード:
 * - フロー:       月次フロー（百億元）棒グラフ
 * - 残高:         月末残高（兆元）折れ線
 * - 残高 前年比:  前年比（%）折れ線
 *
 * データソース: 中国人民銀行（PBOC）
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
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  ViewModeButtonGroup,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { CnAggregateFinancingData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface CnAggregateFinancingChartProps {
  data: CnAggregateFinancingData | null
}

// フロー / 残高 / 残高前年比 の切替
type ViewMode = 'flow' | 'stock' | 'stock_yoy'
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'flow',      label: 'フロー' },
  { mode: 'stock',     label: '残高' },
  { mode: 'stock_yoy', label: '残高前年比' },
]

const COLOR_FLOW  = '#3b82f6'  // 青
const COLOR_STOCK = '#10b981'  // 緑
const COLOR_YOY   = '#f59e0b'  // オレンジ（残高前年比）

// =============================================================================
// 日付フォーマット
// =============================================================================

const formatDateLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}/${month}`
}

const formatDateFull = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}年${parseInt(month)}月`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CnAggregateFinancingChart({ data }: CnAggregateFinancingChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('flow')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    flow:      5,
    stock:     10,
    stock_yoy: 10,
  })

  const sortedData = useSortedData(data?.data ?? [])

  // ビューモードに応じてデータをフィルタリング（Null値のみのレコードを除外）
  const filteredBase = useMemo(() => {
    if (viewMode === 'flow')      return sortedData.filter(d => d.flow  != null)
    if (viewMode === 'stock')     return sortedData.filter(d => d.stock != null)
    if (viewMode === 'stock_yoy') return sortedData.filter(d => d.yoy   != null)
    return sortedData
  }, [sortedData, viewMode])

  const filteredData = usePeriodFiltering(filteredBase, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="社会融資総量" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="社会融資総量" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値取得（各系列で最後の非null値）
  const latestWithFlow  = [...sortedData].reverse().find(d => d.flow  != null)
  const latestWithStock = [...sortedData].reverse().find(d => d.stock != null)
  const latestWithYoy   = [...sortedData].reverse().find(d => d.yoy   != null)

  // SimpleLatestValueBox 用の値・ラベル・色
  const latestValue =
    viewMode === 'flow'      ? (latestWithFlow?.flow   ?? null)
    : viewMode === 'stock'   ? (latestWithStock?.stock ?? null)
    : (latestWithYoy?.yoy ?? null)

  const latestDate =
    viewMode === 'flow'      ? latestWithFlow?.date
    : viewMode === 'stock'   ? latestWithStock?.date
    : latestWithYoy?.date

  const latestLabel =
    viewMode === 'flow'      ? '社会融資総量（フロー）'
    : viewMode === 'stock'   ? '社会融資総量（残高）'
    : '社会融資総量 残高（前年比）'

  const latestUnit =
    viewMode === 'flow'      ? '百億元'
    : viewMode === 'stock'   ? '兆元'
    : '%'

  const latestDecimals =
    viewMode === 'flow'      ? 0
    : viewMode === 'stock'   ? 2
    : 1

  const latestColor =
    viewMode === 'flow'      ? COLOR_FLOW
    : viewMode === 'stock'   ? COLOR_STOCK
    : COLOR_YOY

  return (
    <div id="aggregate-financing">
      <ChartContainer
        title="社会融資総量"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="中国人民銀行（PBOC）"
        sourceUrl="https://camlmac.pbc.gov.cn/diaochatongjisi/116219/116319/index.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={latestLabel}
          value={latestValue}
          date={latestDate}
          unit={latestUnit}
          decimals={latestDecimals}
          valueColor={latestColor}
          dateFormatter={formatDateFull}
          nextRelease={data.next_release ?? null}
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
                  {/* ビューモード切替 + データ比較ボタン（同一行） */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      options={VIEW_MODE_OPTIONS}
                      currentMode={viewMode}
                      onChange={setViewMode}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=cn_aggregate_financing_to_the_real_economy', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 期間選択 */}
                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                  {/* フロー: 棒グラフ */}
                  {viewMode === 'flow' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'flow', color: COLOR_FLOW, name: 'フロー（百億元）' },
                      ]}
                      yAxisFormatter={(v) => `${(v / 100).toFixed(0)}兆`}
                      yDomain={['dataMin - 2000', 'dataMax + 2000']}
                      xAxisFormatter={formatDateLabel}
                      tooltipLabelFormatter={formatDateFull}
                      tooltipValueFormatter={(v) => `${v.toFixed(0)} 百億元`}
                      showZeroLine={true}
                      showLegend={false}
                    />
                  )}

                  {/* 残高: 折れ線 */}
                  {viewMode === 'stock' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'stock', color: COLOR_STOCK, name: '残高（兆元）' },
                      ]}
                      yAxisFormatter={(v) => `${v.toFixed(0)}兆`}
                      yDomain={['dataMin - 5', 'dataMax + 5']}
                      xAxisFormatter={formatDateLabel}
                      tooltipLabelFormatter={formatDateFull}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)} 兆元`}
                      showZeroLine={false}
                      showLegend={false}
                    />
                  )}

                  {/* 残高前年比: 折れ線 */}
                  {viewMode === 'stock_yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'yoy', color: COLOR_YOY, name: '残高前年比（%）' },
                      ]}
                      yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                      yDomain={['dataMin - 1', 'dataMax + 1']}
                      xAxisFormatter={formatDateLabel}
                      tooltipLabelFormatter={formatDateFull}
                      tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
                      showZeroLine={true}
                      showLegend={false}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="cn_aggregate_financing_to_the_real_economy" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
