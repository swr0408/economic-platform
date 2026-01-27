/**
 * ECB銀行貸出調査（BLS）チャートコンポーネント
 *
 * ECB APIからBank Lending Survey（銀行貸出調査）データを取得し、表示
 *
 * データ:
 * - 現在の信用需要 - 企業向け融資 (Loan demand - Enterprises - Current)
 * - 予想信用需要 - 企業向け融資 (Loan demand - Enterprises - Expected)
 * - 現在の信用需要 - 消費者信用 (Loan demand - Consumer credit - Current)
 * - 期待信用需要 - 消費者信用 (Loan demand - Consumer credit - Expected)
 * - 現在の信用需要 - 住宅購入向け融資 (Loan demand - Households for house purchase - Current)
 * - 期待信用需要 - 住宅購入向け融資 (Loan demand - Households for house purchase - Expected)
 *
 * データソース:
 * - European Central Bank (ECB) - Bank Lending Survey
 *
 * 発表スケジュール:
 * - 四半期（1月、4月、7月、10月）
 */
import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'

import { useHiddenSeries, type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, ChartControlRow, NextReleaseDisplay, ViewModeButtonGroup } from '../../usa/common/ChartComponents'
import { TEXT_COLORS, LATEST_VALUE_BOX_STYLE, CHART_COLORS } from '../../usa/common/chartConstants'

import type { ECBBLSData } from '../../../../hooks/useDashboardData'

interface ECBBLSChartProps {
  data: ECBBLSData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  enterprises_current: number
  enterprises_expected: number
  consumer_current: number
  consumer_expected: number
  housing_current: number
  housing_expected: number
  [key: string]: unknown
}

type ViewMode = 'enterprises' | 'consumer' | 'housing'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'enterprises', label: '企業向け' },
  { mode: 'housing', label: '住宅購入' },
  { mode: 'consumer', label: '消費者信用' },
]

// ECB四半期形式（2024-Q3）用のフォーマッター
const formatECBQuarterLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  return dateStr.replace('-Q', '/Q')
}

// ECB四半期形式から年を抽出
const getYearFromECBQuarter = (dateStr: string): number => {
  const match = dateStr.match(/^(\d{4})-Q\d$/)
  return match ? parseInt(match[1], 10) : 0
}

