/**
 * EU交易条件（Terms of Trade）チャートコンポーネント
 *
 * データ:
 * - 交易条件（Terms of Trade）: 輸出単価指数 / 輸入単価指数 × 100
 * - 輸出単価指数（Export Unit Value）
 * - 輸入単価指数（Import Unit Value）
 *
 * データソース:
 * - Eurostat API
 *   - teiet300: Unit value of exports
 *   - teiet310: Unit value of imports
 *
 * 発表スケジュール:
 * - 月次（EU国際貿易と同時発表）
 */
import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'

import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabel,
  formatDateLabelJP,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
  ViewModeButtonGroup,
  ChartControlRow,
} from '../../usa/common/ChartComponents'
import { CHART_COLORS } from '../../usa/common/chartConstants'

import type { EUTermsOfTradeData } from '../../../../hooks/useDashboardData'
import type { PeriodValue } from '../../../common/PeriodSelector'

interface EUTermsOfTradeChartProps {
  data: EUTermsOfTradeData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  export_uv?: number | null
  import_uv?: number | null
  [key: string]: unknown
}

// ビューモード定義
type ViewMode = 'tot_chart' | 'uv_chart'

const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'tot_chart', label: '交易条件' },
  { mode: 'uv_chart', label: '単価指数' },
]

// カラー設定
const COLORS = {
  tot: CHART_COLORS.primary,
  export_uv: '#52c41a',    // 輸出 - 緑
  import_uv: '#faad14',    // 輸入 - 黄
}

// 系列名（日本語）
const SERIES_NAMES = {
  export_uv: '輸出単価指数',
  import_uv: '輸入単価指数',
}

// 初期非表示の系列なし
const INITIAL_HIDDEN: string[] = []

export default function EUTermsOfTradeChart({ data }: EUTermsOfTradeChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')
  const [viewMode, setViewMode] = useState<ViewMode>('tot_chart')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries(INITIAL_HIDDEN)

  // 交易条件データ
  const totChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.terms_of_trade) return []
    return data.terms_of_trade.map(item => ({
      date: item.date,
      value: item.value,
    }))
  }, [data])

  // 単価指数データ（輸出・輸入）
  const uvChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.export_uv && !data?.import_uv) return []

    // 全ての日付を収集
    const dateSet = new Set<string>()
    const exportMap = new Map<string, number>()
    const importMap = new Map<string, number>()

    if (data.export_uv) {
      data.export_uv.forEach(item => {
        dateSet.add(item.date)
        exportMap.set(item.date, item.value)
      })
    }

    if (data.import_uv) {
      data.import_uv.forEach(item => {
        dateSet.add(item.date)
        importMap.set(item.date, item.value)
      })
    }

    return Array.from(dateSet).sort().map(date => ({
      date,
      value: null,
      export_uv: exportMap.get(date) ?? null,
      import_uv: importMap.get(date) ?? null,
    }))
  }, [data])

  // 現在のビューモードに応じたデータを選択
  const rawChartData = viewMode === 'uv_chart' ? uvChartData : totChartData

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2024,
  })

  const hasData = (data?.terms_of_trade?.length ?? 0) > 0

  // 最新値を取得
  const latestTot = data?.latest_tot
  const latestExportUv = data?.latest_export_uv
  const latestImportUv = data?.latest_import_uv
  const nextRelease = data?.next_release ?? null

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="交易条件（ユーロ圏）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="交易条件（ユーロ圏）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    const items = []

    if (viewMode === 'tot_chart') {
      if (latestTot?.value !== null && latestTot?.value !== undefined) {
        items.push({
          label: '交易条件',
          value: latestTot.value.toFixed(1),
          color: COLORS.tot,
        })
      }
    } else {
      // 単価指数モード
      if (latestExportUv?.value !== null && latestExportUv?.value !== undefined) {
        items.push({
          label: '輸出単価',
          value: latestExportUv.value.toFixed(1),
          color: COLORS.export_uv,
        })
      }
      if (latestImportUv?.value !== null && latestImportUv?.value !== undefined) {
        items.push({
          label: '輸入単価',
          value: latestImportUv.value.toFixed(1),
          color: COLORS.import_uv,
        })
      }
    }

    return items
  }

  // 最新値の日付を取得
  const getLatestDate = () => {
    if (viewMode === 'uv_chart') {
      return latestExportUv?.date ?? latestImportUv?.date
    }
    return latestTot?.date
  }

  return (
    <div id="eu-terms-of-trade-chart">
      <ChartContainer
        title="交易条件（ユーロ圏）"
        showPeriodSelector={false}
        dataSource="Eurostat"
        sourceUrl="https://ec.europa.eu/eurostat/web/main/news/euro-indicators?p_p_id=estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageNumber=1&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_action=search&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageSize=11&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_text=balance+of+Trade&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_collection=CAT_PREREL&p_auth=rcRz7IFX&text=international+trade+"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={getLatestDate()}
          nextRelease={nextRelease}
        />

        {/* ビューモード切り替え */}
        <ViewModeButtonGroup
          options={VIEW_MODE_OPTIONS}
          currentMode={viewMode}
          onChange={setViewMode}
        />

        {/* 期間セレクタとデータ比較ボタン */}
        <ChartControlRow
          selectedPeriod={currentPeriod}
          onPeriodChange={setCurrentPeriod}
          indicatorId="eu_terms_of_trade"
        />

        {/* チャート表示 */}
        {viewMode === 'uv_chart' ? (
          <StandardLineChart
            data={filteredData}
            lines={[
              {
                dataKey: 'export_uv',
                color: COLORS.export_uv,
                name: SERIES_NAMES.export_uv,
                hide: hiddenSeries.has('export_uv'),
              },
              {
                dataKey: 'import_uv',
                color: COLORS.import_uv,
                name: SERIES_NAMES.import_uv,
                hide: hiddenSeries.has('import_uv'),
              },
            ]}
            xAxisFormatter={formatDateLabel}
            yAxisFormatter={(v) => v.toFixed(1)}
            tooltipValueFormatter={(v) => v.toFixed(1)}
            tooltipLabelFormatter={formatDateLabelJP}
            showZeroLine={false}
            onLegendClick={handleLegendClick}
            yDomain={['dataMin - 1', 'dataMax +1']}
          />
        ) : (
          <StandardLineChart
            data={filteredData}
            lines={[
              {
                dataKey: 'value',
                color: COLORS.tot,
                name: '交易条件',
              },
            ]}
            xAxisFormatter={formatDateLabel}
            yAxisFormatter={(v) => v.toFixed(1)}
            tooltipValueFormatter={(v) => v.toFixed(1)}
            tooltipLabelFormatter={formatDateLabelJP}
            showZeroLine={false}
            showLegend={false}
            yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
          />
        )}
      </ChartContainer>
    </div>
  )
}
