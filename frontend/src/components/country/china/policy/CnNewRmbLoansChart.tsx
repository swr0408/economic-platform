/**
 * 中国 新規人民元貸出（New RMB Loans）チャートコンポーネント
 *
 * ビューモード:
 * - フロー:       月次新増人民元貸出（亿元）棒グラフ
 * - 残高:         全項貸款残高（亿元）折れ線
 * - 残高 前年比:  前年比（%）折れ線
 *
 * データソース: 中国人民銀行（PBOC）
 *
 * FMPマッピング:
 * - New Yuan Loans / New Loans (econalpha_id: cn_new_rmb_loans)
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

import type { CnNewRmbLoansData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface CnNewRmbLoansChartProps {
  data: CnNewRmbLoansData | null
}

type ViewMode = 'flow' | 'stock' | 'stock_yoy'
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'flow',      label: 'フロー' },
  { mode: 'stock',     label: '残高' },
  { mode: 'stock_yoy', label: '残高前年比' },
]

const COLOR_FLOW  = '#ef4444'  // 赤
const COLOR_STOCK = '#3b82f6'  // 青
const COLOR_YOY   = '#f59e0b'  // オレンジ

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

export default function CnNewRmbLoansChart({ data }: CnNewRmbLoansChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('flow')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    flow:      5,
    stock:     10,
    stock_yoy: 10,
  })

  const sortedData = useSortedData(data?.data ?? [])

  const filteredBase = useMemo(() => {
    if (viewMode === 'flow')      return sortedData.filter(d => d.flow != null)
    if (viewMode === 'stock')     return sortedData.filter(d => d.stock != null)
    if (viewMode === 'stock_yoy') return sortedData.filter(d => d.stock_yoy != null)
    return sortedData
  }, [sortedData, viewMode])

  const filteredData = usePeriodFiltering(filteredBase, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="新規人民元貸出" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="新規人民元貸出" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latestWithFlow  = [...sortedData].reverse().find(d => d.flow != null)
  const latestWithStock = [...sortedData].reverse().find(d => d.stock != null)
  const latestWithYoy   = [...sortedData].reverse().find(d => d.stock_yoy != null)

  const latestValue =
    viewMode === 'flow'      ? (latestWithFlow?.flow ?? null)
    : viewMode === 'stock'   ? (latestWithStock?.stock ?? null)
    : (latestWithYoy?.stock_yoy ?? null)

  const latestDate =
    viewMode === 'flow'      ? latestWithFlow?.date
    : viewMode === 'stock'   ? latestWithStock?.date
    : latestWithYoy?.date

  const latestLabel =
    viewMode === 'flow'      ? '新規人民元貸出（フロー）'
    : viewMode === 'stock'   ? '人民元貸出残高'
    : '人民元貸出 残高（前年比）'

  const latestUnit =
    viewMode === 'flow'      ? '亿元'
    : viewMode === 'stock'   ? '亿元'
    : '%'

  const latestDecimals =
    viewMode === 'flow'      ? 0
    : viewMode === 'stock'   ? 0
    : 2

  const latestColor =
    viewMode === 'flow'      ? COLOR_FLOW
    : viewMode === 'stock'   ? COLOR_STOCK
    : COLOR_YOY

  return (
    <div id="new-rmb-loans">
      <ChartContainer
        title="新規人民元貸出"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="中国人民銀行（PBOC）"
        sourceUrl="https://www.pbc.gov.cn/en/3688247/3688975/index.html"
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
                  {/* ビューモード切替 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      options={VIEW_MODE_OPTIONS}
                      currentMode={viewMode}
                      onChange={setViewMode}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=cn_new_rmb_loans', '_blank')}
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
                        { dataKey: 'flow', color: COLOR_FLOW, name: '新増人民元貸出（亿元）' },
                      ]}
                      yAxisFormatter={(v) => `${(v / 10000).toFixed(1)}万亿`}
                      yDomain={['dataMin - 5000', 'dataMax + 5000']}
                      xAxisFormatter={formatDateLabel}
                      tooltipLabelFormatter={formatDateFull}
                      tooltipValueFormatter={(v) => `${v.toLocaleString()} 亿元`}
                      showZeroLine={true}
                      showLegend={false}
                    />
                  )}

                  {/* 残高: 折れ線 */}
                  {viewMode === 'stock' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'stock', color: COLOR_STOCK, name: '貸出残高（亿元）' },
                      ]}
                      yAxisFormatter={(v) => `${(v / 10000).toFixed(0)}万亿`}
                      yDomain={['dataMin - 50000', 'dataMax + 50000']}
                      xAxisFormatter={formatDateLabel}
                      tooltipLabelFormatter={formatDateFull}
                      tooltipValueFormatter={(v) => `${v.toLocaleString()} 亿元`}
                      showZeroLine={false}
                      showLegend={false}
                    />
                  )}

                  {/* 残高前年比: 折れ線 */}
                  {viewMode === 'stock_yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'stock_yoy', color: COLOR_YOY, name: '残高前年比（%）' },
                      ]}
                      yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                      yDomain={['dataMin - 1', 'dataMax + 1']}
                      xAxisFormatter={formatDateLabel}
                      tooltipLabelFormatter={formatDateFull}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
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
                <MarketImpactTab indicatorId="cn_new_rmb_loans" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
