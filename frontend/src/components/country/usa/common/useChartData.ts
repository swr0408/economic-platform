/**
 * チャートデータ処理用共通Hooks
 *
 * データのソート、期間フィルタリング、日付フォーマットを共通化
 */
import { useMemo, useState, useCallback } from 'react'
import type { IndicatorFrequency } from '../../../../constants/overlayConfig'

// =============================================================================
// 型定義
// =============================================================================

/** 日付を持つデータの基本型 */
export interface DateBasedData {
  date: string
}

/** 期間選択の型 */
export type PeriodType = number | 'all' | 'default'

// =============================================================================
// useSortedData - データを日付でソート
// =============================================================================

/**
 * データを日付昇順でソートするHook
 *
 * @param data - ソート対象のデータ配列
 * @returns ソート済みのデータ配列
 *
 * @example
 * const sortedData = useSortedData(data?.data)
 */
export function useSortedData<T extends DateBasedData>(
  data: T[] | undefined | null
): T[] {
  return useMemo(() => {
    if (!data || data.length === 0) return []

    return [...data].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    )
  }, [data])
}

// =============================================================================
// usePeriodFiltering - 期間でデータをフィルタリング
// =============================================================================

interface PeriodFilteringOptions {
  /** 選択された期間 */
  selectedPeriod: PeriodType
  /** 'default' 選択時の開始年（デフォルト: 2010） */
  defaultStartYear?: number
}

/**
 * 期間に基づいてデータをフィルタリングするHook
 *
 * @param data - フィルタリング対象のデータ配列
 * @param options - フィルタリングオプション
 * @returns フィルタリング済みのデータ配列
 *
 * @example
 * const filteredData = usePeriodFiltering(sortedData, {
 *   selectedPeriod: selectedPeriod,
 *   defaultStartYear: 2010
 * })
 */
export function usePeriodFiltering<T extends DateBasedData>(
  data: T[],
  options: PeriodFilteringOptions
): T[] {
  const { selectedPeriod, defaultStartYear = 2010 } = options

  return useMemo(() => {
    if (data.length === 0) return []

    if (selectedPeriod === 'all') {
      return data
    }

    const cutoffDate = new Date()

    if (selectedPeriod === 'default') {
      cutoffDate.setFullYear(defaultStartYear, 0, 1)
    } else {
      cutoffDate.setFullYear(cutoffDate.getFullYear() - selectedPeriod)
    }

    return data.filter((item) => {
      const itemDate = new Date(item.date)
      return itemDate >= cutoffDate
    })
  }, [data, selectedPeriod, defaultStartYear])
}

// =============================================================================
// 日付フォーマット関数
// =============================================================================

/**
 * 日付を YYYY/MM 形式にフォーマット（X軸用）
 */
export function formatDateLabel(dateStr: string): string {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
}

/**
 * 日付を YYYY年M月 形式にフォーマット（ツールチップ用）
 */
export function formatDateLabelJP(dateStr: string): string {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}/${date.getMonth() + 1}`
}

/**
 * 日付を YYYY/Q1 形式にフォーマット（四半期用）
 */
export function formatQuarterLabel(dateStr: string): string {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  const quarter = Math.floor(date.getMonth() / 3) + 1
  return `${date.getFullYear()}/Q${quarter}`
}

/**
 * 日付を YYYY年Q1 形式にフォーマット（四半期用ツールチップ）
 */
export function formatQuarterLabelJP(dateStr: string): string {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  const quarter = Math.floor(date.getMonth() / 3) + 1
  return `${date.getFullYear()}/Q${quarter}`
}

/**
 * 日付を YYYY/MM/DD 形式にフォーマット（日付付き）
 */
export function formatDateLabelFull(dateStr: string): string {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  const year = date.getFullYear()
  const month = (date.getMonth() + 1).toString().padStart(2, '0')
  const day = date.getDate().toString().padStart(2, '0')
  return `${year}/${month}/${day}`
}

/**
 * 日付を YYYY年MM月DD日 形式にフォーマット（日本語フル表記）
 */
export function formatDateLabelFullJP(dateStr: string): string {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`
}

