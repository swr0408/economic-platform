/**
 * EU国際貿易チャートコンポーネント
 *
 * Eurostat APIから貿易収支・輸出・輸入データを取得し、表示
 *
 * データ:
 * - Balance of Trade (貿易収支): Billion EUR
 * - Exports (輸出): Million EUR
 * - Imports (輸入): Million EUR
 * - 前月比・前年比
 *
 * データソース:
 * - Eurostat - External Trade (ei_etea_m)
 *
 * 発表スケジュール:
 * - 月次（不定期）
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

import type { EUInternationalTradeData } from '../../../../hooks/useDashboardData'
import type { PeriodValue } from '../../../common/PeriodSelector'

interface EUInternationalTradeChartProps {
  data: EUInternationalTradeData | null
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

// 貿易収支: データ種別
type BalanceDataKind = 'level' | 'diff'
const BALANCE_DATA_KIND_OPTIONS: { mode: BalanceDataKind; label: string }[] = [
  { mode: 'level', label: '水準' },
  { mode: 'diff', label: '前月増減幅' },
]

type BalanceDisplayMode = 'chart' | 'heatmap'
const BALANCE_DISPLAY_MODE_OPTIONS: { mode: BalanceDisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// 輸出・輸入: データ種別
type TradeDataKind = 'level' | 'mom' | 'yoy'
const TRADE_DATA_KIND_OPTIONS: { mode: TradeDataKind; label: string }[] = [
  { mode: 'level', label: '水準' },
  { mode: 'mom', label: '前月比' },
  { mode: 'yoy', label: '前年比' },
]

type TradeDisplayMode = 'chart' | 'heatmap'
const TRADE_DISPLAY_MODE_OPTIONS: { mode: TradeDisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

type TradeTableType = 'exports' | 'imports'
const TRADE_TABLE_TYPE_OPTIONS: { type: TradeTableType; label: string }[] = [
  { type: 'exports', label: '輸出' },
  { type: 'imports', label: '輸入' },
]

// カラー設定
const COLORS = {
  balance: CHART_COLORS.primary,
  exports: '#52c41a',  // 緑
  imports: '#ff4d4f',  // 赤
}

export default function EUInternationalTradeChart({ data }: EUInternationalTradeChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(3)
  const [activeTab, setActiveTab] = useState<string>('balance')
  const [balanceDataKind, setBalanceDataKind] = useState<BalanceDataKind>('level')
  const [balanceDisplayMode, setBalanceDisplayMode] = useState<BalanceDisplayMode>('chart')
  const [tradeDataKind, setTradeDataKind] = useState<TradeDataKind>('level')
  const [tradeDisplayMode, setTradeDisplayMode] = useState<TradeDisplayMode>('chart')
  const [tradeTableType, setTradeTableType] = useState<TradeTableType>('exports')

  // 現在のデータカテゴリ
  const dataCategory: DataCategory = activeTab === 'balance' ? 'balance' : 'trade'

  // 貿易収支データ（Billion EUR に変換）
  const balanceChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    // 水準モード: balance配列を使用
    const sourceData = data.balance || []

    return sourceData.map(item => ({
      date: item.date,
      value: item.value / 1000,  // Million -> Billion変換
    }))
  }, [data])

  // 貿易収支 前月増減幅データ（テーブル用）
  const balanceDiffData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const sourceData = data.balance_mom_diff || []

    return sourceData.map(item => ({
      date: item.date,
      value: item.value / 1000,  // Million -> Billion変換
    }))
  }, [data])

  // 輸出・輸入データ
  const tradeChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    let exportsSource: { date: string; value: number }[] = []
    let importsSource: { date: string; value: number }[] = []
    const isLevelChart = tradeDataKind === 'level'

    if (tradeDataKind === 'mom') {
      exportsSource = data.exports_mom || []
      importsSource = data.imports_mom || []
    } else if (tradeDataKind === 'yoy') {
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
        // 水準チャートの場合はBillion変換
        exports: isLevelChart ? item.value / 1000 : item.value,
        imports: null,
      })
    })

    importsSource.forEach(item => {
      const existing = dateMap.get(item.date)
      if (existing) {
        existing.imports = isLevelChart ? item.value / 1000 : item.value
      } else {
        dateMap.set(item.date, {
          date: item.date,
          value: null,
          exports: null,
          imports: isLevelChart ? item.value / 1000 : item.value,
        })
      }
    })

    return Array.from(dateMap.values())
  }, [data, tradeDataKind])

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

  // テーブル用データ（前月増減幅）
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
  const latestBalanceMomDiff = data?.latest_balance_mom_diff
  const latestExportsMom = data?.latest_exports_mom
  const latestExportsYoy = data?.latest_exports_yoy
  const latestImportsMom = data?.latest_imports_mom
  const latestImportsYoy = data?.latest_imports_yoy
  const nextRelease = data?.next_release ?? null

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="国際貿易（ユーロ圏）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="国際貿易（ユーロ圏）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 貿易収支の最新値表示アイテム
  const getBalanceLatestItems = () => {
    const items = []

    if (balanceDataKind === 'level') {
      if (latestBalance?.value !== null && latestBalance?.value !== undefined) {
        items.push({
          label: '貿易収支',
          value: `${(latestBalance.value / 1000).toFixed(1)} B EUR`,
          color: latestBalance.value >= 0 ? COLORS.balance : '#ef4444',
        })
      }
    } else if (balanceDataKind === 'diff') {
      if (latestBalanceMomDiff?.value !== null && latestBalanceMomDiff?.value !== undefined) {
        const diffInBillion = latestBalanceMomDiff.value / 1000
        items.push({
          label: '前月増減幅',
          value: `${diffInBillion >= 0 ? '+' : ''}${diffInBillion.toFixed(1)} B EUR`,
          color: diffInBillion >= 0 ? '#10b981' : '#ef4444',
        })
      }
    }

    return items
  }

  // 輸出・輸入の最新値表示アイテム
  const getTradeLatestItems = () => {
    const items = []

    if (tradeDataKind === 'level') {
      if (latestExports?.value !== null && latestExports?.value !== undefined) {
        items.push({
          label: '輸出',
          value: `${(latestExports.value / 1000).toFixed(1)} B EUR`,
          color: COLORS.exports,
        })
      }
      if (latestImports?.value !== null && latestImports?.value !== undefined) {
        items.push({
          label: '輸入',
          value: `${(latestImports.value / 1000).toFixed(1)} B EUR`,
          color: COLORS.imports,
        })
      }
    } else if (tradeDataKind === 'mom') {
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
    } else if (tradeDataKind === 'yoy') {
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
      if (balanceDataKind === 'diff') {
        return latestBalanceMomDiff?.date
      }
      return latestBalance?.date
    } else {
      if (tradeDataKind === 'mom') {
        return latestExportsMom?.date
      } else if (tradeDataKind === 'yoy') {
        return latestExportsYoy?.date
      }
      return latestExports?.date
    }
  }

  // 比較用指標ID
  const getCompareIndicatorId = () => {
    if (dataCategory === 'balance') {
      return 'eu_international_trade_balance'
    } else {
      return 'eu_international_trade_exports'
    }
  }

  return (
    <div id="eu-international-trade-chart">
      <ChartContainer
        title="国際貿易（ユーロ圏）"
        showPeriodSelector={false}
        dataSource="Eurostat"
        sourceUrl="https://ec.europa.eu/eurostat/web/main/news/euro-indicators?p_p_id=estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageNumber=1&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_action=search&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageSize=11&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_text=balance+of+Trade&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_collection=CAT_PREREL&p_auth=rcRz7IFX&text=international+trade+"
        handbookId="trade-balance"
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
                  {/* 上段: データ種別 */}
                  <div style={{ marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      options={BALANCE_DATA_KIND_OPTIONS}
                      currentMode={balanceDataKind}
                      onChange={setBalanceDataKind}
                    />
                  </div>

                  {/* 下段: 表示形式（diffのときのみ） */}
                  {balanceDataKind === 'diff' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={BALANCE_DISPLAY_MODE_OPTIONS} currentMode={balanceDisplayMode} onChange={setBalanceDisplayMode} />
                    </div>
                  )}

                  {/* 期間セレクタとデータ比較ボタン（ヒートマップ以外で表示） */}
                  {!(balanceDataKind === 'diff' && balanceDisplayMode === 'heatmap') && (
                    <ChartControlRow
                      selectedPeriod={currentPeriod}
                      onPeriodChange={setCurrentPeriod}
                      indicatorId={getCompareIndicatorId()}
                    />
                  )}

                  {/* テーブル表示 */}
                  {balanceDataKind === 'diff' && balanceDisplayMode === 'heatmap' && (
                    <MonthlyTable
                      data={balanceDiffTableData}
                      formatValue={(v) => v === null ? '-' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}`}
                      decimals={1}
                    />
                  )}

                  {/* チャート表示 */}
                  {balanceDataKind === 'level' && (
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
                      tooltipValueFormatter={(v) => `${v.toFixed(2)} Billion EUR`}
                      tooltipLabelFormatter={formatDateLabelJP}
                      showZeroLine={true}
                      showLegend={false}
                    />
                  )}

                  {balanceDataKind === 'diff' && balanceDisplayMode === 'chart' && (
                    <StandardBarChart
                      data={filteredBalanceData}
                      bars={[
                        {
                          dataKey: 'value',
                          name: '前月増減幅',
                          color: COLORS.balance,
                        },
                      ]}
                      xAxisFormatter={formatDateLabel}
                      yAxisFormatter={(v) => `${v.toFixed(0)}B`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)} Billion EUR`}
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
                  {/* 上段: データ種別 */}
                  <div style={{ marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      options={TRADE_DATA_KIND_OPTIONS}
                      currentMode={tradeDataKind}
                      onChange={setTradeDataKind}
                    />
                  </div>

                  {/* 下段: 表示形式（momのときのみ） */}
                  {tradeDataKind === 'mom' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={TRADE_DISPLAY_MODE_OPTIONS} currentMode={tradeDisplayMode} onChange={setTradeDisplayMode} />
                    </div>
                  )}

                  {/* 期間セレクタとデータ比較ボタン（ヒートマップ以外で表示） */}
                  {!(tradeDataKind === 'mom' && tradeDisplayMode === 'heatmap') && (
                    <ChartControlRow
                      selectedPeriod={currentPeriod}
                      onPeriodChange={setCurrentPeriod}
                      indicatorId={getCompareIndicatorId()}
                    />
                  )}

                  {/* テーブル表示（前月比ヒートマップ） */}
                  {tradeDataKind === 'mom' && tradeDisplayMode === 'heatmap' && (
                    <>
                      <div style={{ marginBottom: 8 }}>
                        {TRADE_TABLE_TYPE_OPTIONS.map(opt => (
                          <button
                            key={opt.type}
                            onClick={() => setTradeTableType(opt.type)}
                            style={{
                              marginRight: 8,
                              padding: '4px 12px',
                              border: tradeTableType === opt.type ? '1px solid #1890ff' : '1px solid #d9d9d9',
                              borderRadius: 4,
                              background: tradeTableType === opt.type ? '#1890ff' : 'transparent',
                              color: tradeTableType === opt.type ? '#fff' : 'inherit',
                              cursor: 'pointer',
                            }}
                          >
                            {opt.label}
                          </button>
                        ))}
                      </div>
                      <MonthlyTable
                        data={tradeTableType === 'exports' ? exportsTableData : importsTableData}
                        formatValue={(v) => v === null ? '-' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}`}
                        decimals={1}
                      />
                    </>
                  )}

                  {/* チャート表示 */}
                  {tradeDataKind === 'mom' && tradeDisplayMode === 'chart' && (
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
                  )}

                  {tradeDataKind === 'yoy' && (
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
                  )}

                  {tradeDataKind === 'level' && (
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
                      tooltipValueFormatter={(v) => `${v.toFixed(2)} Billion EUR`}
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
              children: <MarketImpactTab indicatorId="eu_international_trade" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
