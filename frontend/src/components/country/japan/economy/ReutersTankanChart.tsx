/**
 * ロイター短観チャートコンポーネント
 *
 * 製造業ロイター短観: FMP + DB + 手動CSV
 * 非製造業ロイター短観: 手動CSV
 *
 * データソース: Reuters
 * 発表スケジュール: 月次
 */
import { useState, useMemo, useEffect } from 'react'
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
  fetchReutersTankanData,
  type ReutersTankanResponse,
  type ReutersTankanNextRelease,
} from '../../../../utils/japan/reutersTankanApi'

interface ChartDataPoint {
  date: string
  value: number | null
  manufacturing: number | null
  non_manufacturing: number | null
  [key: string]: unknown
}

const COLORS = {
  manufacturing: '#1890ff',
  non_manufacturing: '#fa8c16',
}

const DEFAULT_PERIOD: PeriodValue = 'default'
const DEFAULT_START_DATE = '2015-01-01'

const parseDate = (value: string): Date | null => {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

const filterByPeriod = (
  data: ChartDataPoint[],
  period: PeriodValue
): ChartDataPoint[] => {
  const sorted = [...data].sort((a, b) => {
    const dateA = parseDate(a.date)
    const dateB = parseDate(b.date)
    if (!dateA || !dateB) return 0
    return dateA.getTime() - dateB.getTime()
  })

  if (period === 'all') return sorted

  const now = new Date()
  let startDate: Date
  if (period === 'default') {
    startDate = new Date(DEFAULT_START_DATE)
  } else if (typeof period === 'number') {
    startDate = new Date(now.getFullYear() - period, now.getMonth(), now.getDate())
  } else {
    return sorted
  }

  return sorted.filter((point) => {
    const pointDate = parseDate(point.date)
    return pointDate && pointDate >= startDate
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

const formatNextRelease = (nextRelease: ReutersTankanNextRelease | null | undefined): string | null => {
  if (!nextRelease) return null

  if (nextRelease.datetime_jst) {
    const dt = new Date(nextRelease.datetime_jst)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    const hours = dt.getHours().toString().padStart(2, '0')
    const minutes = dt.getMinutes().toString().padStart(2, '0')
    return `${month}/${day} ${hours}:${minutes}`
  }

  if (nextRelease.date && nextRelease.time_jst) {
    const dt = new Date(nextRelease.date)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    return `${month}/${day} ${nextRelease.time_jst}`
  }

  if (nextRelease.date) {
    const dt = new Date(nextRelease.date)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    return `${month}/${day}`
  }

  return null
}

export default function ReutersTankanChart() {
  const [response, setResponse] = useState<ReutersTankanResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(DEFAULT_PERIOD)
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true)
        setError(null)
        const res = await fetchReutersTankanData()
        if (res.error) {
          setError(res.error)
        } else {
          setResponse(res)
        }
      } catch (err) {
        console.error('Error loading Reuters Tankan data:', err)
        setError('データの読み込みに失敗しました')
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [])

  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!response) return []

    const mfgData = response.manufacturing?.data || []
    const nonMfgData = response.non_manufacturing?.data || []

    const allDates = new Set<string>()
    mfgData.forEach((d) => allDates.add(d.date))
    nonMfgData.forEach((d) => allDates.add(d.date))

    const sortedDates = Array.from(allDates).sort(
      (a, b) => new Date(a).getTime() - new Date(b).getTime()
    )

    const mfgMap = new Map(mfgData.map((d) => [d.date, d.value]))
    const nonMfgMap = new Map(nonMfgData.map((d) => [d.date, d.value]))

    return sortedDates.map((date) => ({
      date,
      value: mfgMap.get(date) ?? null,
      manufacturing: mfgMap.get(date) ?? null,
      non_manufacturing: nonMfgMap.get(date) ?? null,
    }))
  }, [response])

  const filteredData = useMemo(() => filterByPeriod(chartData, selectedPeriod), [chartData, selectedPeriod])

  const mfgLatest = response?.manufacturing?.latest
  const nonMfgLatest = response?.non_manufacturing?.latest

  const hasData = chartData.length > 0
  const showChart = hasData && filteredData.length > 0

  if (loading) {
    return <LoadingChart title="ロイター短観" />
  }

  if (error) {
    return (
      <ChartContainer title="ロイター短観" showDataSource={false} showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>{error}</div>
      </ChartContainer>
    )
  }

  if (!hasData) {
    return (
      <ChartContainer title="ロイター短観" showDataSource={false} showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  const compareUrl = '/compare?s=reuters_tankan'

  return (
    <div id="reuters-tankan">
      <ChartContainer
        title="ロイター短観"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="Reuters"
        sourceUrl="https://jp.reuters.com/"
      >
        {/* 最新値表示 */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {mfgLatest?.date && (
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                {formatDateForDisplay(mfgLatest.date)}
              </span>
            )}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>製造業:</span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.manufacturing }}>
                {mfgLatest?.value?.toFixed(0) ?? '-'}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>非製造業:</span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.non_manufacturing }}>
                {nonMfgLatest?.value?.toFixed(0) ?? '-'}
              </span>
            </div>
          </div>

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
                      onPeriodChange={setSelectedPeriod}
                      selectedPeriod={selectedPeriod}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(compareUrl, '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {showChart && (
                    <ZoomableChart
                      data={filteredData}
                      dataKey="manufacturing"
                      name="製造業"
                      color={COLORS.manufacturing}
                      height={400}
                      strokeWidth={2.5}
                      xAxisTickFormatter={formatMonthLabel}
                      domain={['dataMin - 1', 'dataMax + 1']}
                      showZeroLine={true}
                      zeroLineValue={0}
                      connectNulls={true}
                      tooltipFormatter={(value: number) => `${value.toFixed(0)}`}
                      tooltipLabelFormatter={(label: string) => {
                        const date = parseDate(String(label))
                        if (!date) return label
                        return `${date.getFullYear()}年${date.getMonth() + 1}月`
                      }}
                      yAxisLabel="DI"
                      additionalLines={[
                        {
                          dataKey: 'non_manufacturing',
                          color: COLORS.non_manufacturing,
                          name: '非製造業',
                          strokeWidth: 2.5,
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
              children: <MarketImpactTab indicatorId="reuters_tankan" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
