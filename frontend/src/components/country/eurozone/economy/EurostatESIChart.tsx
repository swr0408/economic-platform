/**
 * Eurostat ESI（Economic Sentiment Indicator）チャートコンポーネント
 *
 * Eurostat APIからESIデータを取得し、表示
 *
 * データ:
 * - Euro Area (ユーロ圏)
 * - Germany (ドイツ)
 * - France (フランス)
 * - Italy (イタリア)
 *
 * データソース:
 * - Eurostat - Business and Consumer Surveys
 *
 * 発表スケジュール:
 * - 毎月25日〜翌月8日 18:00 CET
 */
import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import MarketImpactTab from '../../../indicator/MarketImpactTab'
import { Tabs } from 'antd'

import { type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, ChartControlRow, NextReleaseDisplay } from '../../usa/common/ChartComponents'
import { TEXT_COLORS, LATEST_VALUE_BOX_STYLE } from '../../usa/common/chartConstants'

import type { EurostatESIData } from '../../../../hooks/useDashboardData'

interface EurostatESIChartProps {
  data: EurostatESIData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  euro_area: number | null
  germany: number | null
  france: number | null
  italy: number | null
  [key: string]: unknown
}

// 月次形式（2024-01）用のフォーマッター
const formatMonthLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  return dateStr.replace('-', '/')
}

// 月次形式から年を抽出
const getYearFromMonth = (dateStr: string): number => {
  const match = dateStr.match(/^(\d{4})-\d{2}$/)
  return match ? parseInt(match[1], 10) : 0
}

export default function EurostatESIChart({ data }: EurostatESIChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const dateMap = new Map<string, ChartDataPoint>()

    // ユーロ圏データをマージ
    data.euro_area?.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, {
          date: point.date,
          value: null,
          euro_area: null,
          germany: null,
          france: null,
          italy: null,
        })
      }
      const existing = dateMap.get(point.date)!
      existing.euro_area = point.value
      existing.value = point.value // valueフィールドにユーロ圏を設定
    })

    // ドイツデータをマージ
    data.germany?.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, {
          date: point.date,
          value: null,
          euro_area: null,
          germany: null,
          france: null,
          italy: null,
        })
      }
      const existing = dateMap.get(point.date)!
      existing.germany = point.value
    })

    // フランスデータをマージ
    data.france?.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, {
          date: point.date,
          value: null,
          euro_area: null,
          germany: null,
          france: null,
          italy: null,
        })
      }
      const existing = dateMap.get(point.date)!
      existing.france = point.value
    })

    // イタリアデータをマージ
    data.italy?.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, {
          date: point.date,
          value: null,
          euro_area: null,
          germany: null,
          france: null,
          italy: null,
        })
      }
      const existing = dateMap.get(point.date)!
      existing.italy = point.value
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
      startYear = 2020
    } else if (typeof selectedPeriod === 'number') {
      startYear = currentYear - selectedPeriod
    } else {
      startYear = 2020
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
    return <LoadingChart title="ESI（ユーロ圏・主要国）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="ESI（ユーロ圏・主要国）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 値フォーマッター
  const formatValue = (value: number): string => {
    return `${value.toFixed(1)}`
  }

  // チャートコンテンツ
  const chartContent = (
    <>
      {/* 最新値表示 */}
      {latestData && (
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>ユーロ圏: </span>
              <span
                style={{
                  fontSize: 18,
                  fontWeight: 'bold',
                  color: latestData.euro_area && latestData.euro_area >= 100 ? TEXT_COLORS.positive : TEXT_COLORS.negative,
                }}
              >
                {latestData.euro_area !== null ? formatValue(latestData.euro_area) : '-'}
              </span>
            </div>
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>ドイツ: </span>
              <span style={{ fontSize: 14, color: TEXT_COLORS.primary }}>
                {latestData.germany !== null ? formatValue(latestData.germany) : '-'}
              </span>
            </div>
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>フランス: </span>
              <span style={{ fontSize: 14, color: TEXT_COLORS.primary }}>
                {latestData.france !== null ? formatValue(latestData.france) : '-'}
              </span>
            </div>
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>イタリア: </span>
              <span style={{ fontSize: 14, color: TEXT_COLORS.primary }}>
                {latestData.italy !== null ? formatValue(latestData.italy) : '-'}
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
        indicatorId="euro_esi"
      />

      {/* チャート */}
      <ZoomableChart
        data={filteredData}
        dataKey="euro_area"
        color="#1890ff"
        name="ユーロ圏"
        height={450}
        tickFormatter={formatValue}
        tooltipFormatter={formatValue}
        tooltipLabelFormatter={formatMonthLabel}
        xAxisTickFormatter={formatMonthLabel}
        enableDynamicTicks={true}
        showZeroLine={false}
        showFiftyLine={false}
        connectNulls={true}
        hideLegend={false}
        additionalLines={[
          {
            dataKey: 'germany',
            color: '#52c41a',
            name: 'ドイツ',
            strokeWidth: 2,
          },
          {
            dataKey: 'france',
            color: '#faad14',
            name: 'フランス',
            strokeWidth: 2,
          },
          {
            dataKey: 'italy',
            color: '#f5222d',
            name: 'イタリア',
            strokeWidth: 2,
          },
        ]}
      />
    </>
  )

  return (
    <div id="eurostat-esi-chart">
      <ChartContainer
        title="ESI（ユーロ圏・主要国）"
        showPeriodSelector={false}
        dataSource="Eurostat"
        sourceUrl="https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Glossary:Economic_sentiment_indicator_(ESI)"
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
                <MarketImpactTab indicatorId="euro_esi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
