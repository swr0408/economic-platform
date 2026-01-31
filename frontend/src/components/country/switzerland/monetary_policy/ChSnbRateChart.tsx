/**
 * SNB政策金利チャートコンポーネント
 *
 * スイス国立銀行（SNB）政策金利の推移を表示
 *
 * データソース:
 * - Swiss National Bank / FMP経済カレンダー
 *
 * 発表スケジュール:
 * - 不定期（年4回程度、四半期ごと）
 * - 発表時刻: 08:30 チューリッヒ時間（16:30 JST）
 */
import { useState, useMemo } from 'react'
import { Tooltip as RechartsTooltip } from 'recharts'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// 共通モジュールのインポート
import { usePeriodFiltering, formatDateLabel, type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, SimpleLatestValueBox } from '../../usa/common/ChartComponents'
import { DARK_THEME } from '../../usa/common/chartConstants'

// 型定義
import type { ChSnbRateData } from '../../../../hooks/useDashboardData'

interface ChSnbRateChartProps {
  data: ChSnbRateData | null
}

interface ChSnbRateChartData {
  date: string
  value: number
  rate: number
  [key: string]: string | number | null | undefined
}

export default function ChSnbRateChart({ data }: ChSnbRateChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChSnbRateChartData[]>(() => {
    if (!data?.data || data.data.length === 0) return []

    const formattedData: ChSnbRateChartData[] = data.data.map((item: any) => ({
      date: item.date,
      value: item.value,
      rate: item.value,
    }))

    // 日付でソート（古い順）
    formattedData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return formattedData
  }, [data])

  const formatPercentage = (value: number) => {
    return `${value.toFixed(2)}%`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="SNB政策金利" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="SNB政策金利" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ch-snb-rate-chart">
      <ChartContainer
        title="SNB政策金利"
        showPeriodSelector={false}
        dataSource="Swiss National Bank"
        sourceUrl="https://www.snb.ch/en/the-snb/mandates-goals/monetary-policy/decisions"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="現在の金利"
          value={latestValue?.value}
          valueColor="#DC143C"
          date={latestValue?.date}
          nextRelease={data.next_release ? {
            date: data.next_release.date,
            label: data.next_release.time_jst ? `${data.next_release.time_jst} JST` : undefined
          } : null}
          format="percent"
          decimals={2}
        />

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
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
                        onClick={() => window.open('/compare?s=ch_snb_rate', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
                  <ZoomableChart
                    data={filteredData}
                    dataKey="rate"
                    color="#DC143C"
                    name="SNB政策金利"
                    height={450}
                    tickFormatter={formatPercentage}
                    xAxisTickFormatter={formatDateLabel}
                    enableDynamicTicks={true}
                    showZeroLine={true}
                    showFiftyLine={false}
                    connectNulls={true}
                    hideLegend={true}
                    showDefaultTooltip={false}
                    domain={['dataMin - 0.5', 'dataMax + 0.5']}
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
                              {formatDateLabel(String(label))}
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
                                      backgroundColor: item.color || '#DC143C',
                                      marginRight: 6,
                                    }}
                                  />
                                  {item.name}
                                </span>
                                <span style={{ fontWeight: 500, color: item.color || '#DC143C' }}>
                                  {formatPercentage(item.value as number)}
                                </span>
                              </div>
                            ))}
                          </div>
                        )
                      }}
                    />
                  </ZoomableChart>
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="ch_snb_rate" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
