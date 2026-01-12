/**
 * BOJ Consumption Activity Index (CAI) Chart Component
 * 消費活動指数（旅行収支調整前）チャート
 *
 * データ項目:
 * - nominal_cai: 名目消費活動指数
 * - real_cai: 実質消費活動指数
 */

import { useEffect, useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'
import { SimpleLatestValueBox } from '../../usa/common/ChartComponents'
import { fetchBOJCAIData, type BOJCAIResponse } from '../../../../utils/japan/bojCAIApi'

interface CAIChartDataPoint {
  date: string
  value: number
  nominal_cai: number | undefined
  real_cai: number | undefined
  [key: string]: unknown
}

const DEFAULT_PERIOD: PeriodValue = 'default'
const DEFAULT_START_DATE = '2020-01-01'

// グラフの色
const COLORS = {
  nominal: '#1890ff',
  real: '#52c41a',
}

const parseDate = (value: string): Date | null => {
  const normalized = value.length === 7 ? `${value}-01` : value
  const parsed = new Date(normalized)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

const filterByPeriod = (data: CAIChartDataPoint[], period: PeriodValue): CAIChartDataPoint[] => {
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

export default function BOJCAIChart() {
  const [response, setResponse] = useState<BOJCAIResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(DEFAULT_PERIOD)
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true)
        setError(null)
        const res = await fetchBOJCAIData()

        if (res.error) {
          setError(res.error)
        } else {
          setResponse(res)
        }
      } catch (err) {
        console.error('Error loading BOJ CAI data:', err)
        setError('データの読み込みに失敗しました')
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [])

  const chartData = useMemo(() => {
    if (!response?.data) return []

    const formatted: CAIChartDataPoint[] = response.data
      .filter((d) => d.nominal_cai !== null || d.real_cai !== null)
      .map((d) => ({
        date: d.date,
        value: d.nominal_cai ?? d.real_cai ?? 0,
        nominal_cai: d.nominal_cai ?? undefined,
        real_cai: d.real_cai ?? undefined,
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
    return <LoadingChart title="消費活動指数（旅行収支調整前）" />
  }

  if (error) {
    return (
      <ChartContainer
        title="消費活動指数（旅行収支調整前）"
        showDataSource={false}
        showPeriodSelector={false}
      >
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>{error}</div>
      </ChartContainer>
    )
  }

  const hasData = chartData.length > 0
  const showChart = hasData && filteredData.length > 0

  if (!hasData) {
    return (
      <ChartContainer
        title="消費活動指数（旅行収支調整前）"
        showDataSource={false}
        showPeriodSelector={false}
      >
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latest = response?.latest

  return (
    <div id="japan-boj-cai-chart">
      <ChartContainer
        title="消費活動指数（旅行収支調整前）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="日本銀行"
        sourceUrl="https://www.boj.or.jp/research/research_data/cai/index.htm"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="名目"
          value={latest?.nominal_cai}
          valueColor={COLORS.nominal}
          subLabel="実質"
          subValue={latest?.real_cai}
          subValueColor={COLORS.real}
          date={latest?.date}
          dateFormatter={formatDateForDisplay}
          format="number"
          decimals={2}
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
                        onClick={() => window.open('/compare?s=japan_boj_cai_nominal', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
                  {showChart && (
                    <ZoomableChart
                      data={filteredData}
                      dataKey="nominal_cai"
                      name="名目消費活動指数"
                      color={COLORS.nominal}
                      height={400}
                      strokeWidth={2.5}
                      xAxisTickFormatter={formatMonthLabel}
                      domain={['dataMin - 2', 'dataMax + 2']}
                      showZeroLine={false}
                      showFiftyLine={false}
                      connectNulls={true}
                      enableDynamicTicks={true}
                      tooltipFormatter={(value: number) => `${value.toFixed(2)}`}
                      tooltipLabelFormatter={(label: string) => {
                        const date = parseDate(String(label))
                        if (!date) return label
                        return `${date.getFullYear()}年${date.getMonth() + 1}月`
                      }}
                      additionalLines={[
                        {
                          dataKey: 'real_cai',
                          color: COLORS.real,
                          name: '実質消費活動指数',
                          strokeWidth: 2,
                        },
                      ]}
                    />
                  )}
                </>
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
