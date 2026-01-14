/**
 * Economy Watcher Survey Chart Component
 * 景気ウォッチャー調査チャート（現状判断DIと先行き判断DIをタブで切り替え）
 *
 * データ項目:
 * - total: 合計
 * - household: 家計動向関連
 * - corporate: 企業動向関連
 * - employment: 雇用関連
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
  fetchEconomyWatcherData,
  type EconomyWatcherFullResponse,
  type EconomyWatcherDataPoint,
  type NextRelease,
} from '../../../../utils/japan/economyWatcherApi'

interface EconomyWatcherChartPoint {
  date: string
  value: number
  total: number | null
  household: number | null
  corporate: number | null
  employment: number | null
  [key: string]: unknown
}

type DataType = 'current' | 'outlook'

const DEFAULT_PERIOD: PeriodValue = 'default'
const DEFAULT_START_DATE = '2020-01-01'

const COLORS = {
  total: '#1890ff',
  household: '#52c41a',
  corporate: '#faad14',
  employment: '#722ed1',
}

const parseDate = (value: string): Date | null => {
  const normalized = value.length === 7 ? `${value}-01` : value
  const parsed = new Date(normalized)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

const filterByPeriod = (
  data: EconomyWatcherChartPoint[],
  period: PeriodValue
): EconomyWatcherChartPoint[] => {
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

const transformToChartData = (data: EconomyWatcherDataPoint[]): EconomyWatcherChartPoint[] => {
  return data
    .filter((d) => d.total !== null)
    .map((d) => ({
      date: d.date,
      value: d.total ?? 0,
      total: d.total,
      household: d.household,
      corporate: d.corporate,
      employment: d.employment,
    }))
}

export default function EconomyWatcherChart() {
  const [response, setResponse] = useState<EconomyWatcherFullResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(DEFAULT_PERIOD)
  const [dataType, setDataType] = useState<DataType>('current')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true)
        setError(null)
        const res = await fetchEconomyWatcherData()

        if (res.error) {
          setError(res.error)
        } else {
          setResponse(res)
        }
      } catch (err) {
        console.error('Error loading Economy Watcher data:', err)
        setError('データの読み込みに失敗しました')
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [])

  const currentChartData = useMemo(() => {
    if (!response?.current?.data) return []
    return transformToChartData(response.current.data)
  }, [response])

  const outlookChartData = useMemo(() => {
    if (!response?.outlook?.data) return []
    return transformToChartData(response.outlook.data)
  }, [response])

  const chartData = dataType === 'current' ? currentChartData : outlookChartData
  const latest = dataType === 'current' ? response?.current?.latest : response?.outlook?.latest

  const filteredData = useMemo(() => {
    return filterByPeriod(chartData, selectedPeriod)
  }, [chartData, selectedPeriod])

  const handlePeriodChange = (period: PeriodValue) => {
    setSelectedPeriod(period)
  }

  const handleDataTypeChange = (type: DataType) => {
    setDataType(type)
  }

  if (loading) {
    return <LoadingChart title="景気ウォッチャー調査" />
  }

  if (error) {
    return (
      <ChartContainer title="景気ウォッチャー調査" showDataSource={false} showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>{error}</div>
      </ChartContainer>
    )
  }

  const hasData = chartData.length > 0
  const showChart = hasData && filteredData.length > 0

  if (!hasData) {
    return (
      <ChartContainer title="景気ウォッチャー調査" showDataSource={false} showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  const indicatorId = dataType === 'current' ? 'japan_economy_watcher_current' : 'japan_economy_watcher_outlook'
  const compareUrl = `/compare?s=${indicatorId}`

  return (
    <div id="japan-economy-watcher-chart">
      <ChartContainer
        title="景気ウォッチャー調査"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="内閣府"
        sourceUrl="https://www5.cao.go.jp/keizai3/watcher/watcher_menu.html"
      >
        {/* データタイプ切り替えタブ */}
        <Tabs
          activeKey={dataType}
          onChange={(key) => handleDataTypeChange(key as DataType)}
          style={{ marginBottom: 0 }}
          items={[
            { key: 'current', label: '現状判断DI' },
            { key: 'outlook', label: '先行き判断DI' },
          ]}
        />

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
            {/* 合計 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>合計:</span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.total }}>
                {latest?.total?.toFixed(1) ?? '-'}
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

        {/* 内部タブ（時系列・マーケットインパクト） */}
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
                        onClick={() => window.open(compareUrl, '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
                  {showChart && (
                    <ZoomableChart
                      data={filteredData}
                      dataKey="total"
                      name="合計"
                      color={COLORS.total}
                      height={400}
                      strokeWidth={2.5}
                      xAxisTickFormatter={formatMonthLabel}
                      domain={['dataMin - 2', 'dataMax + 2']}
                      showZeroLine={false}
                      showFiftyLine={true}
                      fiftyLineValue={50}
                      connectNulls={true}
                      enableDynamicTicks={true}
                      initialHiddenLines={['household', 'corporate', 'employment']}
                      tooltipFormatter={(value: number) => `${value.toFixed(1)}`}
                      tooltipLabelFormatter={(label: string) => {
                        const date = parseDate(String(label))
                        if (!date) return label
                        return `${date.getFullYear()}年${date.getMonth() + 1}月`
                      }}
                      additionalLines={[
                        {
                          dataKey: 'household',
                          color: COLORS.household,
                          name: '家計動向関連',
                          strokeWidth: 2,
                        },
                        {
                          dataKey: 'corporate',
                          color: COLORS.corporate,
                          name: '企業動向関連',
                          strokeWidth: 2,
                        },
                        {
                          dataKey: 'employment',
                          color: COLORS.employment,
                          name: '雇用関連',
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
              children: <MarketImpactTab indicatorId={indicatorId} />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
