import { useState, useMemo } from 'react'
import { Tabs } from 'antd'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../common/chartConstants'
import { usePeriodFiltering, type PeriodType } from '../common/useChartData'
import { NoDataMessage, PercentageTooltip } from '../common/ChartComponents'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// 寄与度データの型定義
interface GDPContributionItem {
  date: string
  quarter: string
  pce: number | null
  gpdi: number | null
  exports: number | null
  imports: number | null
  government: number | null
  total: number | null
}

interface SeriesInfo {
  series_id: string
  name: string
  name_en: string
  color: string
}

interface GDPContributionsChartProps {
  data: {
    data: GDPContributionItem[]
    series_info: Record<string, SeriesInfo>
  } | null
}

// 寄与度項目の定義
const CONTRIBUTION_ITEMS = [
  { key: 'pce', name: '個人消費 (PCE)', color: '#1890ff' },
  { key: 'gpdi', name: '民間投資 (GPDI)', color: '#52c41a' },
  { key: 'exports', name: '輸出', color: '#722ed1' },
  { key: 'imports', name: '輸入', color: '#fa541c' },
  { key: 'government', name: '政府支出', color: '#faad14' },
]

export default function GDPContributionsChart({ data }: GDPContributionsChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // チャート用データを変換
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    // 日付でソート（古い順）
    const sortedData = [...data.data].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    )

    return sortedData
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="GDP成長率 寄与度" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="GDP成長率 寄与度" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestValue = filteredData.length > 0 ? filteredData[filteredData.length - 1] : null

  const formatPercentage = (value: number | null) => {
    if (value === null || value === undefined) return '-'
    const sign = value >= 0 ? '+' : ''
    return `${sign}${value.toFixed(2)}%`
  }

  return (
    <div id="gdp-contributions-chart">
      <ChartContainer title="GDP成長率 寄与度" showPeriodSelector={false} dataSource="BEA / FRED" sourceUrl="https://www.bea.gov/data/gdp/gross-domestic-product">
        {/* 最新値サマリー */}
        {latestValue && (
          <div style={LATEST_VALUE_BOX_STYLE}>
            <div style={{ marginBottom: 8, width: '100%' }}>
              <span style={{ fontSize: 14, fontWeight: 500, color: TEXT_COLORS.secondary }}>最新: {latestValue.quarter}</span>
            </div>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(5, 1fr)',
                gap: 8,
                fontSize: 12,
                width: '100%',
              }}
            >
              {CONTRIBUTION_ITEMS.map((item) => {
                const value = latestValue[item.key as keyof GDPContributionItem] as number | null
                return (
                  <div
                    key={item.key}
                    style={{
                      textAlign: 'center',
                      padding: '4px 8px',
                      background: 'rgba(255,255,255,0.05)',
                      borderRadius: 4,
                      borderLeft: `3px solid ${item.color}`,
                    }}
                  >
                    <div style={{ color: TEXT_COLORS.secondary, marginBottom: 2 }}>{item.name}</div>
                    <div
                      style={{
                        fontWeight: 500,
                        color: value !== null && value >= 0 ? '#52c41a' : '#ff4d4f',
                      }}
                    >
                      {formatPercentage(value)}
                    </div>
                  </div>
                )
              })}
            </div>
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
                  <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

                  <ResponsiveContainer width="100%" height={450}>
                    <BarChart
                      data={filteredData}
                      margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
                      stackOffset="sign"
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="quarter"
                        tickMargin={10}
                        height={60}
                        interval="preserveStartEnd"
                        angle={-45}
                        textAnchor="end"
                        fontSize={11}
                      />
                      <YAxis
                        tickFormatter={(value) => `${value}%`}
                        domain={['auto', 'auto']}
                        tickMargin={8}
                      />
                      <Tooltip content={<PercentageTooltip />} />
                      <Legend
                        wrapperStyle={{ paddingTop: 20 }}
                        formatter={(value) => <span style={{ fontSize: 12 }}>{value}</span>}
                      />
                      <ReferenceLine y={0} stroke="#000" strokeWidth={1.5} />

                      {CONTRIBUTION_ITEMS.map((item) => (
                        <Bar
                          key={item.key}
                          dataKey={item.key}
                          name={item.name}
                          stackId="contributions"
                          fill={item.color}
                        >
                          {filteredData.map((entry, index) => {
                            const value = entry[item.key as keyof GDPContributionItem] as number | null
                            return (
                              <Cell
                                key={`cell-${index}`}
                                fill={item.color}
                                opacity={value !== null ? 1 : 0}
                              />
                            )
                          })}
                        </Bar>
                      ))}
                    </BarChart>
                  </ResponsiveContainer>
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="gdp_growth" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
