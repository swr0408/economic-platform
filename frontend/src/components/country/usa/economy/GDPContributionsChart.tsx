import { useState, useMemo } from 'react'
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
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')

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
  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all' || chartData.length === 0) {
      return chartData
    }

    const cutoffDate = new Date()

    if (selectedPeriod === 'default') {
      // デフォルトは2020年から
      cutoffDate.setFullYear(2020, 0, 1)
    } else {
      // 指定年数前から
      cutoffDate.setFullYear(cutoffDate.getFullYear() - selectedPeriod)
    }

    return chartData.filter((item) => {
      const itemDate = new Date(item.date)
      return itemDate >= cutoffDate
    })
  }, [chartData, selectedPeriod])

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="GDP成長率 寄与度" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="GDP成長率 寄与度" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestValue = filteredData.length > 0 ? filteredData[filteredData.length - 1] : null

  const formatPercentage = (value: number) => {
    if (value === null || value === undefined) return '-'
    const sign = value >= 0 ? '+' : ''
    return `${sign}${value.toFixed(2)}%`
  }

  // カスタムツールチップ
  const CustomTooltip = ({
    active,
    payload,
    label,
  }: {
    active?: boolean
    payload?: Array<{
      name: string
      value: number
      color: string
      dataKey: string
    }>
    label?: string
  }) => {
    if (!active || !payload || payload.length === 0) return null

    return (
      <div
        style={{
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          border: '1px solid #ddd',
          borderRadius: 8,
          padding: '12px 16px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        }}
      >
        <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14 }}>{label}</div>
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
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16 }}>
              <span
                style={{
                  display: 'inline-block',
                  width: 10,
                  height: 10,
                  borderRadius: 2,
                  backgroundColor: item.color,
                  marginRight: 6,
                }}
              />
              {item.name}
            </span>
            <span style={{ fontWeight: 500, color: item.value >= 0 ? '#52c41a' : '#ff4d4f' }}>
              {formatPercentage(item.value)}
            </span>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div id="gdp-contributions-chart">
      <ChartContainer title="GDP成長率 寄与度" showPeriodSelector={false} dataSource="BEA / FRED">
        {/* 最新値サマリー */}
        {latestValue && (
          <div
            style={{
              marginBottom: 16,
              padding: '12px 16px',
              background: '#f5f5f5',
              borderRadius: 8,
            }}
          >
            <div style={{ marginBottom: 8 }}>
              <span style={{ fontSize: 14, fontWeight: 500 }}>最新: {latestValue.quarter}</span>
            </div>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(5, 1fr)',
                gap: 8,
                fontSize: 12,
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
                      background: '#fff',
                      borderRadius: 4,
                      borderLeft: `3px solid ${item.color}`,
                    }}
                  >
                    <div style={{ color: '#666', marginBottom: 2 }}>{item.name}</div>
                    <div
                      style={{
                        fontWeight: 500,
                        color: value !== null && value >= 0 ? '#52c41a' : '#ff4d4f',
                      }}
                    >
                      {formatPercentage(value || 0)}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

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
            <Tooltip content={<CustomTooltip />} />
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
      </ChartContainer>
    </div>
  )
}
