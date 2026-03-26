/**
 * NZ 貿易収支（Trade Balance）チャートコンポーネント
 *
 * データ:
 * - exports: 輸出額（10億NZD）
 * - imports: 輸入額（10億NZD）
 * - balance: 貿易収支（10億NZD、輸出-輸入）
 *
 * データソース:
 * - Stats NZ Overseas Merchandise Trade - Table 1.01
 * - https://www.stats.govt.nz/
 *
 * FMPマッピング:
 * - Balance of Trade (econalpha_id: nz_trade_balance)
 */
import { useState } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import type { PeriodType } from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
  StandardBarChart,
  ViewModeButtonGroup,
  LatestValueBox,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { NzTradeBalanceData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface NzTradeBalanceChartProps {
  data: NzTradeBalanceData | null
}

type ViewMode = 'balance' | 'exports_imports'

// カラー設定
const COLOR_BALANCE = '#0ea5e9'   // 貿易収支
const COLOR_EXPORTS = '#16a34a'   // 輸出
const COLOR_IMPORTS = '#dc2626'   // 輸入

// =============================================================================
// 日付フォーマット
// =============================================================================

const formatMonthLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}/${month}`
}

const formatMonthLabelJP = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}年${parseInt(month, 10)}月`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function NzTradeBalanceChart({ data }: NzTradeBalanceChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('balance')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(10)

  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データを日付昇順にソート
  const sortedData = useSortedData(data?.data ?? [])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2019,
  })

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="貿易収支" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="貿易収支" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = sortedData[sortedData.length - 1]
  const balance = latest?.balance ?? null
  const exports_ = latest?.exports ?? null
  const imports_ = latest?.imports ?? null

  return (
    <div id="nz-trade-balance">
      <ChartContainer
        title="貿易収支"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="Stats NZ"
        sourceUrl="https://www.stats.govt.nz/information-releases/?filters=Balance%20of%20payments&topicFiltersID=635"
        handbookId="trade-balance"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '貿易収支',
              value: balance,
              color: balance !== null && balance >= 0 ? COLOR_EXPORTS : COLOR_IMPORTS,
              format: 'number',
              decimals: 2,
              unit: '十億NZD',
            },
            {
              label: '輸出',
              value: exports_,
              color: COLOR_EXPORTS,
              format: 'number',
              decimals: 2,
              unit: '十億NZD',
            },
            {
              label: '輸入',
              value: imports_,
              color: COLOR_IMPORTS,
              format: 'number',
              decimals: 2,
              unit: '十億NZD',
            },
          ]}
          date={latest?.date}
          dateFormatter={formatMonthLabelJP}
          nextRelease={data?.next_release ? { date: data.next_release.date } : undefined}
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
                  {/* 上段: ビューモード切替 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      options={[
                        { mode: 'balance', label: '貿易収支' },
                        { mode: 'exports_imports', label: '輸出入' },
                      ]}
                      currentMode={viewMode}
                      onChange={(mode) => setViewMode(mode as ViewMode)}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=nz_trade_balance', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 下段: 期間選択 */}
                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                  {/* 貿易収支: 棒グラフ */}
                  {viewMode === 'balance' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'balance', color: COLOR_BALANCE, name: '貿易収支' },
                      ]}
                      yAxisFormatter={(v) => `${v.toFixed(1)}`}
                      yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                      xAxisFormatter={formatMonthLabel}
                      tooltipLabelFormatter={formatMonthLabelJP}
                      tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}十億NZD`}
                    />
                  )}

                  {/* 輸出入: 折れ線グラフ（2系列） */}
                  {viewMode === 'exports_imports' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'exports', color: COLOR_EXPORTS, name: '輸出', hide: hiddenSeries.has('exports') },
                        { dataKey: 'imports', color: COLOR_IMPORTS, name: '輸入', hide: hiddenSeries.has('imports') },
                      ]}
                      yAxisFormatter={(v) => `${v.toFixed(1)}`}
                      xAxisFormatter={formatMonthLabel}
                      tooltipLabelFormatter={formatMonthLabelJP}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}十億NZD`}
                      yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                      onLegendClick={(dataKey) => {
                        if (dataKey === 'exports') handleLegendClick('exports')
                        else if (dataKey === 'imports') handleLegendClick('imports')
                        else handleLegendClick(dataKey)
                      }}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="nz_trade_balance" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
