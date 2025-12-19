import { useState, useMemo } from 'react'
import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// GDP項目別成長率データの型定義
interface GDPComponentsGrowthItem {
  date: string
  quarter: string
  pce: number | null
  gpdi: number | null
  exports: number | null
  imports: number | null
  government: number | null
  gdp: number | null
}

interface GDPComponentsGrowthChartProps {
  data: GDPComponentsGrowthItem[] | null
}

// 項目の定義（色・名前）
const COMPONENT_ITEMS = [
  { key: 'pce', name: '個人消費 (PCE)', color: '#1890ff' },
  { key: 'government', name: '政府支出・投資', color: '#722ed1' },
  { key: 'gpdi', name: '民間投資(GPDI)', color: '#faad14' },
  { key: 'imports', name: '輸入', color: '#ff4d4f' },
  { key: 'exports', name: '輸出', color: '#13c2c2' },
]

export default function GDPComponentsGrowthChart({ data }: GDPComponentsGrowthChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')

  // チャート用データを変換（輸入は符号反転）
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return []

    // 日付でソート（古い順）
    const sortedData = [...data].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    )

    // 輸入は符号反転して描画
    return sortedData.map((item) => ({
      ...item,
      imports: item.imports !== null ? -item.imports : null,
    }))
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all' || chartData.length === 0) {
      return chartData
    }

    const cutoffDate = new Date()

    if (selectedPeriod === 'default') {
      // デフォルトは2010年から
      cutoffDate.setFullYear(2010, 0, 1)
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
    return <LoadingChart title="GDP項目別成長率" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="GDP項目別成長率" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  // 最新値を取得（元データから）
  const latestValue = data && data.length > 0
    ? [...data].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())[0]
    : null

  const formatPercentage = (value: number | null) => {
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

    // 日付を四半期形式に変換
    const formatQuarter = (dateStr: string) => {
      const d = new Date(dateStr)
      const q = Math.floor(d.getMonth() / 3) + 1
      return `${d.getFullYear()}Q${q}`
    }

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
        <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14 }}>
          {formatQuarter(label || '')}
        </div>
        {payload.map((item, index) => {
          // 輸入は表示時に符号を戻す
          const displayValue = item.dataKey === 'imports' ? -item.value : item.value
          return (
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
              <span style={{ fontWeight: 500, color: displayValue >= 0 ? '#52c41a' : '#ff4d4f' }}>
                {formatPercentage(displayValue)}
              </span>
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div id="gdp-components-growth-chart">
      <ChartContainer title="GDP項目別成長率" showPeriodSelector={false} dataSource="BEA">
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
              {COMPONENT_ITEMS.map((item) => {
                const value = latestValue[item.key as keyof GDPComponentsGrowthItem] as number | null
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
                      {formatPercentage(value)}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

        <ResponsiveContainer width="100%" height={450}>
          <ComposedChart
            data={filteredData}
            margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
            stackOffset="sign"
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="quarter"
              stroke="#666"
              fontSize={11}
              tickMargin={10}
              interval="preserveStartEnd"
              angle={-45}
              textAnchor="end"
            />
            <YAxis
              stroke="#666"
              fontSize={12}
              tickFormatter={(v) => `${v}%`}
              domain={['auto', 'auto']}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ paddingTop: 20 }}
              formatter={(value) => <span style={{ fontSize: 12 }}>{value}</span>}
            />
            <ReferenceLine y={0} stroke="#000" strokeWidth={1.5} />

            {COMPONENT_ITEMS.map((item) => (
              <Bar
                key={item.key}
                dataKey={item.key}
                name={item.name}
                stackId="total"
                fill={item.color}
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
