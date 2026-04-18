/**
 * SONIA（Sterling Overnight Index Average）チャートコンポーネント
 *
 * 英国のオーバーナイト金利ベンチマーク（SONIA）の推移を表示
 *
 * データソース:
 * - Bank of England Statistical Database
 *
 * 発表スケジュール:
 * - 日次
 * - ロンドン9:00（夏時間: 17:00 JST、冬時間: 18:00 JST）
 */
import { useState, useMemo, useEffect } from 'react'
import { Tooltip as RechartsTooltip } from 'recharts'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import { usePeriodFiltering, formatDateLabel, type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, SimpleLatestValueBox } from '../../usa/common/ChartComponents'
import { CHART_COLORS, DARK_THEME } from '../../usa/common/chartConstants'

// 型定義
interface SONIADataPoint {
  date: string
  value: number
}

interface SONIAApiResponse {
  data: SONIADataPoint[]
  latest?: SONIADataPoint | null
  next_release?: {
    date?: string
    time_london?: string
    time_jst?: string
    datetime_jst?: string
  } | null
  last_updated?: string
  cached?: boolean
  source?: string
  error?: string
}

interface SONIAChartData {
  date: string
  value: number
  rate: number
  [key: string]: string | number | null | undefined
}

export default function SONIAChart() {
  const [data, setData] = useState<SONIAApiResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(2)

  useEffect(() => {
    let isSubscribed = true

    const loadData = () => {
      setLoading(true)

      fetch('/api/uk/sonia')
        .then((response) => {
          if (!response.ok) {
            throw new Error(`Failed to fetch SONIA data: ${response.statusText}`)
          }
          return response.json()
        })
        .then((responseData: SONIAApiResponse) => {
          if (isSubscribed) {
            setData(responseData)
          }
        })
        .catch((err) => {
          console.error('Failed to load SONIA data:', err)
        })
        .finally(() => {
          if (isSubscribed) {
            setLoading(false)
          }
        })
    }

    loadData()

    return () => {
      isSubscribed = false
    }
  }, [])

  // APIデータをチャート用に変換
  const chartData = useMemo<SONIAChartData[]>(() => {
    if (!data?.data || data.data.length === 0) return []

    const formattedData: SONIAChartData[] = data.data.map((item) => ({
      date: item.date,
      value: item.value,
      rate: item.value,
    }))

    // 日付でソート（古い順）
    formattedData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return formattedData
  }, [data])

  const formatPercentage = (value: number) => {
    return `${value.toFixed(4)}%`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // ローディング状態
  if (loading) {
    return <LoadingChart title="SONIA" />
  }

  // データなし
  if (!hasData) {
    return (
      <ChartContainer title="SONIA" showPeriodSelector={false} showDataSource={false} handbookId="sonia">
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="sonia-chart">
      <ChartContainer
        title="SONIA（Sterling Overnight Index Average）"
        showPeriodSelector={false}
        dataSource="Bank of England"
        sourceUrl="https://www.bankofengland.co.uk/markets/sonia-benchmark"
        handbookId="sonia"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="SONIA"
          value={latestValue?.value}
          valueColor={CHART_COLORS.primary}
          date={latestValue?.date}
          nextRelease={data?.next_release?.date ? {
            date: data.next_release.date,
            label: data.next_release.time_jst ? `${data.next_release.time_jst} JST` : undefined
          } : null}
          format="percent"
          decimals={4}
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=uk_sonia&s=uk_boe_bank_rate', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>
        <ZoomableChart
          data={filteredData}
          dataKey="rate"
          color="#1659f7"
          name="SONIA"
          height={450}
          tickFormatter={formatPercentage}
          xAxisTickFormatter={formatDateLabel}
          enableDynamicTicks={true}
          showZeroLine={true}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={true}
          showDefaultTooltip={false}
          domain={['dataMin - 0.1', 'dataMax + 0.1']}
        >
          <RechartsTooltip
            content={({ active, payload, label }) => {
              if (!active || !payload || payload.length === 0) return null
              return (
                <div
                  style={{
                    backgroundColor: DARK_THEME.bgTertiary,
                    border: `1px solid ${DARK_THEME.borderLight}`,
                    borderRadius: 8,
                    padding: '12px 16px',
                    boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
                  }}
                >
                  <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
                    {String(label).replace(/-/g, '/')}
                  </div>
                  {payload.map((item, index) => (
                    <div
                      key={index}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: 4,
                        fontSize: 13,
                      }}
                    >
                      <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
                        <span
                          style={{
                            display: 'inline-block',
                            width: 10,
                            height: 10,
                            borderRadius: 2,
                            backgroundColor: item.color || '#1659f7',
                            marginRight: 6,
                          }}
                        />
                        {item.name}
                      </span>
                      <span style={{ fontWeight: 500, color: item.color || '#1659f7' }}>
                        {formatPercentage(item.value as number)}
                      </span>
                    </div>
                  ))}
                </div>
              )
            }}
          />
        </ZoomableChart>
      </ChartContainer>
    </div>
  )
}
