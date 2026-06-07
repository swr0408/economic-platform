/**
 * NZ 乳製品価格（GDT）チャートコンポーネント
 *
 * データ:
 * - value: GDT価格指数変化率（%）
 *
 * データソース:
 * - GlobalDairyTrade
 * - https://www.globaldairytrade.info/
 *
 * FMPマッピング:
 * - GlobalDairyTrade Price Index (econalpha_id: nz_global_dairy_trade)
 */
import { useState } from 'react'
import { Tabs } from 'antd'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { NzGlobalDairyTradeData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface NzGlobalDairyTradeChartProps {
  data: NzGlobalDairyTradeData | null
}

// カラー設定
const COLOR_POSITIVE = '#16a34a'  // 正値
const COLOR_NEGATIVE = '#dc2626'  // 負値
const COLOR = '#0891b2'           // 棒グラフ（統一色）

// =============================================================================
// 日付フォーマット
// =============================================================================

const formatDateLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month, day] = dateStr.split('-')
  return `${year}/${month}/${day}`
}

const formatDateLabelJP = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month, day] = dateStr.split('-')
  return `${year}年${parseInt(month, 10)}月${parseInt(day, 10)}日`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function NzGlobalDairyTradeChart({ data }: NzGlobalDairyTradeChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)

  // データを日付昇順にソート
  const sortedData = useSortedData(data?.data ?? [])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2022,
  })

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="乳製品価格（GDT）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="乳製品価格（GDT）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = sortedData[sortedData.length - 1]
  const latestValue = latest?.value ?? null
  const valueColor = latestValue !== null
    ? (latestValue >= 0 ? COLOR_POSITIVE : COLOR_NEGATIVE)
    : COLOR

  return (
    <div id="nz-global-dairy-trade">
      <ChartContainer
        title="乳製品価格（GDT）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="GlobalDairyTrade"
        sourceUrl="https://www.globaldairytrade.info/en/product-results/"
        handbookId="nz-global-dairy-trade"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="GDT価格指数"
          value={latestValue}
          unit="%"
          valueColor={valueColor}
          date={latest?.date}
          dateFormatter={formatDateLabelJP}
          nextRelease={data?.next_release ?? undefined}
          decimals={2}
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
                  {/* 期間選択 */}
                  <div style={{ display: 'flex', justifyContent: 'flex-start', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                  </div>

                  {/* 棒グラフ */}
                  <StandardBarChart
                    data={filteredData}
                    bars={[
                      { dataKey: 'value', color: COLOR, name: 'GDT価格指数' },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    showZeroLine={true}
                    xAxisFormatter={formatDateLabel}
                    tooltipLabelFormatter={formatDateLabelJP}
                    tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
                  />
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="nz_global_dairy_trade" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
