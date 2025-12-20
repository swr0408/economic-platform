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

interface OrderInventoryBalanceChartProps {
  data: ISMComponentsData | null
}

export default function OrderInventoryBalanceChart({ data }: OrderInventoryBalanceChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')
  const [hiddenSeries, setHiddenSeries] = useState<Set<string>>(new Set(['balance']))

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        balance: item.order_inventory_balance,
        balance_3ma: item.order_inventory_balance_3ma,
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
    return <LoadingChart title="ISM製造業受注在庫バランス" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="ISM製造業受注在庫バランス" showPeriodSelector={false} showDataSource={false}>
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
  const latestBalance = latestData?.order_inventory_balance
  const latestBalance3MA = latestData?.order_inventory_balance_3ma

  return (
    <div id="order-inventory-balance-chart">
      <ChartContainer
        title="ISM製造業受注在庫バランス"
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
            {latestData && (
              <span style={{ fontSize: 12, color: '#999' }}>
                ({formatDateLabel(latestData.date)})
              </span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span
              style={{
                width: 12,
                height: 12,
                borderRadius: 2,
                backgroundColor: '#228B22',
                display: 'inline-block',
              }}
            />
            <span style={{ fontSize: 12, color: '#666' }}>3ヶ月平均:</span>
            <span style={{ fontSize: 14, fontWeight: 'bold', color: '#228B22' }}>
              {formatValue(latestBalance3MA)}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span
              style={{
                width: 12,
                height: 12,
                borderRadius: 2,
                backgroundColor: 'rgba(34, 139, 34, 0.5)',
                display: 'inline-block',
              }}
            />
            <span style={{ fontSize: 12, color: '#666' }}>当月:</span>
            <span style={{ fontSize: 14, fontWeight: 'bold', color: 'rgba(34, 139, 34, 0.8)' }}>
              {formatValue(latestBalance)}
            </span>
          </div>
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
              domain={['dataMin - 2', 'dataMax + 2']}
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
              strokeDasharray="4 4"
            />

            {/* 受注在庫バランス（3ヶ月移動平均） - メインライン */}
            <Line
              type="monotone"
              dataKey="balance_3ma"
              stroke="#228B22"
              strokeWidth={2}
              dot={false}
              name="受注在庫バランス（3ヶ月平均）"
              hide={hiddenSeries.has('balance_3ma')}
              isAnimationActive={false}
              connectNulls={true}
            />

            {/* 受注在庫バランス（当月） - 補助ライン */}
            <Line
              type="monotone"
              dataKey="balance"
              stroke="rgba(34, 139, 34, 0.5)"
              strokeWidth={1}
              dot={false}
              name="受注在庫バランス（当月）"
              hide={hiddenSeries.has('balance')}
              isAnimationActive={false}
              connectNulls={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
