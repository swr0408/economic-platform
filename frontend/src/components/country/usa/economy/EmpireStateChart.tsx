import { useState, useMemo } from 'react'
import {
  LineChart,
  Line,
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
import type { EmpireStateData } from '../../../../hooks/useDashboardData'

interface EmpireStateChartProps {
  data: EmpireStateData | null
}

// シリーズ設定
const SERIES_CONFIG = {
  current: {
    name: '現況指数',
    color: '#1890ff',
    strokeWidth: 2,
  },
  future: {
    name: '期待指数',
    color: '#fa541c',
    strokeWidth: 2,
  },
}

export default function EmpireStateChart({ data }: EmpireStateChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')
  const [hiddenSeries, setHiddenSeries] = useState<Set<string>>(new Set(['future']))

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        current: item.current,
        future: item.future,
      }))
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
    return <LoadingChart title="NY連銀製造業景気指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="NY連銀製造業景気指数" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  const formatValue = (value: number | null) => {
    if (value === null) return 'N/A'
    return value.toFixed(1)
  }

  const formatDateLabel = (dateStr: string): string => {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
  }

  // 凡例クリックで表示/非表示を切り替え
  const handleLegendClick = (dataKey: string) => {
    setHiddenSeries((prev) => {
      const next = new Set(prev)
      if (next.has(dataKey)) {
        next.delete(dataKey)
      } else {
        next.add(dataKey)
      }
      return next
    })
  }

  // 最新値を取得
  const latestData = data.latest
  const latestCurrent = latestData?.current ?? null
  const latestFuture = latestData?.future ?? null

  return (
    <div id="empire-state-chart">
      <ChartContainer
        title="NY連銀製造業景気指数"
        showPeriodSelector={false}
        dataSource="Federal Reserve Bank of New York / FRED"
        sourceUrl="https://www.newyorkfed.org/survey/empire/empiresurvey_overview"
      >
        {/* 最新値表示 */}
        {latestData && (
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 12,
              padding: '8px 12px',
              background: '#f5f5f5',
              borderRadius: 8,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
              <div>
                <span style={{ fontSize: 12, color: '#666' }}>最新値: </span>
                <span
                  style={{
                    fontSize: 18,
                    fontWeight: 'bold',
                    color: '#1890ff',
                  }}
                >
                  {formatValue(latestCurrent)}
                </span>
                <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>
                  ({formatDateLabel(latestData.date)})
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: 2,
                    backgroundColor: SERIES_CONFIG.future.color,
                    display: 'inline-block',
                  }}
                />
                <span style={{ fontSize: 11, color: '#666' }}>期待指数:</span>
                <span style={{ fontSize: 13, fontWeight: 'bold', color: SERIES_CONFIG.future.color }}>
                  {formatValue(latestFuture)}
                </span>
              </div>
            </div>
            {data.next_release && (
              <div style={{ fontSize: 11, color: '#666', textAlign: 'right' }}>
                <div>次回発表: {data.next_release.date}</div>
              </div>
            )}
          </div>
        )}

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
              tickFormatter={(v) => v.toFixed(0)}
            />
            <Tooltip
              labelFormatter={formatDateLabel}
              formatter={(value, name) => {
                const numValue = typeof value === 'number' ? value : null
                return [numValue !== null ? numValue.toFixed(1) : 'N/A', name]
              }}
              contentStyle={{
                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                border: '1px solid #d9d9d9',
                borderRadius: 4,
              }}
            />
            <Legend
              onClick={(e) => handleLegendClick(e.dataKey as string)}
              wrapperStyle={{ cursor: 'pointer' }}
            />

            {/* ゼロ線 */}
            <ReferenceLine
              y={0}
              stroke="#000"
              strokeWidth={1}
            />

            {/* 現況指数 */}
            <Line
              type="monotone"
              dataKey="current"
              stroke={SERIES_CONFIG.current.color}
              strokeWidth={SERIES_CONFIG.current.strokeWidth}
              dot={false}
              name={SERIES_CONFIG.current.name}
              hide={hiddenSeries.has('current')}
              isAnimationActive={false}
              connectNulls={true}
            />

            {/* 期待指数 */}
            <Line
              type="monotone"
              dataKey="future"
              stroke={SERIES_CONFIG.future.color}
              strokeWidth={SERIES_CONFIG.future.strokeWidth}
              dot={false}
              name={SERIES_CONFIG.future.name}
              hide={hiddenSeries.has('future')}
              isAnimationActive={false}
              connectNulls={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
