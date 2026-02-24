/**
 * オーストラリア 国際貿易チャートコンポーネント
 *
 * ABS SDMX API (ITGS dataflow) から貿易収支・輸出・輸入データを表示
 *
 * データ:
 * - Balance on goods (貿易収支): B AUD
 * - Exports (輸出): B AUD
 * - Imports (輸入): B AUD
 * - 前月比・前年比
 *
 * データソース:
 * - ABS: International Trade in Goods and Services
 *
 * 発表スケジュール: 月次
 */
import { useState, useMemo } from 'react'
import { Tabs } from 'antd'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabel,
  formatDateLabelJP,
  useMonthlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardBarChart,
  ViewModeButtonGroup,
  ChartControlRow,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'
import { CHART_COLORS } from '../../usa/common/chartConstants'

import type { AuInternationalTradeData } from '../../../../hooks/useDashboardData'
import type { PeriodValue } from '../../../common/PeriodSelector'

interface AuInternationalTradeChartProps {
  data: AuInternationalTradeData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  exports?: number | null
  imports?: number | null
  [key: string]: unknown
}

// データカテゴリ（タブ）
type DataCategory = 'balance' | 'trade'

// ビューモード定義
type BalanceViewMode = 'level_chart' | 'diff_table'
type TradeViewMode = 'level_chart' | 'mom_chart' | 'exports_table' | 'imports_table' | 'yoy_chart'

const BALANCE_VIEW_OPTIONS: { mode: BalanceViewMode; label: string }[] = [
  { mode: 'level_chart', label: '水準' },
  { mode: 'diff_table', label: '前月増減幅（テーブル）' },
]

const TRADE_VIEW_OPTIONS: { mode: TradeViewMode; label: string }[] = [
  { mode: 'level_chart', label: '水準' },
  { mode: 'mom_chart', label: '前月比' },
  { mode: 'exports_table', label: '前月比（輸出・テーブル）' },
  { mode: 'imports_table', label: '前月比（輸入・テーブル）' },
  { mode: 'yoy_chart', label: '前年比' },
]

// カラー設定
const COLORS = {
  balance: CHART_COLORS.primary,
  exports: '#52c41a',  // 緑
  imports: '#ff4d4f',  // 赤
}

