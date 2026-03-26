/**
 * 中国 貿易収支チャートコンポーネント
 *
 * 3系列: 貿易収支 + 輸出 + 輸入（億USD）
 * + 前年比（%）・前月増減幅（億USD）
 *
 * タブ構成:
 * - 貿易収支: 水準 | 前月増減幅 (チャート / ヒートマップ)
 * - 輸出・輸入: 水準 | 前月増減幅 | 前年比 (チャート / ヒートマップ)
 * - マーケットインパクト
 *
 * データソース: General Administration of Customs / NBS
 *
 * FMPマッピング: cn_trade_balance
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabel,
  formatDateLabelJP,
  useMonthlyTableData,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardBarChart,
  StandardLineChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'
import { CHART_COLORS } from '../../usa/common/chartConstants'

import type { CnTradeBalanceData } from '../../../../hooks/useDashboardData'
import type { PeriodValue } from '../../../common/PeriodSelector'

interface Props {
  data: CnTradeBalanceData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  exports?: number | null
  imports?: number | null
  [key: string]: unknown
}

// 貿易収支: データ種別
type BalanceDataKind = 'level' | 'diff'

const BALANCE_DATA_KIND_OPTIONS: { mode: BalanceDataKind; label: string }[] = [
  { mode: 'level', label: '水準' },
  { mode: 'diff', label: '前月増減幅' },
]

// 貿易収支: 表示形式（diff時）
type BalanceDisplayMode = 'chart' | 'heatmap'

const BALANCE_DISPLAY_MODE_OPTIONS: { mode: BalanceDisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// 輸出入: データ種別
type TradeDataKind = 'level' | 'mom' | 'yoy'

const TRADE_DATA_KIND_OPTIONS: { mode: TradeDataKind; label: string }[] = [
  { mode: 'level', label: '水準' },
  { mode: 'mom', label: '前月増減幅' },
  { mode: 'yoy', label: '前年比' },
]

// 輸出入: テーブルデータ種別
type TradeTableType = 'exports' | 'imports'

const TRADE_TABLE_TYPE_OPTIONS: { type: TradeTableType; label: string }[] = [
  { type: 'exports', label: '輸出' },
  { type: 'imports', label: '輸入' },
]

// 輸出入: 表示形式
type TradeDisplayMode = 'chart' | 'heatmap'

const TRADE_DISPLAY_MODE_OPTIONS: { mode: TradeDisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// カラー設定
const COLORS = {
  balance: CHART_COLORS.primary,
  exports: '#52c41a',  // 緑
  imports: '#ff4d4f',  // 赤
}

export default function CnTradeBalanceChart({ data }: Props) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(5)
  const [activeTab, setActiveTab] = useState<string>('balance')
  const [balanceDataKind, setBalanceDataKind] = useState<BalanceDataKind>('level')
  const [balanceDisplayMode, setBalanceDisplayMode] = useState<BalanceDisplayMode>('chart')
  const [tradeDataKind, setTradeDataKind] = useState<TradeDataKind>('level')
  const [tradeDisplayMode, setTradeDisplayMode] = useState<TradeDisplayMode>('chart')
  const [tradeTableType, setTradeTableType] = useState<TradeTableType>('exports')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const dataCategory = activeTab === 'balance' ? 'balance' : 'trade'

  // 貿易収支データ
  const balanceChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []
    return (data.balance || []).map(item => ({
      date: item.date,
      value: item.value,
    }))
  }, [data])

  // 貿易収支 前月増減幅データ
  const balanceDiffData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []
    return (data.balance_mom_diff || []).map(item => ({
      date: item.date,
      value: item.value,
    }))
  }, [data])

  // 輸出・輸入データ
  const tradeChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    let exportsSource: { date: string; value: number }[] = []
    let importsSource: { date: string; value: number }[] = []

    if (tradeDataKind === 'mom') {
      exportsSource = data.exports_mom_diff || []
      importsSource = data.imports_mom_diff || []
    } else if (tradeDataKind === 'yoy') {
      exportsSource = data.exports_yoy || []
      importsSource = data.imports_yoy || []
    } else {
      exportsSource = data.exports || []
      importsSource = data.imports || []
    }

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
  }, [data, tradeDataKind])

  // ソートとフィルタリング
  const sortedBalanceData = useSortedData(balanceChartData)
  const sortedBalanceDiffData = useSortedData(balanceDiffData)
  const sortedTradeData = useSortedData(tradeChartData)

  const filteredBalanceData = usePeriodFiltering(sortedBalanceData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const filteredBalanceDiffData = usePeriodFiltering(sortedBalanceDiffData, {
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

  // 最新値
  const latestBalance = data?.latest_balance
  const latestExports = data?.latest_exports
  const latestImports = data?.latest_imports
  const nextRelease = data?.next_release ?? null

  // 最新のYoY
  const latestExportsYoy = useMemo(() => {
    const arr = data?.exports_yoy || []
    return arr.length > 0 ? arr[arr.length - 1] : null
  }, [data])
  const latestImportsYoy = useMemo(() => {
    const arr = data?.imports_yoy || []
    return arr.length > 0 ? arr[arr.length - 1] : null
  }, [data])

  // 最新の前月増減幅
  const latestBalanceMomDiff = useMemo(() => {
    const arr = data?.balance_mom_diff || []
    return arr.length > 0 ? arr[arr.length - 1] : null
  }, [data])
  const latestExportsMomDiff = useMemo(() => {
    const arr = data?.exports_mom_diff || []
    return arr.length > 0 ? arr[arr.length - 1] : null
  }, [data])
  const latestImportsMomDiff = useMemo(() => {
    const arr = data?.imports_mom_diff || []
    return arr.length > 0 ? arr[arr.length - 1] : null
  }, [data])

  // ローディング
  if (data === null) {
    return (
      <div id="cn-trade-balance">
        <LoadingChart title="貿易収支" />
      </div>
    )
  }

  // データなし
  if (!hasData) {
    return (
      <div id="cn-trade-balance">
        <ChartContainer title="貿易収支" showPeriodSelector={false} showDataSource={false}>
          <NoDataMessage />
        </ChartContainer>
      </div>
    )
  }

  // 貿易収支の最新値表示アイテム
  const getBalanceLatestItems = () => {
    const items = []

    if (balanceDataKind === 'level') {
      if (latestBalance?.value !== null && latestBalance?.value !== undefined) {
        items.push({
          label: '貿易収支',
          value: `${latestBalance.value >= 0 ? '+' : ''}${latestBalance.value.toFixed(1)} 億USD`,
          color: latestBalance.value >= 0 ? COLORS.balance : '#ef4444',
        })
      }
    } else if (balanceDataKind === 'diff') {
      if (latestBalanceMomDiff?.value !== null && latestBalanceMomDiff?.value !== undefined) {
        items.push({
          label: '前月増減幅',
          value: `${latestBalanceMomDiff.value >= 0 ? '+' : ''}${latestBalanceMomDiff.value.toFixed(1)} 億USD`,
          color: latestBalanceMomDiff.value >= 0 ? '#10b981' : '#ef4444',
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
          value: `${latestExports.value.toFixed(1)} 億USD`,
          color: COLORS.exports,
        })
      }
      if (latestImports?.value !== null && latestImports?.value !== undefined) {
        items.push({
          label: '輸入',
          value: `${latestImports.value.toFixed(1)} 億USD`,
          color: COLORS.imports,
        })
      }
    } else if (tradeDataKind === 'mom') {
      if (latestExportsMomDiff?.value !== null && latestExportsMomDiff?.value !== undefined) {
        items.push({
          label: '輸出 前月増減幅',
          value: `${latestExportsMomDiff.value >= 0 ? '+' : ''}${latestExportsMomDiff.value.toFixed(1)} 億USD`,
          color: latestExportsMomDiff.value >= 0 ? '#10b981' : '#ef4444',
        })
      }
      if (latestImportsMomDiff?.value !== null && latestImportsMomDiff?.value !== undefined) {
        items.push({
          label: '輸入 前月増減幅',
          value: `${latestImportsMomDiff.value >= 0 ? '+' : ''}${latestImportsMomDiff.value.toFixed(1)} 億USD`,
          color: latestImportsMomDiff.value >= 0 ? '#10b981' : '#ef4444',
        })
      }
    } else if (tradeDataKind === 'yoy') {
      if (latestExportsYoy?.value !== null && latestExportsYoy?.value !== undefined) {
        items.push({
          label: '輸出 前年比',
          value: `${latestExportsYoy.value >= 0 ? '+' : ''}${latestExportsYoy.value.toFixed(1)}%`,
          color: COLORS.exports,
        })
      }
      if (latestImportsYoy?.value !== null && latestImportsYoy?.value !== undefined) {
        items.push({
          label: '輸入 前年比',
          value: `${latestImportsYoy.value >= 0 ? '+' : ''}${latestImportsYoy.value.toFixed(1)}%`,
          color: COLORS.imports,
        })
      }
    }

    return items
  }

  // 最新値の日付を取得
  const getLatestDate = () => {
    if (dataCategory === 'balance') {
      if (balanceDataKind === 'diff') return latestBalanceMomDiff?.date
      return latestBalance?.date
    } else {
      if (tradeDataKind === 'mom') return latestExportsMomDiff?.date
      if (tradeDataKind === 'yoy') return latestExportsYoy?.date
      return latestExports?.date
    }
  }

  // 比較用指標ID
  const getCompareIndicatorId = () => {
    if (dataCategory === 'balance') return 'cn_trade_balance'
    return 'cn_exports'
  }

  return (
    <div id="cn-trade-balance">
      <ChartContainer
        title="貿易収支"
        showPeriodSelector={false}
        dataSource="General Administration of Customs / NBS"
        sourceUrl="https://data.stats.gov.cn/english/easyquery.htm?cn=A01"
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
                  {/* ViewModeButtonGroup + データ比較ボタン（同一行） */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      options={BALANCE_DATA_KIND_OPTIONS}
                      currentMode={balanceDataKind}
                      onChange={setBalanceDataKind}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(`/compare?s=${getCompareIndicatorId()}`, '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 表示形式（diffのときのみ） */}
                  {balanceDataKind === 'diff' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={BALANCE_DISPLAY_MODE_OPTIONS} currentMode={balanceDisplayMode} onChange={setBalanceDisplayMode} />
                    </div>
                  )}

                  {/* PeriodSelector（単独行） */}
                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                  {/* ヒートマップ */}
                  {balanceDataKind === 'diff' && balanceDisplayMode === 'heatmap' && (
                    <MonthlyTable
                      data={balanceDiffTableData}
                      formatValue={(v) => v === null ? '-' : `${v >= 0 ? '+' : ''}${v.toFixed(0)}`}
                      decimals={0}
                    />
                  )}
                  {/* チャート: 水準（棒グラフ） */}
                  {balanceDataKind === 'level' && (
                    <StandardBarChart
                      data={filteredBalanceData}
                      bars={[{ dataKey: 'value', name: '貿易収支', color: COLORS.balance }]}
                      xAxisFormatter={formatDateLabel}
                      yAxisFormatter={(v) => `${v.toFixed(0)}`}
                      tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)} 億USD`}
                      tooltipLabelFormatter={formatDateLabelJP}
                      showZeroLine={true}
                      showLegend={false}
                    />
                  )}

                  {/* チャート: 前月増減幅（棒グラフ） */}
                  {balanceDataKind === 'diff' && balanceDisplayMode === 'chart' && (
                    <StandardBarChart
                      data={filteredBalanceDiffData}
                      bars={[{ dataKey: 'value', name: '貿易収支', color: COLORS.balance }]}
                      xAxisFormatter={formatDateLabel}
                      yAxisFormatter={(v) => `${v.toFixed(0)}`}
                      tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)} 億USD`}
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
                  {/* ViewModeButtonGroup + データ比較ボタン（同一行） */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      options={TRADE_DATA_KIND_OPTIONS}
                      currentMode={tradeDataKind}
                      onChange={setTradeDataKind}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(`/compare?s=${getCompareIndicatorId()}`, '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 表示形式（momのときのみ） */}
                  {tradeDataKind === 'mom' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={TRADE_DISPLAY_MODE_OPTIONS} currentMode={tradeDisplayMode} onChange={setTradeDisplayMode} />
                    </div>
                  )}

                  {/* ヒートマップ時のテーブル種別選択 */}
                  {tradeDataKind === 'mom' && tradeDisplayMode === 'heatmap' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup
                        options={TRADE_TABLE_TYPE_OPTIONS.map(o => ({ mode: o.type, label: o.label }))}
                        currentMode={tradeTableType}
                        onChange={setTradeTableType}
                      />
                    </div>
                  )}

                  {/* PeriodSelector（単独行） */}
                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                  {/* ヒートマップ */}
                  {tradeDataKind === 'mom' && tradeDisplayMode === 'heatmap' && (
                    <MonthlyTable
                      data={tradeTableType === 'exports' ? exportsTableData : importsTableData}
                      formatValue={(v) => v === null ? '-' : `${v >= 0 ? '+' : ''}${v.toFixed(0)}`}
                      decimals={0}
                    />
                  )}

                  {/* チャート: 水準（棒グラフ） */}
                  {tradeDataKind === 'level' && (
                    <StandardBarChart
                      data={filteredTradeData}
                      bars={[
                        { dataKey: 'exports', name: '輸出', color: COLORS.exports },
                        { dataKey: 'imports', name: '輸入', color: COLORS.imports },
                      ]}
                      xAxisFormatter={formatDateLabel}
                      yAxisFormatter={(v) => `${v.toFixed(0)}`}
                      tooltipValueFormatter={(v) => `${v.toFixed(1)} 億USD`}
                      tooltipLabelFormatter={formatDateLabelJP}
                      showZeroLine={false}
                    />
                  )}

                  {/* チャート: 前年比（折れ線グラフ） */}
                  {tradeDataKind === 'yoy' && (
                    <StandardLineChart
                      data={filteredTradeData}
                      lines={[
                        { dataKey: 'exports', color: COLORS.exports, name: '輸出', hide: hiddenSeries.has('exports') },
                        { dataKey: 'imports', color: COLORS.imports, name: '輸入', hide: hiddenSeries.has('imports') },
                      ]}
                      xAxisFormatter={formatDateLabel}
                      yAxisFormatter={(v) => `${v.toFixed(0)}%`}
                      tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                      tooltipLabelFormatter={formatDateLabelJP}
                      showZeroLine={true}
                      onLegendClick={handleLegendClick}
                    />
                  )}

                  {/* チャート: 前月増減幅（棒グラフ） */}
                  {tradeDataKind === 'mom' && tradeDisplayMode === 'chart' && (
                    <StandardBarChart
                      data={filteredTradeData}
                      bars={[
                        { dataKey: 'exports', name: '輸出', color: COLORS.exports },
                        { dataKey: 'imports', name: '輸入', color: COLORS.imports },
                      ]}
                      xAxisFormatter={formatDateLabel}
                      yAxisFormatter={(v) => `${v.toFixed(0)}`}
                      tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)} 億USD`}
                      tooltipLabelFormatter={formatDateLabelJP}
                      showZeroLine={true}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="cn_trade_balance" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
