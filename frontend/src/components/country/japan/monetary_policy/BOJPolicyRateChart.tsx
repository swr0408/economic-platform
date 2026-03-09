/**
 * 日銀政策金利チャートコンポーネント
 *
 * 日本銀行の政策金利の推移を表示
 *
 * データソース:
 * - Bank of Japan
 *
 * 発表スケジュール:
 * - 年8回（金融政策決定会合後）
 * - 発表時刻: 11:30-13:00 JST（変動あり）
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
import { CHART_COLORS, DARK_THEME } from '../../usa/common/chartConstants'

// 型定義
import type { BOJPolicyRateData } from '../../../../hooks/useDashboardData'

interface BOJPolicyRateChartProps {
  data: BOJPolicyRateData | null
}

interface BOJPolicyRateChartData {
  date: string
  value: number
  rate: number
  [key: string]: string | number | null | undefined
}

export default function BOJPolicyRateChart({ data }: BOJPolicyRateChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(2)
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // propsのデータをチャート用に変換
  const policyRateData = useMemo<BOJPolicyRateChartData[]>(() => {
    if (!data?.data || data.data.length === 0) return []

    const chartData: BOJPolicyRateChartData[] = data.data.map((item) => ({
      date: item.date,
      value: item.value,
      rate: item.value,
    }))

    // 日付でソート（古い順）
    chartData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return chartData
  }, [data])

  const formatPercentage = (value: number) => {
    return `${value.toFixed(2)}%`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(policyRateData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  const hasData = policyRateData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="日銀政策金利" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="日銀政策金利" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="boj-policy-rate-chart">
      <ChartContainer
        title="日銀政策金利"
        showPeriodSelector={false}
        dataSource="Bank of Japan"
        sourceUrl="https://www.boj.or.jp/mopo/index.htm"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="現在の金利"
          value={latestValue?.value}
          valueColor={CHART_COLORS.primary}
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
                        onClick={() => window.open('/compare?s=boj_policy_rate', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
                  <ZoomableChart
                    data={filteredData}
                    dataKey="rate"
                    color="#1890ff"
                    name="政策金利"
                    height={450}
                    tickFormatter={formatPercentage}
                    xAxisTickFormatter={formatDateLabel}
                    enableDynamicTicks={true}
                    showZeroLine={true}
                    showFiftyLine={false}
                    connectNulls={true}
                    hideLegend={true}
                    showDefaultTooltip={false}
                    domain={['dataMin - 0.25', 'dataMax + 0.25']}
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
                                      backgroundColor: item.color || '#1890ff',
                                      marginRight: 6,
                                    }}
                                  />
                                  {item.name}
                                </span>
                                <span style={{ fontWeight: 500, color: item.color || '#1890ff' }}>
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
              children: <MarketImpactTab indicatorId="boj_policy_rate" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
