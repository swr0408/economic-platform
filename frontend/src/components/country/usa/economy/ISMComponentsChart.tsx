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
import type { ISMComponentsData } from '../../../../hooks/useDashboardData'

interface ISMComponentsChartProps {
  data: ISMComponentsData | null
}

// サブインデックスの設定
const SERIES_CONFIG = {
  new_orders: { name: '新規受注', color: '#1890ff' },
  production: { name: '生産', color: '#52c41a' },
  employment: { name: '雇用', color: '#faad14' },
  prices: { name: '価格（仕入価格）', color: '#f5222d' },
  supplier_deliveries: { name: 'サプライヤー配送', color: '#722ed1' },
} as const

type SeriesKey = keyof typeof SERIES_CONFIG

export default function ISMComponentsChart({ data }: ISMComponentsChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')
  const [hiddenSeries, setHiddenSeries] = useState<Set<SeriesKey>>(new Set())

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        new_orders: item.new_orders,
        production: item.production,
        employment: item.employment,
        prices: item.prices,
        supplier_deliveries: item.supplier_deliveries,
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
    return <LoadingChart title="ISM製造業サブインデックス" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="ISM製造業サブインデックス" showPeriodSelector={false} showDataSource={false}>
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
    const key = dataKey as SeriesKey
    setHiddenSeries((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  // 最新値表示用
  const latestValues = data.latest
    ? Object.entries(SERIES_CONFIG).map(([key, config]) => ({
        key,
        name: config.name,
        color: config.color,
        value: data.latest?.[key as keyof typeof data.latest] as number | null,
      }))
    : []

  return (
    <div id="ism-components-chart">
      <ChartContainer
        title="ISM製造業サブインデックス"
        showPeriodSelector={false}
        dataSource="ISM"
        sourceUrl="https://www.ismworld.org/supply-management-news-and-reports/reports/ism-pmi-reports/"
      >
        {/* 最新値表示 */}
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 16,
            marginBottom: 12,
            padding: '12px 16px',
            background: '#f5f5f5',
            borderRadius: 8,
          }}
        >
          <div style={{ flex: '0 0 auto' }}>
            <span style={{ fontSize: 12, color: '#666' }}>最新: </span>
            {data.latest && (
              <span style={{ fontSize: 12, color: '#999' }}>
                ({formatDateLabel(data.latest.date)})
              </span>
            )}
          </div>
          {latestValues.map(({ key, name, color, value }) => (
            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span
                style={{
                  width: 12,
                  height: 12,
                  borderRadius: 2,
                  backgroundColor: color,
                  display: 'inline-block',
                }}
              />
              <span style={{ fontSize: 12, color: '#666' }}>{name}:</span>
              <span style={{ fontSize: 14, fontWeight: 'bold', color }}>
                {formatValue(value)}
              </span>
            </div>
          ))}
        </div>

        {/* 次回発表日 */}
        {data.next_release && (
          <div
            style={{
              marginBottom: 12,
              padding: '8px 16px',
              background: '#fff7e6',
              borderRadius: 8,
              borderLeft: '4px solid #faad14',
            }}
          >
            <span style={{ fontSize: 11, color: '#999' }}>次回発表: </span>
            <span style={{ fontSize: 12, color: '#666' }}>{data.next_release.date}</span>
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

            {/* 50の基準線 */}
            <ReferenceLine
              y={50}
              stroke="#000"
              strokeWidth={1}
              label={{
                value: '50',
                position: 'right',
                fontSize: 10,
                fill: '#666',
              }}
            />

            {/* 各サブインデックスのライン */}
            {Object.entries(SERIES_CONFIG).map(([key, config]) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={config.color}
                strokeWidth={2}
                dot={false}
                name={config.name}
                hide={hiddenSeries.has(key as SeriesKey)}
                isAnimationActive={false}
                connectNulls={true}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
