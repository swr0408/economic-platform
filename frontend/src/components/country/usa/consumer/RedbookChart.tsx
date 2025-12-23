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
import type { RedbookData } from '../../../../hooks/useDashboardData'

interface RedbookChartProps {
  data: RedbookData | null
}

export default function RedbookChart({ data }: RedbookChartProps) {
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
      // デフォルトは2020年1月から
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
    return <LoadingChart title="Redbook小売売上高指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="Redbook小売売上高指数" showPeriodSelector={false} showDataSource={false}>
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

  // 週次データなので日付も表示
  const formatDateLabel = (dateStr: string): string => {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`
  }

  // X軸用の簡略表示
  const formatXAxisLabel = (dateStr: string): string => {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
  }

  // グラフの色
  const COLORS = {
    value: '#1890ff',
  }

  const latest = data.latest

  return (
    <div id="redbook">
      <ChartContainer
        title="レッドブック（前年比）"
        showPeriodSelector={false}
        dataSource="Redbook Research"
        sourceUrl="https://www.redbookresearch.com/"
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
            {/* 現在値（前年比） */}
            <div>
              <span style={{ fontSize: 12, color: '#666' }}>
                最新値:{' '}
              </span>
              {latest && (
                <span
                  style={{
                    fontSize: 20,
                    fontWeight: 'bold',
                    color: latest.value >= 0 ? '#52c41a' : '#ff4d4f',
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
            {data.next_release && (
              <div>次回発表: {data.next_release.date}</div>
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
              tickFormatter={formatXAxisLabel}
              tick={{ fontSize: 11 }}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={['dataMin - 2', 'dataMax + 2']}
              tick={{ fontSize: 11 }}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip
              labelFormatter={formatDateLabel}
              formatter={(value, name) => {
                const numValue = typeof value === 'number' ? value : null
                if (numValue === null) return ['N/A', name]
                const sign = numValue >= 0 ? '+' : ''
                return [`${sign}${numValue.toFixed(2)}%`, 'レッドブック（前年比）']
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
              stroke={COLORS.value}
              strokeWidth={2}
              dot={false}
              name="前年比"
              isAnimationActive={false}
              connectNulls={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
