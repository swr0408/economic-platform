/**
 * 政策金利チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
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
import { usePeriodFiltering, formatDateLabel, type PeriodType } from '../common/useChartData'
import { NoDataMessage, SimpleLatestValueBox } from '../common/ChartComponents'
import { CHART_COLORS, DARK_THEME } from '../common/chartConstants'

// Props型定義
interface PolicyRateItem {
  date: string
  rate: number
}

interface NextFomcInfo {
  date: string
  label: string
  has_sep: boolean
}

interface PolicyRateChartProps {
  data: PolicyRateItem[] | null
  nextFomc?: NextFomcInfo | null
}

interface PolicyRateChartData {
  date: string
  value: number
  rate: number
  [key: string]: string | number | null | undefined
}

export default function PolicyRateChart({ data, nextFomc }: PolicyRateChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(2)
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // propsのデータをチャート用に変換
  const policyRateData = useMemo<PolicyRateChartData[]>(() => {
    if (!data || data.length === 0) return []

    const chartData: PolicyRateChartData[] = data.map((item) => ({
      date: item.date,
      value: item.rate,
      rate: item.rate,
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
    defaultStartYear: 2020,
  })

  const hasData = policyRateData.length > 0

  // 最新値を取得
  const latestValue = filteredData.length > 0 ? filteredData[filteredData.length - 1] : null

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="政策金利" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="政策金利" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="policy-rate-chart">
      <ChartContainer
        title="政策金利"
        showPeriodSelector={false}
        dataSource="Federal Reserve"
        sourceUrl="https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="現在の金利"
          value={latestValue?.rate}
          valueColor={CHART_COLORS.primary}
          date={latestValue?.date}
          nextRelease={nextFomc ? { date: nextFomc.date, label: nextFomc.has_sep ? 'SEP発表あり' : undefined } : null}
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
                        onClick={() => window.open('/compare?s=policy_rate', '_blank')}
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
              children: <MarketImpactTab indicatorId="policy_rate" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
