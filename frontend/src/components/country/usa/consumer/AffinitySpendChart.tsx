import { useState, useMemo } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { AffinitySpendData } from '../../../../hooks/useDashboardData'

interface AffinitySpendChartProps {
  data: AffinitySpendData | null
}

export default function AffinitySpendChart({ data }: AffinitySpendChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    if (chartData.length === 0) return []

    if (selectedPeriod === 'all') {
      return chartData
    }

    const cutoffDate = new Date()

    if (selectedPeriod === 'default') {
      cutoffDate.setFullYear(2020, 0, 1)
    } else {
      cutoffDate.setFullYear(cutoffDate.getFullYear() - selectedPeriod)
    }

    return chartData.filter((item) => {
      const itemDate = new Date(item.date)
      return itemDate >= cutoffDate
    })
  }, [chartData, selectedPeriod])

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="Affinityカード支出" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="Affinityカード支出" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  const formatValue = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'N/A'
    const sign = value >= 0 ? '+' : ''
    return `${sign}${value.toFixed(1)}%`
  }

  const formatDateLabel = (dateStr: string): string => {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
  }

  // グラフの色
  const COLORS = {
    value: '#2f54eb',
  }

  const latest = data.latest

  return (
    <div id="affinity-spend">
      <ChartContainer
        title="クレジット / デビットカードカード支出"
        showPeriodSelector={false}
        dataSource="Opportunity Insights Economic Tracker"
        sourceUrl="https://economictracker.org/"
      >
        {/* 最新値表示 */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 12,
            padding: '12px 16px',
            background: '#f5f5f5',
            borderRadius: 8,
            flexWrap: 'wrap',
            gap: 12,
          }}
        >
          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
            {/* 現在値（2020年1月比） */}
            <div>
              <span style={{ fontSize: 12, color: '#666' }}>
                2020年1月比:{' '}
              </span>
              {latest && (
                <span
                  style={{
                    fontSize: 20,
                    fontWeight: 'bold',
                    color: COLORS.value,
                  }}
                >
                  {formatValue(latest.value)}
                </span>
              )}
            </div>
            {/* 日付 */}
            {latest && (
              <span style={{ fontSize: 12, color: '#999', alignSelf: 'center' }}>
                ({latest.date ? formatDateLabel(latest.date) : ''})
              </span>
            )}
          </div>
          <div style={{ fontSize: 11, color: '#888', textAlign: 'right' }}>
            {data.last_commit && (
              <div>
                最終更新: {data.last_commit.date?.split('T')[0] || ''} 
              </div>
            )}
          </div>
        </div>

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

        <ResponsiveContainer width="100%" height={450}>
          <LineChart
            data={filteredData}
            margin={{ top: 20, right: 30, left: 0, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="date"
              tickFormatter={formatDateLabel}
              tick={{ fontSize: 11 }}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={['dataMin - 5', 'dataMax + 5']}
              tick={{ fontSize: 11 }}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip
              labelFormatter={formatDateLabel}
              formatter={(value, name) => {
                const numValue = typeof value === 'number' ? value : null
                if (numValue === null) return ['N/A', name]
                const sign = numValue >= 0 ? '+' : ''
                return [`${sign}${numValue.toFixed(1)}%`, name]
              }}
              contentStyle={{
                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                border: '1px solid #d9d9d9',
                borderRadius: 4,
              }}
            />
            <ReferenceLine y={0} stroke="#000" strokeWidth={1}/>
            <Line
              type="monotone"
              dataKey="value"
              name='クレジット / デビットカードカード支出'
              stroke={COLORS.value}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              connectNulls={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
