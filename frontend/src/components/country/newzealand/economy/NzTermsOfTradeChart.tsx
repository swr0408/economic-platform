/**
 * NZ 交易条件（Terms of Trade）チャートコンポーネント
 *
 * データ:
 * - terms_of_trade_qoq: 交易条件 前期比（%）
 * - export_price_qoq:   輸出価格指数 前期比（%）
 * - import_price_qoq:   輸入価格指数 前期比（%）
 * - terms_of_trade_yoy: 交易条件 前年比（%）
 * - export_price_yoy:   輸出価格指数 前年比（%）
 * - import_price_yoy:   輸入価格指数 前年比（%）
 *
 * データソース:
 * - Stats NZ Overseas Trade Indexes (Prices) - Table 1.01
 * - https://www.stats.govt.nz/
 *
 * FMPマッピング:
 * - Terms of Trade QoQ (econalpha_id: nz_terms_of_trade)
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
  useViewModePeriodManagement,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
  StandardBarChart,
  ViewModeButtonGroup,
  LatestValueBox,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { NzTermsOfTradeData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface NzTermsOfTradeChartProps {
  data: NzTermsOfTradeData | null
}

type ViewMode = 'qoq' | 'yoy'

// カラー設定
const COLOR_TOT = '#0ea5e9'      // 交易条件
const COLOR_EXPORT = '#16a34a'   // 輸出価格
const COLOR_IMPORT = '#dc2626'   // 輸入価格

// =============================================================================
// 日付フォーマット
// =============================================================================

const formatQuarterLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  const monthNum = parseInt(month, 10)
  const quarter = Math.ceil(monthNum / 3)
  return `${year}/Q${quarter}`
}

const formatQuarterLabelJP = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  const monthNum = parseInt(month, 10)
  const quarter = Math.ceil(monthNum / 3)
  return `${year}年 Q${quarter}`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function NzTermsOfTradeChart({ data }: NzTermsOfTradeChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('qoq')

  // QoQ/YoYで期間を別管理（前年比は2023 Q3以降）
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    qoq: 20,
    yoy: 20,
  })

  // 輸出価格・輸入価格は初期非表示
  const { hiddenSeries, handleLegendClick } = useHiddenSeries(['export', 'import'])

  // データを日付昇順にソート
  const sortedData = useSortedData(data?.data ?? [])

  // 期間フィルタリング
  const defaultStartYear = viewMode === 'yoy' ? 2023 : 2020
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear,
  })

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="交易条件" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="交易条件" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = sortedData[sortedData.length - 1]
  const totQoQ = latest?.terms_of_trade_qoq ?? null
  const totYoY = latest?.terms_of_trade_yoy ?? null


  return (
    <div id="nz-terms-of-trade">
      <ChartContainer
        title="交易条件"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="Stats NZ"
        sourceUrl="https://www.stats.govt.nz/information-releases/?filters=Balance%20of%20payments&topicFiltersID=635"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '交易条件 (前期比)',
              value: totQoQ,
              color: totQoQ !== null && totQoQ >= 0 ? COLOR_EXPORT : COLOR_IMPORT,
              format: 'percent',
            },
            {
              label: '交易条件 (前年比)',
              value: totYoY,
              color: totYoY !== null && totYoY >= 0 ? COLOR_EXPORT : COLOR_IMPORT,
              format: 'percent',
            },
            {
              label: '輸出価格 (前期比)',
              value: latest?.export_price_qoq ?? null,
              color: COLOR_EXPORT,
              format: 'percent',
            },
            {
              label: '輸入価格 (前期比)',
              value: latest?.import_price_qoq ?? null,
              color: COLOR_IMPORT,
              format: 'percent',
            },
          ]}
          date={latest?.date}
          dateFormatter={formatQuarterLabelJP}
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
                        { mode: 'qoq', label: '前期比' },
                        { mode: 'yoy', label: '前年比' },
                      ]}
                      currentMode={viewMode}
                      onChange={(mode) => setViewMode(mode as ViewMode)}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=nz_terms_of_trade', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 下段: 期間選択 */}
                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                  {/* 前期比: 棒グラフ（3系列） */}
                  {viewMode === 'qoq' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'terms_of_trade_qoq', color: COLOR_TOT, name: '交易条件' },
                        { dataKey: 'export_price_qoq', color: COLOR_EXPORT, name: '輸出価格', hide: hiddenSeries.has('export') },
                        { dataKey: 'import_price_qoq', color: COLOR_IMPORT, name: '輸入価格', hide: hiddenSeries.has('import') },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      yDomain={['dataMin - 2', 'dataMax + 2']}
                      xAxisFormatter={formatQuarterLabel}
                      tooltipLabelFormatter={formatQuarterLabelJP}
                      tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                      onLegendClick={(dataKey) => {
                        if (dataKey === 'export_price_qoq') handleLegendClick('export')
                        else if (dataKey === 'import_price_qoq') handleLegendClick('import')
                        else handleLegendClick(dataKey)
                      }}
                    />
                  )}

                  {/* 前年比: 折れ線グラフ（3系列） */}
                  {viewMode === 'yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'terms_of_trade_yoy', color: COLOR_TOT, name: '交易条件' },
                        { dataKey: 'export_price_yoy', color: COLOR_EXPORT, name: '輸出価格', hide: hiddenSeries.has('export') },
                        { dataKey: 'import_price_yoy', color: COLOR_IMPORT, name: '輸入価格', hide: hiddenSeries.has('import') },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      showZeroLine={true}
                      xAxisFormatter={formatQuarterLabel}
                      tooltipLabelFormatter={formatQuarterLabelJP}
                      tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                      onLegendClick={(dataKey) => {
                        if (dataKey === 'export_price_yoy') handleLegendClick('export')
                        else if (dataKey === 'import_price_yoy') handleLegendClick('import')
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
                <MarketImpactTab indicatorId="nz_terms_of_trade" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
