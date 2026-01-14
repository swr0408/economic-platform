/**
 * Consumer Sentiment Chart Component
 * 消費動向調査（消費者態度指数）チャート
 *
 * データ項目:
 * - cci: 消費者態度指数
 * - livelihood: 暮らし向き
 * - income: 収入の増え方
 * - employment: 雇用環境
 * - durable_goods: 耐久消費財の買い時判断
 */

import { useEffect, useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined, CalendarOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'
import {
  LATEST_VALUE_BOX_STYLE,
  TEXT_COLORS,
} from '../../usa/common/chartConstants'
import {
  fetchConsumerSentimentData,
  type ConsumerSentimentResponse,
  type NextRelease,
} from '../../../../utils/japan/consumerSentimentApi'

interface ConsumerSentimentChartPoint {
  date: string
  value: number // Required by ZoomableChart (maps to cci)
  cci: number | null
  livelihood: number | null
  income: number | null
  employment: number | null
  durable_goods: number | null
  [key: string]: unknown // Index signature for compatibility with ZoomableChart
}

const DEFAULT_PERIOD: PeriodValue = 'default'
const DEFAULT_START_DATE = '2020-01-01'

// グラフの色
const COLORS = {
  cci: '#1890ff',
}

const parseDate = (value: string): Date | null => {
  const normalized = value.length === 7 ? `${value}-01` : value
  const parsed = new Date(normalized)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

const filterByPeriod = (
  data: ConsumerSentimentChartPoint[],
  period: PeriodValue
): ConsumerSentimentChartPoint[] => {
  if (period === 'all') {
    return [...data].sort((a, b) => {
      const dateA = parseDate(a.date)
      const dateB = parseDate(b.date)
      if (!dateA || !dateB) return 0
      return dateA.getTime() - dateB.getTime()
    })
  }

  const now = new Date()
  let startDate: Date

  if (period === 'default') {
    startDate = new Date(DEFAULT_START_DATE)
  } else if (typeof period === 'number') {
    startDate = new Date(now.getFullYear() - period, now.getMonth(), now.getDate())
  } else {
    return data
  }

  return data
    .filter((point) => {
      const pointDate = parseDate(point.date)
      return pointDate && pointDate >= startDate
    })
    .sort((a, b) => {
      const dateA = parseDate(a.date)
      const dateB = parseDate(b.date)
      if (!dateA || !dateB) return 0
      return dateA.getTime() - dateB.getTime()
    })
}

const formatMonthLabel = (dateStr: string): string => {
  const date = parseDate(dateStr)
  if (!date) return dateStr
  const year = date.getFullYear() % 100
  const month = date.getMonth() + 1
  return `'${year.toString().padStart(2, '0')}/${month.toString().padStart(2, '0')}`
}

const formatDateForDisplay = (dateStr: string): string => {
  const date = parseDate(dateStr)
  if (!date) return dateStr
  return `${date.getFullYear()}年${date.getMonth() + 1}月`
}

// 次回発表日時フォーマット関数
const formatNextRelease = (nextRelease: NextRelease | null | undefined): string | null => {
  if (!nextRelease) return null

  // datetime_jstがある場合はそれを使用
  if (nextRelease.datetime_jst) {
    const dt = new Date(nextRelease.datetime_jst)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    const hours = dt.getHours().toString().padStart(2, '0')
    const minutes = dt.getMinutes().toString().padStart(2, '0')
    return `${month}/${day} ${hours}:${minutes}`
  }

  // time_jstがある場合
  if (nextRelease.date && nextRelease.time_jst) {
    const dt = new Date(nextRelease.date)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    return `${month}/${day} ${nextRelease.time_jst}`
  }

  // dateのみの場合
  if (nextRelease.date) {
    const dt = new Date(nextRelease.date)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    return `${month}/${day}`
  }

  return null
}

export default function ConsumerSentimentChart() {
  const [response, setResponse] = useState<ConsumerSentimentResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(DEFAULT_PERIOD)
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true)
        setError(null)
        const res = await fetchConsumerSentimentData()

        if (res.error) {
          setError(res.error)
        } else {
          setResponse(res)
        }
      } catch (err) {
        console.error('Error loading consumer sentiment data:', err)
        setError('データの読み込みに失敗しました')
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [])

  const chartData = useMemo(() => {
    if (!response?.data) return []

    const formatted: ConsumerSentimentChartPoint[] = response.data
      .filter((d) => d.cci !== null)
      .map((d) => ({
        date: d.date,
        value: d.cci ?? 0,
        cci: d.cci,
        livelihood: d.livelihood,
        income: d.income,
        employment: d.employment,
        durable_goods: d.durable_goods,
      }))

    return formatted
  }, [response])

  const filteredData = useMemo(() => {
    return filterByPeriod(chartData, selectedPeriod)
  }, [chartData, selectedPeriod])

  const handlePeriodChange = (period: PeriodValue) => {
    setSelectedPeriod(period)
  }

  if (loading) {
    return <LoadingChart title="消費動向調査" />
  }

  if (error) {
    return (
      <ChartContainer title="消費動向調査" showDataSource={false} showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>{error}</div>
      </ChartContainer>
    )
  }

  const hasData = chartData.length > 0
  const showChart = hasData && filteredData.length > 0

  if (!hasData) {
    return (
      <ChartContainer title="消費動向調査" showDataSource={false} showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latest = response?.latest

  return (
    <div id="japan-consumer-sentiment-chart">
      <ChartContainer
        title="消費動向調査"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="内閣府"
        sourceUrl="https://www.esri.cao.go.jp/jp/stat/shouhi/shouhi.html"
      >
        {/* 最新値表示（統合ボックス） */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          {/* 左側: 最新値 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {/* 日付 */}
            {latest?.date && (
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                {formatDateForDisplay(latest.date)}
              </span>
            )}
            {/* 消費者態度指数 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>消費者態度指数:</span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.cci }}>
                {latest?.cci?.toFixed(1) ?? '-'}
              </span>
            </div>
          </div>

          {/* 右側: 次回発表 */}
          {response?.next_release && formatNextRelease(response.next_release) && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 12,
              color: TEXT_COLORS.secondary,
            }}>
              <CalendarOutlined />
              <span>次回発表: {formatNextRelease(response.next_release)}</span>
            </div>
          )}
        </div>

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
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: 8,
                    }}
                  >
                    <PeriodSelector
                      onPeriodChange={handlePeriodChange}
                      selectedPeriod={selectedPeriod}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=japan_consumer_sentiment', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
                  {showChart && (
                    <ZoomableChart
                      data={filteredData}
                      dataKey="cci"
                      name="消費者態度指数"
                      color={COLORS.cci}
                      height={400}
                      strokeWidth={2.5}
                      xAxisTickFormatter={formatMonthLabel}
                      domain={['dataMin - 2', 'dataMax + 2']}
                      showZeroLine={false}
                      showFiftyLine={true}
                      fiftyLineValue={50}
                      connectNulls={true}
                      enableDynamicTicks={true}
                      initialHiddenLines={['livelihood', 'income', 'employment', 'durable_goods']}
                      tooltipFormatter={(value: number) => `${value.toFixed(1)}`}
                      tooltipLabelFormatter={(label: string) => {
                        const date = parseDate(String(label))
                        if (!date) return label
                        return `${date.getFullYear()}年${date.getMonth() + 1}月`
                      }}
                      additionalLines={[
                        {
                          dataKey: 'livelihood',
                          color: '#52c41a',
                          name: '暮らし向き',
                          strokeWidth: 2,
                        },
                        {
                          dataKey: 'income',
                          color: '#faad14',
                          name: '収入の増え方',
                          strokeWidth: 2,
                        },
                        {
                          dataKey: 'employment',
                          color: '#722ed1',
                          name: '雇用環境',
                          strokeWidth: 2,
                        },
                        {
                          dataKey: 'durable_goods',
                          color: '#eb2f96',
                          name: '耐久消費財の買い時判断',
                          strokeWidth: 2,
                        },
                      ]}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="japan_consumer_sentiment" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
