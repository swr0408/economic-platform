/**
 * 汎用経済指標チャートコンポーネント
 *
 * データフェッチ、ローディング、エラー処理、チャート描画を一括で処理。
 * 新しい指標を追加する際のボイラープレートコードを削減。
 *
 * @example
 * // 基本的な使用法
 * <GenericIndicatorChart
 *   title="POS-UVPI（週次）"
 *   fetchData={fetchPosUvpiData}
 *   lines={[{ dataKey: 'value', color: '#1890ff', name: 'POS-UVPI' }]}
 *   latestItems={(latest) => [
 *     { label: 'POS-UVPI', value: latest?.value, color: '#1890ff', format: 'percent' }
 *   ]}
 *   dataSource="一橋大学経済研究所"
 *   sourceUrl="https://..."
 *   compareIndicatorId="japan_pos_uvpi"
 * />
 */

import { useEffect, useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from './ChartContainer'
import LoadingChart from './LoadingChart'
import PeriodSelector from './PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../country/usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../country/usa/common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

/** API応答の基本型 */
interface BaseApiResponse<T> {
  data?: T[]
  latest?: T
  next_release?: {
    date?: string
    datetime_jst?: string
    label?: string
  }
  error?: string
}

/** 折れ線の設定 */
interface LineConfig {
  dataKey: string
  color: string
  name: string
  hide?: boolean
  strokeWidth?: number
  strokeDasharray?: string
  yAxisId?: 'left' | 'right'
}

/** 最新値表示アイテム */
interface LatestValueItem {
  label: string
  value: string | number | null | undefined
  color?: string
  format?: 'percent' | 'currency' | 'number' | 'raw'
  unit?: string
  decimals?: number
}

/** コンポーネントのプロパティ */
interface GenericIndicatorChartProps<T> {
  /** チャートタイトル */
  title: string
  /** チャートID（ページ内アンカー用） */
  chartId?: string
  /** データフェッチ関数 */
  fetchData: (forceRefresh?: boolean) => Promise<BaseApiResponse<T>>
  /** データをチャート用に変換する関数（省略時はそのまま使用） */
  transformData?: (data: T[]) => T[]
  /** データをフィルタリングする関数（省略時はnull/undefined除外） */
  filterData?: (item: T) => boolean
  /** 折れ線の設定 */
  lines: LineConfig[]
  /** 最新値表示アイテムを生成する関数 */
  latestItems: (latest: T | undefined) => LatestValueItem[]
  /** データソース名 */
  dataSource?: string
  /** データソースURL */
  sourceUrl?: string
  /** 比較ページ用の指標ID */
  compareIndicatorId?: string
  /** 比較ページ用のクエリパラメータ（複数系列の場合） */
  compareQueryParams?: string
  /** X軸のフォーマッター */
  xAxisFormatter?: (date: string) => string
  /** Y軸のフォーマッター */
  yAxisFormatter?: (value: number) => string
  /** ツールチップのラベルフォーマッター */
  tooltipLabelFormatter?: (date: string) => string
  /** ツールチップの値フォーマッター */
  tooltipValueFormatter?: (value: number, dataKey: string) => string
  /** 日付のフォーマッター（最新値表示用） */
  dateFormatter?: (date: string) => string
  /** Y軸のドメイン */
  yDomain?: [string | number, string | number]
  /** ゼロラインを表示するか */
  showZeroLine?: boolean
  /** 50ラインを表示するか */
  showFiftyLine?: boolean
  /** 右Y軸を表示するか */
  showRightYAxis?: boolean
  /** 右Y軸のフォーマッター */
  rightYAxisFormatter?: (value: number) => string
  /** 右Y軸のドメイン */
  rightYDomain?: [string | number, string | number]
  /** デフォルトの開始年（期間フィルタリング用） */
  defaultStartYear?: number
  /** チャートの高さ */
  chartHeight?: number
  /** 凡例のクリックでシリーズを非表示にする機能を有効化 */
  enableLegendToggle?: boolean
}

// =============================================================================
// ヘルパー関数
// =============================================================================

/** 月次日付フォーマット（YYYY/MM） */
const formatDateMonthly = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
}

/** 日次日付フォーマット（YYYY/MM/DD） */
const formatDateDaily = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`
}

/** 日本語月次日付フォーマット */
const formatDateMonthlyJP = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}年${date.getMonth() + 1}月`
}

