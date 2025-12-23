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
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { TSACheckpointData } from '../../../../hooks/useDashboardData'

interface TSACheckpointChartProps {
  data: TSACheckpointData | null
}

// チャートの色設定
const COLORS = {
  value: '#1890ff',    // 旅客数（青）
  ma30: '#ff7300',     // 30日移動平均（オレンジ）
}

export default function TSACheckpointChart({ data }: TSACheckpointChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')
  const [hiddenSeries, setHiddenSeries] = useState<Set<string>>(new Set())

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    )
  }, [data])

  // 期間フィルタリング（デフォルトを2年に変更）
  const filteredData = useMemo(() => {
    if (chartData.length === 0) return []

    if (selectedPeriod === 'all') {
      return chartData
    }

    const cutoffDate = new Date()

    if (selectedPeriod === 'default') {
      // デフォルトは2年間（2年分データに対応）
      cutoffDate.setFullYear(cutoffDate.getFullYear() - 2)
    } else {
      cutoffDate.setFullYear(cutoffDate.getFullYear() - selectedPeriod)
    }

    return chartData.filter((item) => {
      const itemDate = new Date(item.date)
      return itemDate >= cutoffDate
    })
  }, [chartData, selectedPeriod])

  // Y軸のドメインを計算（余白を持たせてスケール調整）
  const yAxisDomain = useMemo(() => {
    if (filteredData.length === 0) return [0, 'auto'] as [number, 'auto']

    const values = filteredData
      .flatMap((d) => [d.value, d.ma30])
      .filter((v): v is number => v !== null && v !== undefined)

    if (values.length === 0) return [0, 'auto'] as [number, 'auto']

    const minValue = Math.min(...values)
    const maxValue = Math.max(...values)

    // 最小値から10%の余白、最大値から5%の余白を持たせる
    const padding = (maxValue - minValue) * 0.1
    const adjustedMin = Math.max(0, minValue - padding)
    const adjustedMax = maxValue + padding * 0.5

    return [adjustedMin, adjustedMax] as [number, number]
  }, [filteredData])

  const hasData = chartData.length > 0

  // レジェンドクリックで系列を非表示
  const handleLegendClick = (dataKey: string) => {
    setHiddenSeries((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(dataKey)) {
        newSet.delete(dataKey)
      } else {
        newSet.add(dataKey)
      }
      return newSet
    })
  }

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="米航空機旅客者数（TSA Checkpoint）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="米航空機旅客者数（TSA Checkpoint）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  // 値のフォーマット（百万人単位）
  const formatValue = (value: number | null | undefined): string => {
    if (value === null || value === undefined) return 'N/A'
    return `${(value / 1000000).toFixed(2)}M`
  }

  // ツールチップ用フォーマット
  const formatTooltipValue = (value: number | null | undefined): string => {
    if (value === null || value === undefined) return 'N/A'
    return `${value.toLocaleString()} 人`
  }

  // 日付フォーマット
  const formatDateLabel = (dateStr: string): string => {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`
  }

  // 最新値
  const latest = data.latest

  return (
    <div id="tsa-checkpoint-chart">
      <ChartContainer
        title="米航空機旅客者数"
        showPeriodSelector={false}
        dataSource="TSA"
        sourceUrl="https://www.tsa.gov/travel/passenger-volumes"
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
          <div>
            <span style={{ fontSize: 12, color: '#666' }}>最新値: </span>
            {latest && (
              <>
                <span
                  style={{
                    fontSize: 20,
                    fontWeight: 'bold',
                    color: COLORS.value,
                  }}
                >
                  {formatTooltipValue(latest.value)}
                </span>
                <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>
                  ({formatDateLabel(latest.date)})
                </span>
              </>
            )}
          </div>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            {latest?.mom_pct !== null && latest?.mom_pct !== undefined && (
              <div style={{ fontSize: 12 }}>
                <span style={{ color: '#666' }}>前月比: </span>
                <span
                  style={{
                    fontWeight: 'bold',
                    color: latest.mom_pct >= 0 ? '#52c41a' : '#ff4d4f',
                  }}
                >
                  {latest.mom_pct >= 0 ? '+' : ''}
                  {latest.mom_pct.toFixed(1)}%
                </span>
              </div>
            )}
            {latest?.yoy_pct !== null && latest?.yoy_pct !== undefined && (
              <div style={{ fontSize: 12 }}>
                <span style={{ color: '#666' }}>前年同月比: </span>
                <span
                  style={{
                    fontWeight: 'bold',
                    color: latest.yoy_pct >= 0 ? '#52c41a' : '#ff4d4f',
                  }}
                >
                  {latest.yoy_pct >= 0 ? '+' : ''}
                  {latest.yoy_pct.toFixed(1)}%
                </span>
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
              tick={{ fontSize: 11 }}
              tickFormatter={formatValue}
              domain={yAxisDomain}
            />
            <Tooltip
              labelFormatter={formatDateLabel}
              formatter={(value: number, name: string) => {
                const displayName = name === 'value'
                  ? '旅客数'
                  : name === 'ma30'
                  ? '30日移動平均'
                  : name
                return [formatTooltipValue(value), displayName]
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
            <Line
              type="monotone"
              dataKey="value"
              stroke={COLORS.value}
              strokeWidth={1}
              dot={false}
              name="旅客数"
              hide={hiddenSeries.has('value')}
              connectNulls={true}
            />
            <Line
              type="monotone"
              dataKey="ma30"
              stroke={COLORS.ma30}
              strokeWidth={2}
              dot={false}
              name="30日移動平均"
              hide={hiddenSeries.has('ma30')}
              connectNulls={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