/**
 * 週次日付を MM/DD 形式にフォーマット（週次データX軸用）
 */
export function formatWeekEnding(dateStr: string): string {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  const month = date.getMonth() + 1
  const day = date.getDate()
  return `${month}/${day}`
}

/**
 * 週次日付を YYYY年MM月DD日週 形式にフォーマット（週次データツールチップ用）
 */
export function formatWeekEndingJP(dateStr: string): string {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  const year = date.getFullYear()
  const month = date.getMonth() + 1
  const day = date.getDate()
  return `${year}年${month}月${day}日週`
}

// =============================================================================
// 頻度に応じたフォーマッター選択
// =============================================================================

export interface FrequencyFormatterPair {
  xAxisFormatter: (dateStr: string) => string
  tooltipFormatter: (dateStr: string) => string
}

/**
 * 頻度に応じた日付フォーマッターのペアを返す
 *
 * @param frequency - 指標の頻度
 * @returns X軸用とツールチップ用のフォーマッターペア
 *
 * @example
 * const { xAxisFormatter, tooltipFormatter } = getFrequencyFormatters('daily')
 */
export function getFrequencyFormatters(frequency: IndicatorFrequency): FrequencyFormatterPair {
  switch (frequency) {
    case 'daily':
      return {
        xAxisFormatter: formatDateLabelFull,      // YYYY/MM/DD
        tooltipFormatter: formatDateLabelFullJP,  // YYYY年MM月DD日
      }
    case 'weekly':
      return {
        xAxisFormatter: formatDateLabelFull,      // YYYY/MM/DD
        tooltipFormatter: formatWeekEndingJP,     // YYYY年MM月DD日週
      }
    case 'monthly':
      return {
        xAxisFormatter: formatDateLabel,          // YYYY/MM
        tooltipFormatter: formatDateLabelJP,      // YYYY年M月
      }
    case 'quarterly':
      return {
        xAxisFormatter: formatQuarterLabel,       // YYYY/Q1
        tooltipFormatter: formatQuarterLabelJP,   // YYYY年Q1
      }
    case 'irregular':
    default:
      return {
        xAxisFormatter: formatDateLabel,          // YYYY/MM
        tooltipFormatter: formatDateLabelJP,      // YYYY年M月
      }
  }
}

// =============================================================================
// 値フォーマット関数
// =============================================================================

/**
 * 数値をパーセント形式にフォーマット（符号付き）
 */