export default function AuInternationalTradeChart({ data }: AuInternationalTradeChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(3)
  const [activeTab, setActiveTab] = useState<string>('balance')
  const [balanceViewMode, setBalanceViewMode] = useState<BalanceViewMode>('level_chart')
  const [tradeViewMode, setTradeViewMode] = useState<TradeViewMode>('level_chart')

  // 現在のデータカテゴリ
  const dataCategory: DataCategory = activeTab === 'balance' ? 'balance' : 'trade'

  // 貿易収支データ（すでにB AUDで格納済み）
  const balanceChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []
    const sourceData = data.balance || []
    return sourceData.map(item => ({
      date: item.date,
      value: item.value,
    }))
  }, [data])

  // 貿易収支 前月増減幅データ（テーブル用）
  const balanceDiffData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []
    const sourceData = data.balance_mom_diff || []
    return sourceData.map(item => ({
      date: item.date,
      value: item.value,
    }))
  }, [data])

  // 輸出・輸入データ
  const tradeChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    let exportsSource: { date: string; value: number }[] = []
    let importsSource: { date: string; value: number }[] = []

    if (tradeViewMode === 'mom_chart' || tradeViewMode === 'exports_table' || tradeViewMode === 'imports_table') {
      exportsSource = data.exports_mom || []
      importsSource = data.imports_mom || []
    } else if (tradeViewMode === 'yoy_chart') {
      exportsSource = data.exports_yoy || []
      importsSource = data.imports_yoy || []
    } else {
      exportsSource = data.exports || []
      importsSource = data.imports || []
    }

    // 日付をマージ
    const dateMap = new Map<string, ChartDataPoint>()

    exportsSource.forEach(item => {
      dateMap.set(item.date, {
        date: item.date,
        value: null,
        exports: item.value,
        imports: null,
      })
    })

    importsSource.forEach(item => {
      const existing = dateMap.get(item.date)
      if (existing) {
        existing.imports = item.value
      } else {
        dateMap.set(item.date, {
          date: item.date,
          value: null,
          exports: null,
          imports: item.value,
        })
      }
    })

    return Array.from(dateMap.values())
  }, [data, tradeViewMode])

  // ソートとフィルタリング
  const sortedBalanceData = useSortedData(balanceChartData)
  const sortedBalanceDiffData = useSortedData(balanceDiffData)
  const sortedTradeData = useSortedData(tradeChartData)

  const filteredBalanceData = usePeriodFiltering(sortedBalanceData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const filteredTradeData = usePeriodFiltering(sortedTradeData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ
  const balanceDiffTableData = useMonthlyTableData(sortedBalanceDiffData, (item) => item.value, 10)
  const exportsTableData = useMonthlyTableData(
    sortedTradeData.map(d => ({ date: d.date, value: d.exports ?? null })),
    (item) => item.value,
    10
  )
  const importsTableData = useMonthlyTableData(
    sortedTradeData.map(d => ({ date: d.date, value: d.imports ?? null })),
    (item) => item.value,
    10
  )

  const hasData = (data?.balance?.length ?? 0) > 0 || (data?.exports?.length ?? 0) > 0

  // 最新値を取得
  const latestBalance = data?.latest_balance
  const latestExports = data?.latest_exports
  const latestImports = data?.latest_imports
  const nextRelease = data?.next_release ?? null

  // 最新のMoM/YoYを取得
  const latestExportsMom = useMemo(() => {
    const arr = data?.exports_mom || []
    return arr.length > 0 ? arr[arr.length - 1] : null
  }, [data])
  const latestExportsYoy = useMemo(() => {
    const arr = data?.exports_yoy || []
    return arr.length > 0 ? arr[arr.length - 1] : null
  }, [data])
  const latestImportsMom = useMemo(() => {
    const arr = data?.imports_mom || []
    return arr.length > 0 ? arr[arr.length - 1] : null
  }, [data])
  const latestImportsYoy = useMemo(() => {
    const arr = data?.imports_yoy || []
    return arr.length > 0 ? arr[arr.length - 1] : null
  }, [data])
  const latestBalanceMomDiff = useMemo(() => {
    const arr = data?.balance_mom_diff || []
    return arr.length > 0 ? arr[arr.length - 1] : null
  }, [data])

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="国際貿易" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="国際貿易" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 貿易収支の最新値表示アイテム
  const getBalanceLatestItems = () => {
    const items = []

    if (balanceViewMode === 'level_chart') {
      if (latestBalance?.value !== null && latestBalance?.value !== undefined) {
        items.push({
          label: '貿易収支',
          value: `${latestBalance.value.toFixed(1)} B AUD`,
          color: latestBalance.value >= 0 ? COLORS.balance : '#ef4444',
        })
      }
    } else if (balanceViewMode === 'diff_table') {
      if (latestBalanceMomDiff?.value !== null && latestBalanceMomDiff?.value !== undefined) {
        items.push({
          label: '前月増減幅',
          value: `${latestBalanceMomDiff.value >= 0 ? '+' : ''}${latestBalanceMomDiff.value.toFixed(1)} B AUD`,
          color: latestBalanceMomDiff.value >= 0 ? '#10b981' : '#ef4444',
        })
      }
    }

    return items
  }

  // 輸出・輸入の最新値表示アイテム
  const getTradeLatestItems = () => {
    const items = []

    if (tradeViewMode === 'level_chart') {
      if (latestExports?.value !== null && latestExports?.value !== undefined) {
        items.push({
          label: '輸出',
          value: `${latestExports.value.toFixed(1)} B AUD`,
          color: COLORS.exports,
        })
      }
      if (latestImports?.value !== null && latestImports?.value !== undefined) {
        items.push({
          label: '輸入',
          value: `${latestImports.value.toFixed(1)} B AUD`,
          color: COLORS.imports,
        })
      }
    } else if (tradeViewMode === 'mom_chart' || tradeViewMode === 'exports_table' || tradeViewMode === 'imports_table') {
      if (latestExportsMom?.value !== null && latestExportsMom?.value !== undefined) {
        items.push({
          label: '輸出 前月比',
          value: `${latestExportsMom.value >= 0 ? '+' : ''}${latestExportsMom.value.toFixed(1)}%`,
          color: latestExportsMom.value >= 0 ? '#10b981' : '#ef4444',
        })
      }
      if (latestImportsMom?.value !== null && latestImportsMom?.value !== undefined) {
        items.push({
          label: '輸入 前月比',
          value: `${latestImportsMom.value >= 0 ? '+' : ''}${latestImportsMom.value.toFixed(1)}%`,
          color: latestImportsMom.value >= 0 ? '#10b981' : '#ef4444',
        })
      }
    } else if (tradeViewMode === 'yoy_chart') {
      if (latestExportsYoy?.value !== null && latestExportsYoy?.value !== undefined) {
        items.push({
          label: '輸出 前年比',
          value: `${latestExportsYoy.value >= 0 ? '+' : ''}${latestExportsYoy.value.toFixed(1)}%`,
          color: latestExportsYoy.value >= 0 ? '#10b981' : '#ef4444',
        })
      }
      if (latestImportsYoy?.value !== null && latestImportsYoy?.value !== undefined) {
        items.push({
          label: '輸入 前年比',
          value: `${latestImportsYoy.value >= 0 ? '+' : ''}${latestImportsYoy.value.toFixed(1)}%`,
          color: latestImportsYoy.value >= 0 ? '#10b981' : '#ef4444',
        })
      }
    }

    return items
  }

  // 最新値の日付を取得
  const getLatestDate = () => {
    if (dataCategory === 'balance') {
      if (balanceViewMode === 'diff_table') {
        return latestBalanceMomDiff?.date
      }
      return latestBalance?.date
    } else {
      if (tradeViewMode === 'mom_chart' || tradeViewMode === 'exports_table' || tradeViewMode === 'imports_table') {
        return latestExportsMom?.date
      } else if (tradeViewMode === 'yoy_chart') {
        return latestExportsYoy?.date
      }
      return latestExports?.date
    }
  }

  // 比較用指標ID
  const getCompareIndicatorId = () => {
    if (dataCategory === 'balance') {
      return 'au_international_trade_balance'
    } else {
      return 'au_international_trade_exports'
    }
  }

  return (
    <div id="au-international-trade-chart">
      <ChartContainer
        title="国際貿易"
        showPeriodSelector={false}
        dataSource="Australian Bureau of Statistics"
        sourceUrl="https://www.abs.gov.au/statistics/economy/international-trade/international-trade-goods-and-services-australia"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={dataCategory === 'balance' ? getBalanceLatestItems() : getTradeLatestItems()}
          date={getLatestDate()}
          nextRelease={nextRelease}
        />

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'balance',
              label: '貿易収支',
              children: (
                <>
                  {/* ビューモード切り替え */}
                  <ViewModeButtonGroup
                    options={BALANCE_VIEW_OPTIONS}
                    currentMode={balanceViewMode}
                    onChange={setBalanceViewMode}
                  />

                  {/* 期間セレクタとデータ比較ボタン（テーブル以外で表示） */}
                  {balanceViewMode !== 'diff_table' && (
                    <ChartControlRow
                      selectedPeriod={currentPeriod}
                      onPeriodChange={setCurrentPeriod}
                      indicatorId={getCompareIndicatorId()}
                    />
                  )}

                  {/* チャート/テーブル表示 */}
                  {balanceViewMode === 'diff_table' ? (
                    <MonthlyTable
                      data={balanceDiffTableData}
                      formatValue={(v) => v === null ? '-' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}`}
                      decimals={1}
                    />
                  ) : (
                    <StandardBarChart
                      data={filteredBalanceData}
                      bars={[
                        {
                          dataKey: 'value',
                          name: '貿易収支',
                          color: COLORS.balance,
                        },
                      ]}
                      xAxisFormatter={formatDateLabel}
                      yAxisFormatter={(v) => `${v.toFixed(0)}B`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)} Billion AUD`}
                      tooltipLabelFormatter={formatDateLabelJP}
                      showZeroLine={true}
                      showLegend={false}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'trade',
              label: '輸出・輸入',
              children: (
                <>
                  {/* ビューモード切り替え */}
                  <ViewModeButtonGroup
                    options={TRADE_VIEW_OPTIONS}
                    currentMode={tradeViewMode}
                    onChange={setTradeViewMode}
                  />

                  {/* 期間セレクタとデータ比較ボタン（テーブル以外で表示） */}
                  {tradeViewMode !== 'exports_table' && tradeViewMode !== 'imports_table' && (
                    <ChartControlRow
                      selectedPeriod={currentPeriod}
                      onPeriodChange={setCurrentPeriod}
                      indicatorId={getCompareIndicatorId()}
                    />
                  )}

                  {/* チャート/テーブル表示 */}
                  {tradeViewMode === 'exports_table' ? (
                    <MonthlyTable
                      data={exportsTableData}
                      formatValue={(v) => v === null ? '-' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}`}
                      decimals={1}
                    />
                  ) : tradeViewMode === 'imports_table' ? (
                    <MonthlyTable
                      data={importsTableData}
                      formatValue={(v) => v === null ? '-' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}`}
                      decimals={1}
                    />
                  ) : tradeViewMode === 'mom_chart' || tradeViewMode === 'yoy_chart' ? (
                    <StandardBarChart
                      data={filteredTradeData}
                      bars={[
                        {
                          dataKey: 'exports',
                          name: '輸出',
                          color: COLORS.exports,
                        },
                        {
                          dataKey: 'imports',
                          name: '輸入',
                          color: COLORS.imports,
                        },
                      ]}
                      xAxisFormatter={formatDateLabel}
                      yAxisFormatter={(v) => `${v.toFixed(0)}%`}
                      tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
                      tooltipLabelFormatter={formatDateLabelJP}
                      showZeroLine={true}
                    />
                  ) : (
                    <StandardBarChart
                      data={filteredTradeData}
                      bars={[
                        {
                          dataKey: 'exports',
                          name: '輸出',
                          color: COLORS.exports,
                        },
                        {
                          dataKey: 'imports',
                          name: '輸入',
                          color: COLORS.imports,
                        },
                      ]}
                      xAxisFormatter={formatDateLabel}
                      yAxisFormatter={(v) => `${v.toFixed(0)}B`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)} Billion AUD`}
                      tooltipLabelFormatter={formatDateLabelJP}
                      showZeroLine={false}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="au_international_trade" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
