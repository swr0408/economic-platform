/**
 * ZEW景況感指数チャートコンポーネント
 *
 * データ:
 * - ZEW Indicator of Economic Sentiment Germany（景況感指数）: 経済見通しに関する期待
 * - Economic Situation Germany（現況指数）: 現在の経済状況の評価
 *
 * データソース:
 * - ZEW (ドイツ経済研究センター)
 * - FMP economic_calendar_events
 *
 * 発表スケジュール:
 * - 月次（毎月第2または第3火曜日 11:00 CET）
 */
import { useState, useMemo } from 'react'
import { Tabs } from 'antd'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import { type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, ChartControlRow, NextReleaseDisplay } from '../../usa/common/ChartComponents'
import { TEXT_COLORS, LATEST_VALUE_BOX_STYLE } from '../../usa/common/chartConstants'

import type { ZEWEconomicSentimentData } from '../../../../hooks/useDashboardData'

interface ZEWEconomicSentimentChartProps {
  data: ZEWEconomicSentimentData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  sentiment: number | null
  situation: number | null
  [key: string]: unknown
}

// 月次形式（YYYY-MM）用のフォーマッター
const formatMonthLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  return dateStr.replace('-', '/')
}

// 月次形式から年を抽出
const getYearFromMonth = (dateStr: string): number => {
  const match = dateStr.match(/^(\d{4})-\d{2}$/)
  return match ? parseInt(match[1], 10) : 0
}

export default function ZEWEconomicSentimentChart({ data }: ZEWEconomicSentimentChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const dateMap = new Map<string, ChartDataPoint>()

    // 景況感指数（期待）データをマージ
    data.sentiment?.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, {
          date: point.date,
          value: null,
          sentiment: null,
          situation: null,
        })
      }
      const existing = dateMap.get(point.date)!
      existing.sentiment = point.value
      existing.value = point.value // valueフィールドに景況感を設定
    })

    // 現況指数データをマージ
    data.situation?.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, {
          date: point.date,
          value: null,
          sentiment: null,
          situation: null,
        })
      }
      const existing = dateMap.get(point.date)!
      existing.situation = point.value
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
      const year = getYearFromMonth(item.date)
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
    return <LoadingChart title="ZEW景況感指数（ドイツ）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="ZEW景況感指数（ドイツ）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 値フォーマッター
  const formatValue = (value: number): string => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(1)}`
  }

  // チャートコンテンツ
  const chartContent = (
    <>
      {/* 最新値表示 */}
      {latestData && (
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>景況感（期待）: </span>
              <span
                style={{
                  fontSize: 18,
                  fontWeight: 'bold',
                  color: latestData.sentiment !== null && latestData.sentiment >= 0 ? TEXT_COLORS.positive : TEXT_COLORS.negative,
                }}
              >
                {latestData.sentiment !== null ? formatValue(latestData.sentiment) : '-'}
              </span>
            </div>
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>現況: </span>
              <span
                style={{
                  fontSize: 14,
                  color: latestData.situation !== null && latestData.situation >= 0 ? TEXT_COLORS.positive : TEXT_COLORS.negative,
                }}
              >
                {latestData.situation !== null ? formatValue(latestData.situation) : '-'}
              </span>
            </div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.tertiary }}>
              ({formatMonthLabel(latestData.date)})
            </span>
          </div>
          <NextReleaseDisplay nextRelease={data.next_release} />
        </div>
      )}

      {/* 期間セレクター + 比較ボタン */}
      <ChartControlRow
        selectedPeriod={selectedPeriod}
        onPeriodChange={setSelectedPeriod}
        indicatorId="zew_economic_sentiment"
      />

      {/* チャート */}
      <ZoomableChart
        data={filteredData}
        dataKey="sentiment"
        color="#1890ff"
        name="景況感（期待）"
        height={450}
        tickFormatter={formatValue}
        tooltipFormatter={formatValue}
        tooltipLabelFormatter={formatMonthLabel}
        xAxisTickFormatter={formatMonthLabel}
        enableDynamicTicks={true}
        showZeroLine={true}
        showFiftyLine={false}
        connectNulls={true}
        hideLegend={false}
        additionalLines={[
          {
            dataKey: 'situation',
            color: '#52c41a',
            name: '現況',
            strokeWidth: 2,
          },
        ]}
      />
    </>
  )

  return (
    <div id="zew-economic-sentiment-chart">
      <ChartContainer
        title="ZEW景況感指数（ドイツ）"
        showPeriodSelector={false}
        dataSource="ZEW"
        sourceUrl="https://www.zew.de/en/publications/zew-expertises-research-reports/research-reports/business-cycle/zew-financial-market-survey"
      >
        <Tabs
          defaultActiveKey="chart"
          items={[
            {
              key: 'chart',
              label: '時系列',
              children: chartContent,
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="zew_economic_sentiment_index" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
