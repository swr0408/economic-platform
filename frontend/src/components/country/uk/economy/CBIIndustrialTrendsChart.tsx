/**
 * CBI製造業受注指数チャートコンポーネント
 *
 * CBI Industrial Trends Orders（製造業受注指数）を表示
 *
 * データソース:
 * - Confederation of British Industry (CBI)
 *
 * 発表スケジュール:
 * - 毎月（不定期）19:00-20:00 ロンドン時間
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import { type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, NextReleaseDisplay } from '../../usa/common/ChartComponents'
import { TEXT_COLORS, CHART_COLORS, LATEST_VALUE_BOX_STYLE } from '../../usa/common/chartConstants'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { CBIIndustrialTrendsData } from '../../../../hooks/useDashboardData'

interface CBIIndustrialTrendsChartProps {
  data: CBIIndustrialTrendsData | null
}

interface ChartDataPoint {
  date: string
  value: number
  forecast?: number | null
  previous?: number | null
  [key: string]: unknown
}

// 月ラベルをフォーマット
const formatMonthLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  // "2024-09-01" -> "2024/09"
  const match = dateStr.match(/^(\d{4})-(\d{2})-01$/)
  if (match) {
    return `${match[1]}/${match[2]}`
  }
  return dateStr
}

// 日付から年を抽出
const getYearFromDate = (dateStr: string): number => {
  const match = dateStr.match(/^(\d{4})/)
  return match ? parseInt(match[1], 10) : 0
}

// 値のフォーマット（指数）
const formatValue = (value: number): string => {
  if (value === null || value === undefined) return '-'
  return value.toFixed(0)
}

export default function CBIIndustrialTrendsChart({ data }: CBIIndustrialTrendsChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    const result: ChartDataPoint[] = data.data
      .filter(point => point.value !== null && point.value !== undefined)
      .map(point => ({
        date: point.date,
        value: point.value as number,
        forecast: point.forecast,
        previous: point.previous,
      }))

    result.sort((a, b) => a.date.localeCompare(b.date))
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
      const year = getYearFromDate(item.date)
      return year >= startYear
    })
  }, [chartData, selectedPeriod])

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="CBI製造業受注指数（イギリス）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="CBI製造業受注指数（イギリス）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestValue = filteredData.length > 0 ? filteredData[filteredData.length - 1] : null

  // データ比較用のoverlayConfig ID
  const compareIndicatorId = 'uk_cbi_industrial_trends'
  const marketImpactIndicatorId = 'cbi_industrial_trends'

  return (
    <div id="cbi-industrial-trends-chart">
      <ChartContainer
        title="CBI製造業受注指数"
        showPeriodSelector={false}
        dataSource="Confederation of British Industry (CBI)"
        sourceUrl="https://www.cbi.org.uk/media-centre/?pageSize=12&filter=topic%7CEconomic~&currentFilter=topic"
      >
        {/* 最新値表示（ダークテーマ） */}
        {latestValue && (
          <div style={LATEST_VALUE_BOX_STYLE}>
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>最新値: </span>
              <span
                style={{
                  fontSize: 18,
                  fontWeight: 'bold',
                  color: latestValue.value >= 0 ? TEXT_COLORS.positive : TEXT_COLORS.negative,
                }}
              >
                {formatValue(latestValue.value)}
              </span>
              <span style={{ fontSize: 12, color: TEXT_COLORS.tertiary, marginLeft: 8 }}>
                ({formatMonthLabel(latestValue.date)})
              </span>
            </div>
            <NextReleaseDisplay nextRelease={data.next_release} />
          </div>
        )}

        {/* タブ切替 */}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(`/compare?s=${compareIndicatorId}`, '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <ZoomableChart
                    data={filteredData}
                    dataKey="value"
                    color={CHART_COLORS.primary}
                    name="CBI製造業受注指数"
                    height={450}
                    tickFormatter={formatValue}
                    tooltipFormatter={formatValue}
                    tooltipLabelFormatter={formatMonthLabel}
                    xAxisTickFormatter={formatMonthLabel}
                    enableDynamicTicks={true}
                    showZeroLine={true}
                    showFiftyLine={false}
                    connectNulls={true}
                    hideLegend={true}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId={marketImpactIndicatorId} />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
