/**
 * ECB銀行貸出調査（BLS）チャートコンポーネント
 *
 * ECB APIからBank Lending Survey（銀行貸出調査）データを取得し、表示
 *
 * データ:
 * - Enterprises (企業向け融資の信用基準)
 * - Households (家計向け住宅融資の信用基準)
 *
 * データソース:
 * - European Central Bank (ECB) - Bank Lending Survey
 *
 * 発表スケジュール:
 * - 毎日18:00 CET更新
 */
import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'

import { type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, ChartControlRow } from '../../usa/common/ChartComponents'
import { TEXT_COLORS, LATEST_VALUE_BOX_STYLE } from '../../usa/common/chartConstants'

import type { ECBBLSData } from '../../../../hooks/useDashboardData'

interface ECBBLSChartProps {
  data: ECBBLSData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  enterprises: number
  households: number
  [key: string]: unknown
}

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

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data || !data.enterprises || !data.households) return []

    const dateMap = new Map<string, ChartDataPoint>()

    // 企業向けデータをマージ
    data.enterprises.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, { date: point.date, value: null, enterprises: 0, households: 0 })
      }
      const existing = dateMap.get(point.date)!
      existing.enterprises = point.value || 0
      existing.value = point.value || 0  // valueフィールドに企業向け融資を設定
    })

    // 家計向けデータをマージ
    data.households.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, { date: point.date, value: null, enterprises: 0, households: 0 })
      }
      const existing = dateMap.get(point.date)!
      existing.households = point.value || 0
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

  return (
    <div id="ecb-bls-chart">
      <ChartContainer
        title="銀行貸出調査（ユーロ圏）"
        showPeriodSelector={false}
        dataSource="European Central Bank (ECB)"
        sourceUrl="https://www.ecb.europa.eu/stats/ecb_surveys/bank_lending_survey/html/index.en.html"
      >
        {/* 最新値表示 */}
        {latestData && (
          <div style={LATEST_VALUE_BOX_STYLE}>
            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
              <div>
                <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>企業向け: </span>
                <span
                  style={{
                    fontSize: 18,
                    fontWeight: 'bold',
                    color: latestData.enterprises >= 0 ? TEXT_COLORS.positive : TEXT_COLORS.negative,
                  }}
                >
                  {formatValue(latestData.enterprises)}
                </span>
              </div>
              <div>
                <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>家計向け: </span>
                <span
                  style={{
                    fontSize: 18,
                    fontWeight: 'bold',
                    color: latestData.households >= 0 ? TEXT_COLORS.positive : TEXT_COLORS.negative,
                  }}
                >
                  {formatValue(latestData.households)}
                </span>
              </div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.tertiary }}>
                ({formatECBQuarterLabel(latestData.date)})
              </span>
            </div>
          </div>
        )}

        {/* 期間セレクター + 比較ボタン */}
        <ChartControlRow
          selectedPeriod={selectedPeriod}
          onPeriodChange={setSelectedPeriod}
          indicatorId="ecb_bls_enterprises"
        />

        {/* チャート */}
        <ZoomableChart
          data={filteredData}
          dataKey="enterprises"
          color="#3B82F6"
          name="企業向け融資"
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
          additionalLines={[
            {
              dataKey: 'households',
              color: '#10B981',
              name: '家計向け融資',
              strokeWidth: 2,
            }
          ]}
        />
      </ChartContainer>
    </div>
  )
}
