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
import type { PhiladelphiaFedData } from '../../../../hooks/useDashboardData'

interface PhiladelphiaFedChartProps {
  data: PhiladelphiaFedData | null
}

// シリーズ設定（10シリーズ）
const SERIES_CONFIG = {
  general_activity_current: {
    name: '一般活動',
    color: '#0958D9',
    strokeWidth: 2,
  },
  general_activity_future: {
    name: '一般活動期待',
    color: '#91CAFF',
    strokeWidth: 2,
  },
  new_orders_current: {
    name: '新規受注',
    color: '#389e0d',
    strokeWidth: 2,
  },
  new_orders_future: {
    name: '新規受注期待',
    color: '#b7eb8f',
    strokeWidth: 2,
  },
  prices_paid_current: {
    name: '支払価格',
    color: '#cf1322',
    strokeWidth: 2,
  },
  prices_paid_future: {
    name: '支払価格期待',
    color: '#ffa39e',
    strokeWidth: 2,
  },
  employment_current: {
    name: '雇用',
    color: '#d46b08',
    strokeWidth: 2,
  },
  employment_future: {
    name: '雇用期待',
    color: '#ffd591',
    strokeWidth: 2,
  },
  capex_current: {
    name: '設備投資（ソフトウェア・機械設備）',
    color: '#531dab',
    strokeWidth: 2,
  },
  capex_future: {
    name: '設備投資期待',
    color: '#d3adf7',
    strokeWidth: 2,
  },
}

// 初期非表示シリーズ（一般活動指数のみ表示）
const INITIAL_HIDDEN_SERIES = new Set([
  'general_activity_future',
  'new_orders_current',
  'new_orders_future',
  'prices_paid_current',
  'prices_paid_future',
  'employment_current',
  'employment_future',
  'capex_current',
  'capex_future',
])