export default function ECBBLSChart({ data }: ECBBLSChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const [viewMode, setViewMode] = useState<ViewMode>('enterprises')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const dateMap = new Map<string, ChartDataPoint>()

    const initPoint = (date: string): ChartDataPoint => ({
      date,
      value: null,
      enterprises_current: 0,
      enterprises_expected: 0,
      consumer_current: 0,
      consumer_expected: 0,
      housing_current: 0,
      housing_expected: 0,
    })

    // 企業向け・現在
    const enterprisesCurrent = data.enterprises_current || []
    enterprisesCurrent.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      const existing = dateMap.get(point.date)!
      existing.enterprises_current = point.value || 0
    })

    // 企業向け・予想
    const enterprisesExpected = data.enterprises_expected || []
    enterprisesExpected.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      const existing = dateMap.get(point.date)!
      existing.enterprises_expected = point.value || 0
    })

    // 消費者信用・現在
    const consumerCurrent = data.consumer_current || []
    consumerCurrent.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      const existing = dateMap.get(point.date)!
      existing.consumer_current = point.value || 0
    })

    // 消費者信用・予想
    const consumerExpected = data.consumer_expected || []
    consumerExpected.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      const existing = dateMap.get(point.date)!
      existing.consumer_expected = point.value || 0
    })

    // 住宅購入向け・現在
    const housingCurrent = data.housing_current || []
    housingCurrent.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      const existing = dateMap.get(point.date)!
      existing.housing_current = point.value || 0
    })

    // 住宅購入向け・予想
    const housingExpected = data.housing_expected || []
    housingExpected.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, initPoint(point.date))
      }
      const existing = dateMap.get(point.date)!
      existing.housing_expected = point.value || 0
    })

    // 日付でソート
    const result = Array.from(dateMap.values()).sort((a, b) => a.date.localeCompare(b.date))
    return result
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    if (!chartData.length) return []

    const now = new Date()
    const currentYear = now.getFullYear()

    let startYear: number
    if (selectedPeriod === 'all') {
      return chartData
    } else if (selectedPeriod === 'default') {
      startYear = 2015
    } else if (typeof selectedPeriod === 'number') {
      startYear = currentYear - selectedPeriod
    } else {
      startYear = 2015
    }

    return chartData.filter(item => {
      const year = getYearFromECBQuarter(item.date)
      return year >= startYear
    })
  }, [chartData, selectedPeriod])

  // 最新値を取得
  const latestData = useMemo(() => {
    if (!filteredData.length) return null
    return filteredData[filteredData.length - 1]
  }, [filteredData])

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="銀行貸出調査（ユーロ圏）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="銀行貸出調査（ユーロ圏）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 値フォーマッター
  const formatValue = (value: number): string => {
    return `${value.toFixed(1)}`
  }

  // 現在のビューモードに応じた表示データキー
  const getKeysAndLabels = () => {
    switch (viewMode) {
      case 'enterprises':
        return {
          currentKey: 'enterprises_current',
          expectedKey: 'enterprises_expected',
          currentLabel: '現在（企業向け）',
          expectedLabel: '予想（企業向け）',
        }
      case 'housing':
        return {
          currentKey: 'housing_current',
          expectedKey: 'housing_expected',
          currentLabel: '現在（住宅購入）',
          expectedLabel: '予想（住宅購入）',
        }
      case 'consumer':
        return {
          currentKey: 'consumer_current',
          expectedKey: 'consumer_expected',
          currentLabel: '現在（消費者信用）',
          expectedLabel: '予想（消費者信用）',
        }
    }
  }

  const { currentKey, expectedKey, currentLabel, expectedLabel } = getKeysAndLabels()

  // 現在のビューモードの最新値
  const getLatestValues = () => {
    if (!latestData) return { current: 0, expected: 0 }
    switch (viewMode) {
      case 'enterprises':
        return { current: latestData.enterprises_current, expected: latestData.enterprises_expected }
      case 'consumer':
        return { current: latestData.consumer_current, expected: latestData.consumer_expected }
      case 'housing':
        return { current: latestData.housing_current, expected: latestData.housing_expected }
    }
  }

  const { current: latestCurrent, expected: latestExpected } = getLatestValues()

  return (
    <div id="ecb-bls-chart">
      <ChartContainer
        title="銀行貸出調査（ユーロ圏・BLS）"
        showPeriodSelector={false}
        dataSource="European Central Bank (ECB)"
        sourceUrl="https://www.ecb.europa.eu/stats/ecb_surveys/bank_lending_survey/html/index.en.html"
      >
        {/* 最新値表示 */}
        {latestData && (
          <div style={LATEST_VALUE_BOX_STYLE}>
            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
              <div>
                <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>現在: </span>
                <span
                  style={{
                    fontSize: 18,
                    fontWeight: 'bold',
                    color: latestCurrent >= 0 ? TEXT_COLORS.positive : TEXT_COLORS.negative,
                  }}
                >
                  {formatValue(latestCurrent)}
                </span>
              </div>
              <div>
                <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>予想: </span>
                <span
                  style={{
                    fontSize: 18,
                    fontWeight: 'bold',
                    color: latestExpected >= 0 ? TEXT_COLORS.positive : TEXT_COLORS.negative,
                  }}
                >
                  {formatValue(latestExpected)}
                </span>
              </div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.tertiary }}>
                ({formatECBQuarterLabel(latestData.date)})
              </span>
            </div>
            <NextReleaseDisplay nextRelease={data.next_release} />
          </div>
        )}

        {/* ビューモード切り替え */}
        <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />

        {/* 期間セレクター + 比較ボタン */}
        <ChartControlRow
          selectedPeriod={selectedPeriod}
          onPeriodChange={setSelectedPeriod}
          indicatorId="ecb_bls"
        />

        {/* チャート */}
        <ZoomableChart
          data={filteredData}
          dataKey={currentKey}
          color={CHART_COLORS.primary}
          name={currentLabel}
          height={450}
          tickFormatter={formatValue}
          tooltipFormatter={formatValue}
          tooltipLabelFormatter={formatECBQuarterLabel}
          xAxisTickFormatter={formatECBQuarterLabel}
          enableDynamicTicks={true}
          showZeroLine={true}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={false}
          onLegendClick={handleLegendClick}
          initialHiddenLines={Array.from(hiddenSeries)}
          additionalLines={[
            {
              dataKey: expectedKey,
              color: CHART_COLORS.orange,
              name: expectedLabel,
              strokeWidth: 2,
            }
          ]}
        />
      </ChartContainer>
    </div>
  )
}