/** 日本語日次日付フォーマット */
const formatDateDailyJP = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`
}

/** 次回発表日のフォーマット */
const formatNextRelease = (nextRelease?: { date?: string; datetime_jst?: string }): string | null => {
  if (!nextRelease) return null
  if (nextRelease.datetime_jst) {
    const dt = new Date(nextRelease.datetime_jst)
    return `${dt.getMonth() + 1}/${dt.getDate()} ${dt.getHours().toString().padStart(2, '0')}:${dt.getMinutes().toString().padStart(2, '0')}`
  }
  if (nextRelease.date) {
    const dt = new Date(nextRelease.date)
    return `${dt.getMonth() + 1}/${dt.getDate()}`
  }
  return null
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function GenericIndicatorChart<T extends { date: string }>({
  title,
  chartId,
  fetchData,
  transformData,
  filterData,
  lines,
  latestItems,
  dataSource,
  sourceUrl,
  compareIndicatorId,
  compareQueryParams,
  xAxisFormatter = formatDateMonthly,
  yAxisFormatter = (v) => `${v}%`,
  tooltipLabelFormatter = formatDateMonthlyJP,
  tooltipValueFormatter = (v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`,
  dateFormatter = formatDateMonthlyJP,
  yDomain = ['dataMin - 1', 'dataMax + 1'],
  showZeroLine = true,
  showFiftyLine = false,
  showRightYAxis = false,
  rightYAxisFormatter,
  rightYDomain,
  defaultStartYear = 2021,
  chartHeight = 450,
  enableLegendToggle = true,
}: GenericIndicatorChartProps<T>) {
  const [data, setData] = useState<BaseApiResponse<T> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentPeriod, setCurrentPeriod] = useState<number | 'default' | 'all'>(10)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データ取得
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true)
        setError(null)
        const res = await fetchData()
        if (res.error) {
          setError(res.error)
        } else {
          setData(res)
        }
      } catch (err) {
        console.error(`Error loading ${title} data:`, err)
        setError('データの読み込みに失敗しました')
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [fetchData, title])

  // データを変換
  const chartData = useMemo(() => {
    if (!data?.data) return []

    let processedData = data.data

    // フィルタリング
    if (filterData) {
      processedData = processedData.filter(filterData)
    } else {
      // デフォルト: 全ての値がnull/undefinedでない項目のみ
      processedData = processedData.filter((d) => {
        return lines.some((line) => {
          const value = (d as Record<string, unknown>)[line.dataKey]
          return value !== null && value !== undefined
        })
      })
    }

    // 変換
    if (transformData) {
      processedData = transformData(processedData)
    }

    return processedData
  }, [data, filterData, transformData, lines])

  // データを日付昇順にソート
  const sortedData = useSortedData(chartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear,
  })

  const hasData = sortedData.length > 0

  // 折れ線設定に非表示状態を適用
  const linesWithHidden = useMemo(() => {
    return lines.map((line) => ({
      ...line,
      hide: enableLegendToggle ? hiddenSeries.has(line.dataKey) : line.hide,
    }))
  }, [lines, hiddenSeries, enableLegendToggle])

  // ローディング状態
  if (loading) {
    return <LoadingChart title={title} />
  }

  // エラー状態
  if (error) {
    return (
      <ChartContainer title={title} showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>{error}</div>
      </ChartContainer>
    )
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title={title} showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest
  const nextReleaseStr = formatNextRelease(data?.next_release)

  // 比較ページURL
  const compareUrl = compareQueryParams
    ? `/compare?${compareQueryParams}`
    : compareIndicatorId
    ? `/compare?s=${compareIndicatorId}`
    : null

  return (
    <div id={chartId || title.toLowerCase().replace(/[^a-z0-9]/g, '-')}>
      <ChartContainer
        title={title}
        showPeriodSelector={false}
        showDataSource={!!dataSource}
        dataSource={dataSource}
        sourceUrl={sourceUrl}
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={latestItems(latest)}
          date={(latest as T & { date: string })?.date}
          dateFormatter={dateFormatter}
          nextRelease={nextReleaseStr ? { date: nextReleaseStr } : undefined}
        />

        {/* 期間セレクター + データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          {compareUrl && (
            <Tooltip title="比較ページを開く">
              <Button
                icon={<AreaChartOutlined />}
                onClick={() => window.open(compareUrl, '_blank')}
              >
                データ比較
              </Button>
            </Tooltip>
          )}
        </div>

        {/* チャート */}
        <StandardLineChart
          data={filteredData}
          lines={linesWithHidden}
          height={chartHeight}
          yAxisFormatter={yAxisFormatter}
          yDomain={yDomain}
          xAxisFormatter={xAxisFormatter}
          tooltipLabelFormatter={tooltipLabelFormatter}
          tooltipValueFormatter={tooltipValueFormatter}
          onLegendClick={enableLegendToggle ? handleLegendClick : undefined}
          showZeroLine={showZeroLine}
          showFiftyLine={showFiftyLine}
          showRightYAxis={showRightYAxis}
          rightYAxisFormatter={rightYAxisFormatter}
          rightYDomain={rightYDomain}
        />
      </ChartContainer>
    </div>
  )
}

// エクスポートするヘルパー関数
export {
  formatDateMonthly,
  formatDateDaily,
  formatDateMonthlyJP,
  formatDateDailyJP,
  formatNextRelease,
}

// 型のエクスポート
export type {
  GenericIndicatorChartProps,
  BaseApiResponse,
  LineConfig,
  LatestValueItem,
}
