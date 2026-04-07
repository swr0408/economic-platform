/**
 * ECB交渉妥結賃金チャートコンポーネント
 *
 * ECB Data APIから交渉妥結賃金データを取得し、表示
 *
 * データ:
 * - Negotiated Wage Rates (交渉妥結賃金) 前年比
 *
 * データソース:
 * - ECB Data API (STS.Q.I9.N.INWR.000000.3.ANR)
 *
 * 発表スケジュール:
 * - 四半期ごと（不定期）
 * - 発表時刻: 18:00-18:10 CET
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { ECBNegotiatedWagesData } from '../../../../hooks/useDashboardData'

interface ECBNegotiatedWagesChartProps {
  data: ECBNegotiatedWagesData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  wages: '#ff7300',
}

/**
 * 四半期形式の日付（2025-Q2）をソート可能な形式に変換
 */
function parseQuarterDate(dateStr: string): Date {
  const match = dateStr.match(/^(\d{4})-Q([1-4])$/)
  if (match) {
    const year = parseInt(match[1], 10)
    const quarter = parseInt(match[2], 10)
    const month = (quarter - 1) * 3
    return new Date(year, month, 1)
  }
  return new Date(dateStr)
}

/**
 * 四半期日付を日本語表記に変換
 */
function formatQuarterDateJP(dateStr: string): string {
  const match = dateStr.match(/^(\d{4})-Q([1-4])$/)
  if (match) {
    const year = match[1]
    const quarter = parseInt(match[2], 10)
    const quarterNames = ['1-3月期', '4-6月期', '7-9月期', '10-12月期']
    return `${year}年${quarterNames[quarter - 1]}`
  }
  return dateStr
}

/**
 * 四半期データを期間でフィルタリング
 */
function filterQuarterlyData<T extends { date: string }>(
  data: T[],
  selectedPeriod: number | 'all' | 'default'
): T[] {
  if (data.length === 0) return []
  if (selectedPeriod === 'all') return data

  const now = new Date()
  let cutoffDate: Date

  if (selectedPeriod === 'default') {
    cutoffDate = new Date(2020, 0, 1)
  } else {
    cutoffDate = new Date(now.getFullYear() - selectedPeriod, now.getMonth(), 1)
  }

  return data.filter((item) => {
    const itemDate = parseQuarterDate(item.date)
    return itemDate >= cutoffDate
  })
}

export default function ECBNegotiatedWagesChart({ data }: ECBNegotiatedWagesChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<number | 'all' | 'default'>(20)

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter(item => item.value !== null)
      .map(item => ({
        date: item.date,
        value: item.value,
      }))
      .sort((a, b) =>
        parseQuarterDate(a.date).getTime() - parseQuarterDate(b.date).getTime()
      )
  }, [data])

  // 期間フィルタリング（四半期データ用）
  const filteredData = useMemo(() =>
    filterQuarterlyData(chartData, currentPeriod),
    [chartData, currentPeriod]
  )

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (!data?.latest) return null
    return data.latest
  }, [data])

  // 次回発表日のフォーマット
  const formatNextRelease = () => {
    if (!data?.next_release) return null
    const nr = data.next_release
    if (nr.datetime_jst) {
      const dt = new Date(nr.datetime_jst)
      return `${dt.getMonth() + 1}/${dt.getDate()} ${dt.getHours().toString().padStart(2, '0')}:${dt.getMinutes().toString().padStart(2, '0')}`
    }
    if (nr.date) {
      const dt = new Date(nr.date)
      return `${dt.getMonth() + 1}/${dt.getDate()}`
    }
    return null
  }

  if (data === null) {
    return <LoadingChart title="交渉妥結賃金（ユーロ圏）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="交渉妥結賃金（ユーロ圏）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ecb-negotiated-wages-chart">
      <ChartContainer
        title="交渉妥結賃金（ユーロ圏・前年比）"
        showPeriodSelector={false}
        dataSource="European Central Bank (ECB)"
        handbookId="ecb-negotiated-wages"
        sourceUrl="https://data.ecb.europa.eu/data/datasets/STS/STS.Q.I9.N.INWR.000000.3.ANR"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={latest?.value}
          valueColor={COLORS.wages}
          date={latest?.date}
          nextRelease={formatNextRelease() ? { date: formatNextRelease()! } : undefined}
          format="percent"
          dateFormatter={formatQuarterDateJP}
        />

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
                  {/* 期間セレクター */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=ecb_negotiated_wages_yoy', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* チャート */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: COLORS.wages, name: '交渉妥結賃金（前年比）' },
                    ]}
                    xAxisFormatter={(date) => date.replace('-', ' ')}
                    tooltipLabelFormatter={formatQuarterDateJP}
                    yAxisFormatter={(v) => `${v}%`}
                    tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
                    yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                    showZeroLine={true}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ecb_negotiated_wages" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
