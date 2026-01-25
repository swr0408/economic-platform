/**
 * IFO企業景況感指数チャートコンポーネント
 *
 * データ:
 * - Geschäftsklima (Business Climate / 景況感): 企業の景況感総合指数
 * - Geschäftslage (Current Conditions / 現況): 現在の経済状況の評価
 * - Geschäftserwartungen (Expectations / 期待): 6ヶ月先の経済見通し
 *
 * データソース:
 * - IFO研究所
 * - FMP economic_calendar_events
 *
 * 発表スケジュール:
 * - 月次（毎月第4週前後 10:00 CET）
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

import type { IfoBusinessClimateData } from '../../../../hooks/useDashboardData'

interface IfoBusinessClimateChartProps {
  data: IfoBusinessClimateData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  climate: number | null
  current: number | null
  expectations: number | null
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

export default function IfoBusinessClimateChart({ data }: IfoBusinessClimateChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const dateMap = new Map<string, ChartDataPoint>()

    // 景況感（総合）データをマージ
    data.climate?.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, {
          date: point.date,
          value: null,
          climate: null,
          current: null,
          expectations: null,
        })
      }
      const existing = dateMap.get(point.date)!
      existing.climate = point.value
      existing.value = point.value // valueフィールドに景況感を設定
    })

    // 現況データをマージ
    data.current?.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, {
          date: point.date,
          value: null,
          climate: null,
          current: null,
          expectations: null,
        })
      }
      const existing = dateMap.get(point.date)!
      existing.current = point.value
    })

    // 期待データをマージ
    data.expectations?.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, {
          date: point.date,
          value: null,
          climate: null,
          current: null,
          expectations: null,
        })
      }
      const existing = dateMap.get(point.date)!
      existing.expectations = point.value
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
    return <LoadingChart title="IFO企業景況感指数（ドイツ）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="IFO企業景況感指数（ドイツ）" showPeriodSelector={false} showDataSource={false}>
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
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>景況感: </span>
              <span
                style={{
                  fontSize: 18,
                  fontWeight: 'bold',
                  color: TEXT_COLORS.primary,
                }}
              >
                {latestData.climate !== null ? formatValue(latestData.climate) : '-'}
              </span>
            </div>
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>現況: </span>
              <span style={{ fontSize: 14, color: TEXT_COLORS.primary }}>
                {latestData.current !== null ? formatValue(latestData.current) : '-'}
              </span>
            </div>
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>期待: </span>
              <span style={{ fontSize: 14, color: TEXT_COLORS.primary }}>
                {latestData.expectations !== null ? formatValue(latestData.expectations) : '-'}
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
        indicatorId="ifo_business_climate"
      />

      {/* チャート */}
      <ZoomableChart
        data={filteredData}
        dataKey="climate"
        color="#1890ff"
        name="景況感"
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
            dataKey: 'current',
            color: '#52c41a',
            name: '現況',
            strokeWidth: 2,
          },
          {
            dataKey: 'expectations',
            color: '#faad14',
            name: '期待',
            strokeWidth: 2,
          },
        ]}
      />
    </>
  )

  return (
    <div id="ifo-business-climate-chart">
      <ChartContainer
        title="IFO企業景況感指数（ドイツ）"
        showPeriodSelector={false}
        dataSource="IFO"
        sourceUrl="https://www.ifo.de/fakten/2025-12-17/ifo-geschaeftsklimaindex-gesunken-dezember-2025"
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
                <MarketImpactTab indicatorId="ifo_business_climate" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