export default function PhiladelphiaFedChart({ data }: PhiladelphiaFedChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')
  const [hiddenSeries, setHiddenSeries] = useState<Set<string>>(new Set(INITIAL_HIDDEN_SERIES))

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        general_activity_current: item.general_activity_current,
        general_activity_future: item.general_activity_future,
        new_orders_current: item.new_orders_current,
        new_orders_future: item.new_orders_future,
        prices_paid_current: item.prices_paid_current,
        prices_paid_future: item.prices_paid_future,
        employment_current: item.employment_current,
        employment_future: item.employment_future,
        capex_current: item.capex_current,
        capex_future: item.capex_future,
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
    return <LoadingChart title="フィラデルフィア連銀製造業景気指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="フィラデルフィア連銀製造業景気指数" showPeriodSelector={false} showDataSource={false}>
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
  const latestCurrent = latestData?.general_activity_current ?? null
  const latestFuture = latestData?.general_activity_future ?? null

  return (
    <div id="philadelphia-fed-chart">
      <ChartContainer
        title="フィラデルフィア連銀製造業景気指数 現況 / 期待（今後6か月）"
        showPeriodSelector={false}
        dataSource="Federal Reserve Bank of Philadelphia / FRED"
        sourceUrl="https://www.philadelphiafed.org/surveys-and-data/regional-economic-analysis/manufacturing-business-outlook-survey"
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
                    backgroundColor: SERIES_CONFIG.general_activity_future.color,
                    display: 'inline-block',
                  }}
                />
                <span style={{ fontSize: 11, color: '#666' }}>期待指数:</span>
                <span style={{ fontSize: 13, fontWeight: 'bold', color: SERIES_CONFIG.general_activity_future.color }}>
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

            {/* 一般活動指数 */}
            <Line
              type="monotone"
              dataKey="general_activity_current"
              stroke={SERIES_CONFIG.general_activity_current.color}
              strokeWidth={SERIES_CONFIG.general_activity_current.strokeWidth}
              dot={false}
              name={SERIES_CONFIG.general_activity_current.name}
              hide={hiddenSeries.has('general_activity_current')}
              isAnimationActive={false}
              connectNulls={true}
            />

            {/* 一般活動期待指数 */}
            <Line
              type="monotone"
              dataKey="general_activity_future"
              stroke={SERIES_CONFIG.general_activity_future.color}
              strokeWidth={SERIES_CONFIG.general_activity_future.strokeWidth}
              dot={false}
              name={SERIES_CONFIG.general_activity_future.name}
              hide={hiddenSeries.has('general_activity_future')}
              isAnimationActive={false}
              connectNulls={true}
            />

            {/* 新規受注指数 */}
            <Line
              type="monotone"
              dataKey="new_orders_current"
              stroke={SERIES_CONFIG.new_orders_current.color}
              strokeWidth={SERIES_CONFIG.new_orders_current.strokeWidth}
              dot={false}
              name={SERIES_CONFIG.new_orders_current.name}
              hide={hiddenSeries.has('new_orders_current')}
              isAnimationActive={false}
              connectNulls={true}
            />

            {/* 新規受注期待指数 */}
            <Line
              type="monotone"
              dataKey="new_orders_future"
              stroke={SERIES_CONFIG.new_orders_future.color}
              strokeWidth={SERIES_CONFIG.new_orders_future.strokeWidth}
              dot={false}
              name={SERIES_CONFIG.new_orders_future.name}
              hide={hiddenSeries.has('new_orders_future')}
              isAnimationActive={false}
              connectNulls={true}
            />

            {/* 支払価格指数 */}
            <Line
              type="monotone"
              dataKey="prices_paid_current"
              stroke={SERIES_CONFIG.prices_paid_current.color}
              strokeWidth={SERIES_CONFIG.prices_paid_current.strokeWidth}
              dot={false}
              name={SERIES_CONFIG.prices_paid_current.name}
              hide={hiddenSeries.has('prices_paid_current')}
              isAnimationActive={false}
              connectNulls={true}
            />

            {/* 支払価格期待指数 */}
            <Line
              type="monotone"
              dataKey="prices_paid_future"
              stroke={SERIES_CONFIG.prices_paid_future.color}
              strokeWidth={SERIES_CONFIG.prices_paid_future.strokeWidth}
              dot={false}
              name={SERIES_CONFIG.prices_paid_future.name}
              hide={hiddenSeries.has('prices_paid_future')}
              isAnimationActive={false}
              connectNulls={true}
            />

            {/* 従業員数指数 */}
            <Line
              type="monotone"
              dataKey="employment_current"
              stroke={SERIES_CONFIG.employment_current.color}
              strokeWidth={SERIES_CONFIG.employment_current.strokeWidth}
              dot={false}
              name={SERIES_CONFIG.employment_current.name}
              hide={hiddenSeries.has('employment_current')}
              isAnimationActive={false}
              connectNulls={true}
            />

            {/* 従業員数期待指数 */}
            <Line
              type="monotone"
              dataKey="employment_future"
              stroke={SERIES_CONFIG.employment_future.color}
              strokeWidth={SERIES_CONFIG.employment_future.strokeWidth}
              dot={false}
              name={SERIES_CONFIG.employment_future.name}
              hide={hiddenSeries.has('employment_future')}
              isAnimationActive={false}
              connectNulls={true}
            />

            {/* 設備投資指数 */}
            <Line
              type="monotone"
              dataKey="capex_current"
              stroke={SERIES_CONFIG.capex_current.color}
              strokeWidth={SERIES_CONFIG.capex_current.strokeWidth}
              dot={false}
              name={SERIES_CONFIG.capex_current.name}
              hide={hiddenSeries.has('capex_current')}
              isAnimationActive={false}
              connectNulls={true}
            />

            {/* 設備投資期待指数 */}
            <Line
              type="monotone"
              dataKey="capex_future"
              stroke={SERIES_CONFIG.capex_future.color}
              strokeWidth={SERIES_CONFIG.capex_future.strokeWidth}
              dot={false}
              name={SERIES_CONFIG.capex_future.name}
              hide={hiddenSeries.has('capex_future')}
              isAnimationActive={false}
              connectNulls={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