export function formatPercent(
  value: number | null | undefined,
  decimals: number = 2
): string {
  if (value === null || value === undefined) return 'N/A'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(decimals)}%`
}

/**
 * 数値をパーセント形式にフォーマット（符号なし）
 */
export function formatPercentNoSign(
  value: number | null | undefined,
  decimals: number = 2
): string {
  if (value === null || value === undefined) return 'N/A'
  return `${value.toFixed(decimals)}%`
}

/**
 * 数値を通貨形式にフォーマット
 */
export function formatCurrency(
  value: number | null | undefined,
  unit: string = 'B',
  decimals: number = 2
): string {
  if (value === null || value === undefined) return 'N/A'
  return `$${value.toFixed(decimals)}${unit}`
}

/**
 * 数値を単位付きでフォーマット
 */
export function formatWithUnit(
  value: number | null | undefined,
  unit: string,
  decimals: number = 2
): string {
  if (value === null || value === undefined) return 'N/A'
  return `${value.toFixed(decimals)}${unit}`
}

// =============================================================================
// useMergedNominalRealData - 名目・実質データのマージ
// =============================================================================

interface NominalRealDataItem {
  date: string
  mom?: number | null
  yoy?: number | null
}

interface MergedNominalRealItem {
  date: string
  nominal_mom: number | null
  nominal_yoy: number | null
  real_mom: number | null
  real_yoy: number | null
}

/**
 * 名目・実質データをマージして日付昇順にソートするHook
 * PCE, PersonalIncome, DisposableIncome など共通で使用
 *
 * @param nominalData - 名目データ配列
 * @param realData - 実質データ配列
 * @returns マージされたデータ配列
 */
export function useMergedNominalRealData(
  nominalData: NominalRealDataItem[] | undefined,
  realData: NominalRealDataItem[] | undefined
): MergedNominalRealItem[] {
  return useMemo(() => {
    const nominal = nominalData || []
    const real = realData || []

    const dateMap = new Map<string, MergedNominalRealItem>()

    nominal.forEach((item) => {
      dateMap.set(item.date, {
        date: item.date,
        nominal_mom: item.mom ?? null,
        nominal_yoy: item.yoy ?? null,
        real_mom: null,
        real_yoy: null,
      })
    })

    real.forEach((item) => {
      const existing = dateMap.get(item.date)
      if (existing) {
        existing.real_mom = item.mom ?? null
        existing.real_yoy = item.yoy ?? null
      } else {
        dateMap.set(item.date, {
          date: item.date,
          nominal_mom: null,
          nominal_yoy: null,
          real_mom: item.mom ?? null,
          real_yoy: item.yoy ?? null,
        })
      }
    })

    return Array.from(dateMap.values()).sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    )
  }, [nominalData, realData])
}

// =============================================================================
// useMonthlyTableData - 月別テーブルデータを生成
// =============================================================================

interface MonthlyTableDataResult<T> {
  years: number[]
  monthlyData: Record<number, Record<number, T | null>>
}

/**
 * チャートデータから月別テーブルデータを生成するHook
 *
 * @param data - 元データ配列
 * @param valueExtractor - 各アイテムから値を抽出する関数
 * @param yearRange - 表示する年数（デフォルト: 10年）
 * @returns 年別×月別のマトリックスデータ
 *
 * @example
 * const tableData = useMonthlyTableData(
 *   chartData,
 *   (item) => item.mom,
 *   10
 * )
 */
export function useMonthlyTableData<T extends DateBasedData, V>(
  data: T[],
  valueExtractor: (item: T) => V | null | undefined,
  yearRange: number = 10
): MonthlyTableDataResult<V> {
  return useMemo(() => {
    if (data.length === 0) return { years: [], monthlyData: {} }

    const currentYear = new Date().getFullYear()
    const startYear = currentYear - (yearRange - 1)

    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) {
      years.push(y)
    }

    const monthlyData: Record<number, Record<number, V | null>> = {}

    data.forEach((item) => {
      const date = new Date(item.date)
      const year = date.getFullYear()
      const month = date.getMonth()

      if (year >= startYear && year <= currentYear) {
        if (!monthlyData[year]) {
          monthlyData[year] = {}
        }
        const value = valueExtractor(item)
        monthlyData[year][month] = value ?? null
      }
    })

    return { years, monthlyData }
  }, [data, valueExtractor, yearRange])
}

// =============================================================================
// useQuarterlyTableData - 四半期別テーブルデータを生成
// =============================================================================

interface QuarterlyTableDataResult<T> {
  years: number[]
  quarterlyData: Record<number, Record<number, T | null>>
}

/**
 * 四半期形式の日付（YYYY-QN）をパースしてyearとquarter（0-3）を返す
 * 通常の日付形式（YYYY-MM-DD）もサポート
 */
function parseQuarterlyDate(dateStr: string): { year: number; quarter: number } | null {
  // YYYY-QN 形式をパース
  const quarterMatch = dateStr.match(/^(\d{4})-Q([1-4])$/)
  if (quarterMatch) {
    const year = parseInt(quarterMatch[1], 10)
    const quarter = parseInt(quarterMatch[2], 10) - 1 // 0-indexed (Q1=0, Q2=1, Q3=2, Q4=3)
    return { year, quarter }
  }

  // 通常の日付形式（YYYY-MM-DD）をパース
  const date = new Date(dateStr)
  if (!isNaN(date.getTime())) {
    return {
      year: date.getFullYear(),
      quarter: Math.floor(date.getMonth() / 3)
    }
  }

  return null
}

/**
 * チャートデータから四半期別テーブルデータを生成するHook
 */
export function useQuarterlyTableData<T extends DateBasedData, V>(
  data: T[],
  valueExtractor: (item: T) => V | null | undefined,
  yearRange: number = 10
): QuarterlyTableDataResult<V> {
  return useMemo(() => {
    if (data.length === 0) return { years: [], quarterlyData: {} }

    const currentYear = new Date().getFullYear()
    const startYear = currentYear - (yearRange - 1)

    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) {
      years.push(y)
    }

    const quarterlyData: Record<number, Record<number, V | null>> = {}

    data.forEach((item) => {
      const parsed = parseQuarterlyDate(item.date)
      if (!parsed) return

      const { year, quarter } = parsed

      if (year >= startYear && year <= currentYear) {
        if (!quarterlyData[year]) {
          quarterlyData[year] = {}
        }
        const value = valueExtractor(item)
        // 各四半期の最新値を保持
        quarterlyData[year][quarter] = value ?? null
      }
    })

    return { years, quarterlyData }
  }, [data, valueExtractor, yearRange])
}

// =============================================================================
// useMultiValueMonthlyTableData - 複数値の月別テーブルデータを生成
// =============================================================================

interface MultiValueMonthlyTableDataResult<T extends string> {
  years: number[]
  monthlyData: Record<number, Record<number, Record<T, number | null> | null>>
}

/**
 * 複数の値を持つ月別テーブルデータを生成するHook
 * MonthlyTableWithDataTypes コンポーネントと組み合わせて使用
 *
 * @param data - 元データ配列
 * @param valueExtractors - 各データタイプの値を抽出する関数のマップ
 * @param yearRange - 表示する年数（デフォルト: 10年）
 * @returns 年別×月別×データタイプのマトリックスデータ
 *
 * @example
 * const tableData = useMultiValueMonthlyTableData(
 *   chartData,
 *   {
 *     total: (item) => item.mom,
 *     ex_transport: (item) => item.ex_transport_mom,
 *   },
 *   10
 * )
 */
export function useMultiValueMonthlyTableData<T extends DateBasedData, K extends string>(
  data: T[],
  valueExtractors: Record<K, (item: T) => number | null | undefined>,
  yearRange: number = 10
): MultiValueMonthlyTableDataResult<K> {
  return useMemo(() => {
    if (data.length === 0) return { years: [], monthlyData: {} }

    const currentYear = new Date().getFullYear()
    const startYear = currentYear - (yearRange - 1)

    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) {
      years.push(y)
    }

    const monthlyData: Record<number, Record<number, Record<K, number | null> | null>> = {}

    data.forEach((item) => {
      const date = new Date(item.date)
      const year = date.getFullYear()
      const month = date.getMonth()

      if (year >= startYear && year <= currentYear) {
        if (!monthlyData[year]) {
          monthlyData[year] = {}
        }

        const values = {} as Record<K, number | null>
        for (const [key, extractor] of Object.entries(valueExtractors) as [K, (item: T) => number | null | undefined][]) {
          values[key] = extractor(item) ?? null
        }
        monthlyData[year][month] = values
      }
    })

    return { years, monthlyData }
  }, [data, valueExtractors, yearRange])
}

// =============================================================================
// useHiddenSeries - 凡例クリックによる系列表示/非表示管理
// =============================================================================

interface UseHiddenSeriesResult<T extends string = string> {
  /** 非表示にされている系列のSet */
  hiddenSeries: Set<T>
  /** 凡例クリック時のハンドラ */
  handleLegendClick: (dataKey: string) => void
  /** 特定の系列が非表示かどうかを確認 */
  isHidden: (dataKey: T) => boolean
  /** すべての系列を表示 */
  showAll: () => void
  /** 指定した系列のみを表示（他を非表示） */
  showOnly: (dataKey: T) => void
}

/**
 * 凡例クリックによる系列の表示/非表示を管理するHook
 *
 * @param initialHidden - 初期状態で非表示にする系列の配列またはSet
 * @param allKeys - すべての系列キー（showOnlyで使用）
 * @returns hiddenSeries, handleLegendClick, isHidden, showAll, showOnly
 *
 * @example
 * const { hiddenSeries, handleLegendClick, isHidden } = useHiddenSeries<'yoy' | 'mom'>()
 * const { hiddenSeries, handleLegendClick } = useHiddenSeries(['future']) // 初期非表示
 *
 * <Legend onClick={(e) => handleLegendClick(e.dataKey as string)} />
 * <Line dataKey="yoy" hide={isHidden('yoy')} />
 */
export function useHiddenSeries<T extends string = string>(
  initialHidden?: T[] | Set<T>,
  allKeys?: T[]
): UseHiddenSeriesResult<T> {
  const [hiddenSeries, setHiddenSeries] = useState<Set<T>>(() => {
    if (!initialHidden) return new Set()
    return initialHidden instanceof Set ? new Set(initialHidden) : new Set(initialHidden)
  })

  const handleLegendClick = useCallback((dataKey: string) => {
    setHiddenSeries((prev) => {
      const next = new Set(prev)
      if (next.has(dataKey as T)) {
        next.delete(dataKey as T)
      } else {
        next.add(dataKey as T)
      }
      return next
    })
  }, [])

  const isHidden = useCallback(
    (dataKey: T): boolean => hiddenSeries.has(dataKey),
    [hiddenSeries]
  )

  const showAll = useCallback(() => {
    setHiddenSeries(new Set())
  }, [])

  const showOnly = useCallback(
    (dataKey: T) => {
      if (!allKeys) return
      const newHidden = new Set<T>(allKeys.filter((k) => k !== dataKey))
      setHiddenSeries(newHidden)
    },
    [allKeys]
  )

  return { hiddenSeries, handleLegendClick, isHidden, showAll, showOnly }
}

// =============================================================================
// useViewModePeriodManagement - ビューモード毎の期間管理
// =============================================================================

interface UseViewModePeriodManagementResult<M extends string> {
  /** 各ビューモードの選択期間を取得 */
  getPeriod: (mode: M) => PeriodType
  /** ビューモードの期間を設定 */
  setPeriod: (mode: M, period: PeriodType) => void
  /** 現在のビューモードの期間を取得 */
  currentPeriod: PeriodType
  /** 現在のビューモードの期間セッター */
  setCurrentPeriod: (period: PeriodType) => void
}

/**
 * 複数のビューモードごとに独立した期間選択を管理するHook
 *
 * @param currentMode - 現在のビューモード
 * @param defaultPeriods - 各ビューモードのデフォルト期間
 * @returns 期間管理オブジェクト
 *
 * @example
 * const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(
 *   viewMode,
 *   { yoy: 'default', mom_chart: 3, mom_table: 'all' }
 * )
 */
export function useViewModePeriodManagement<M extends string>(
  currentMode: M,
  defaultPeriods: Partial<Record<M, PeriodType>>
): UseViewModePeriodManagementResult<M> {
  const [periods, setPeriods] = useState<Partial<Record<M, PeriodType>>>(defaultPeriods)

  const getPeriod = useCallback(
    (mode: M): PeriodType => periods[mode] ?? 'default',
    [periods]
  )

  const setPeriod = useCallback((mode: M, period: PeriodType) => {
    setPeriods((prev) => ({ ...prev, [mode]: period }))
  }, [])

  const currentPeriod = getPeriod(currentMode)

  const setCurrentPeriod = useCallback(
    (period: PeriodType) => {
      setPeriod(currentMode, period)
    },
    [currentMode, setPeriod]
  )

  return { getPeriod, setPeriod, currentPeriod, setCurrentPeriod }
}

// =============================================================================
// ツールチップフォーマッター関数
// =============================================================================

type TooltipFormatter = (value: unknown, name: string) => [string, string]

/**
 * パーセント表示用のツールチップフォーマッターを生成
 *
 * @param decimals - 小数点以下の桁数（デフォルト: 2）
 * @param showSign - 符号を表示するか（デフォルト: true）
 * @returns Rechart Tooltip用のフォーマッター関数
 *
 * @example
 * <Tooltip formatter={createPercentFormatter()} />
 */
export function createPercentFormatter(decimals: number = 2, showSign: boolean = true): TooltipFormatter {
  return (value: unknown, name: string): [string, string] => {
    const numValue = typeof value === 'number' ? value : null
    if (numValue === null) return ['N/A', name]
    if (showSign) {
      return [formatPercent(numValue, decimals), name]
    }
    return [formatPercentNoSign(numValue, decimals), name]
  }
}

/**
 * 数値表示用のツールチップフォーマッターを生成
 *
 * @param decimals - 小数点以下の桁数（デフォルト: 1）
 * @returns Recharts Tooltip用のフォーマッター関数
 *
 * @example
 * <Tooltip formatter={createNumberFormatter(1)} />
 */
export function createNumberFormatter(decimals: number = 1): TooltipFormatter {
  return (value: unknown, name: string): [string, string] => {
    const numValue = typeof value === 'number' ? value : null
    return [numValue !== null ? numValue.toFixed(decimals) : 'N/A', name]
  }
}

/**
 * 通貨表示用のツールチップフォーマッターを生成
 *
 * @param unit - 単位（デフォルト: 'B'）
 * @param decimals - 小数点以下の桁数（デフォルト: 2）
 * @returns Recharts Tooltip用のフォーマッター関数
 *
 * @example
 * <Tooltip formatter={createCurrencyFormatter('B', 2)} />
 */
export function createCurrencyFormatter(unit: string = 'B', decimals: number = 2): TooltipFormatter {
  return (value: unknown, name: string): [string, string] => {
    const numValue = typeof value === 'number' ? value : null
    return [numValue !== null ? formatCurrency(numValue, unit, decimals) : 'N/A', name]
  }
}

/**
 * ドル値表示用のツールチップフォーマッターを生成（10億ドル単位）
 *
 * @param decimals - 小数点以下の桁数（デフォルト: 1）
 * @param divisor - 除数（デフォルト: 1000=10億ドル単位に変換）
 * @returns Recharts Tooltip用のフォーマッター関数
 *
 * @example
 * <Tooltip formatter={createDollarFormatter(1)} /> // $1234.5B
 */
export function createDollarFormatter(decimals: number = 1, divisor: number = 1000): TooltipFormatter {
  return (value: unknown, name: string): [string, string] => {
    const numValue = typeof value === 'number' ? value : null
    if (numValue === null) return ['N/A', name]
    const converted = numValue / divisor
    return [`$${converted.toFixed(decimals)}B`, name]
  }
}

/**
 * 単位付き数値表示用のツールチップフォーマッターを生成
 *
 * @param unit - 単位（例: '万台', '%'）
 * @param decimals - 小数点以下の桁数（デフォルト: 1）
 * @returns Recharts Tooltip用のフォーマッター関数
 *
 * @example
 * <Tooltip formatter={createUnitFormatter('万台', 1)} />
 */
export function createUnitFormatter(unit: string, decimals: number = 1): TooltipFormatter {
  return (value: unknown, name: string): [string, string] => {
    const numValue = typeof value === 'number' ? value : null
    return [numValue !== null ? `${numValue.toFixed(decimals)}${unit}` : 'N/A', name]
  }
}
