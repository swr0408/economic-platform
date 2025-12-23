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
import type { CartsData } from '../../../../hooks/useDashboardData'

interface CartsChartProps {
  data: CartsData | null
}

type ViewMode = 'chart' | 'table'

// 月名の定義
const MONTH_NAMES = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

export default function CartsChart({ data }: CartsChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')
  const [viewMode, setViewMode] = useState<ViewMode>('chart')
  const [hiddenSeries, setHiddenSeries] = useState<Set<string>>(new Set())

  // 週次データを月次データに集約
  const monthlyData = useMemo(() => {
    if (!data?.weekly?.data || data.weekly.data.length === 0) return []

    // 週次データを月ごとにグループ化し、月末の値を使用
    const monthGroups: Record<string, typeof data.weekly.data[0]> = {}

    data.weekly.data.forEach((item) => {
      const date = new Date(item.date)
      const monthKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`

      // 同じ月の中で最も遅い日付のデータを使用
      if (!monthGroups[monthKey] || new Date(item.date) > new Date(monthGroups[monthKey].date)) {
        monthGroups[monthKey] = item
      }
    })

    // 月ごとのデータを配列に変換し、日付順にソート
    return Object.entries(monthGroups)
      .map(([monthKey, item]) => ({
        date: `${monthKey}-01`,
        monthKey,
        nominal: item.nominal,
        real: item.real,
        // 十億ドル単位に変換（グラフ用）
        nominalB: item.nominal ? item.nominal / 1000 : null,
        realB: item.real ? item.real / 1000 : null,
      }))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    if (monthlyData.length === 0) return []

    if (selectedPeriod === 'all') {
      return monthlyData
    }

    const cutoffDate = new Date()

    if (selectedPeriod === 'default') {
      cutoffDate.setFullYear(2020, 0, 1)
    } else {
      cutoffDate.setFullYear(cutoffDate.getFullYear() - selectedPeriod)
    }

    return monthlyData.filter((item) => {
      const itemDate = new Date(item.date)
      return itemDate >= cutoffDate
    })
  }, [monthlyData, selectedPeriod])

  // テーブル用データ（年別×月別のマトリックス）
  const tableData = useMemo(() => {
    if (monthlyData.length === 0) return { years: [], monthlyData: {} }

    const currentYear = new Date().getFullYear()
    const startYear = currentYear - 9

    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) {
      years.push(y)
    }

    const data: Record<number, Record<number, { nominal: number | null; real: number | null }>> = {}

    monthlyData.forEach((item) => {
      const date = new Date(item.date)
      const year = date.getFullYear()
      const month = date.getMonth()

      if (year >= startYear && year <= currentYear) {
        if (!data[year]) {
          data[year] = {}
        }
        data[year][month] = {
          nominal: item.nominal,
          real: item.real,
        }
      }
    })

    return { years, monthlyData: data }
  }, [monthlyData])

  const hasData = monthlyData.length > 0

  if (data === null) {
    return <LoadingChart title="シカゴ連銀小売指数（CARTS）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="シカゴ連銀小売指数（CARTS）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  const formatDollarValue = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'N/A'
    // 百万ドルを十億ドルに変換して表示
    return `$${(value / 1000).toFixed(1)}B`
  }

  const formatDateLabel = (dateStr: string): string => {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
  }

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

  // グラフの色
  const COLORS = {
    nominal: '#2f54eb',
    real: '#52c41a',
  }

  const latest = data.weekly?.latest

  // 表示モード切り替えボタン
  const ViewModeButtons = () => (
    <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
      <button
        onClick={() => setViewMode('chart')}
        style={{
          padding: '6px 12px',
          border: viewMode === 'chart' ? '2px solid #2f54eb' : '1px solid #d9d9d9',
          borderRadius: 4,
          background: viewMode === 'chart' ? '#e6f0ff' : '#fff',
          cursor: 'pointer',
          fontWeight: viewMode === 'chart' ? 'bold' : 'normal',
        }}
      >
        グラフ
      </button>
      <button
        onClick={() => setViewMode('table')}
        style={{
          padding: '6px 12px',
          border: viewMode === 'table' ? '2px solid #1890ff' : '1px solid #d9d9d9',
          borderRadius: 4,
          background: viewMode === 'table' ? '#e6f7ff' : '#fff',
          cursor: 'pointer',
          fontWeight: viewMode === 'table' ? 'bold' : 'normal',
        }}
      >
        テーブル
      </button>
    </div>
  )

  // テーブルコンポーネント（実質値表示）
  const DataTable = () => (
    <div style={{ overflowX: 'auto' }}>
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: 12,
          textAlign: 'center',
        }}
      >
        <thead>
          <tr style={{ backgroundColor: '#fafafa' }}>
            <th style={{ padding: '8px 4px', borderBottom: '2px solid #d9d9d9', fontWeight: 'bold' }}>
              年
            </th>
            {MONTH_NAMES.map((month, idx) => (
              <th
                key={idx}
                style={{
                  padding: '8px 4px',
                  borderBottom: '2px solid #d9d9d9',
                  fontWeight: 'bold',
                  minWidth: 60,
                }}
              >
                {month}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tableData.years.map((year: number) => (
            <tr key={year}>
              <td
                style={{
                  padding: '6px 4px',
                  borderBottom: '1px solid #e8e8e8',
                  fontWeight: 'bold',
                  backgroundColor: '#fafafa',
                }}
              >
                {year}
              </td>
              {Array.from({ length: 12 }, (_, month) => {
                const cellData = tableData.monthlyData[year]?.[month]
                const value = cellData?.real

                return (
                  <td
                    key={month}
                    style={{
                      padding: '6px 4px',
                      borderBottom: '1px solid #e8e8e8',
                    }}
                  >
                    {value !== null && value !== undefined ? (
                      <span style={{ color: '#52c41a' }}>
                        {(value / 1000).toFixed(1)}
                      </span>
                    ) : (
                      <span style={{ color: '#bfbfbf' }}>-</span>
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: 8, fontSize: 11, color: '#888' }}>
        ※ 実質値（2017年基準、十億ドル）
      </div>
    </div>
  )

  return (
    <div id="carts">
      <ChartContainer
        title="シカゴ連銀小売指数（CARTS）"
        showPeriodSelector={false}
        dataSource="Chicago Fed CARTS"
        sourceUrl="https://www.chicagofed.org/research/data/carts/current-data"
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
            {/* 名目値 */}
            <div>
              <span style={{ fontSize: 12, color: '#666' }}>
                名目値:{' '}
              </span>
              {latest && (
                <>
                  <span
                    style={{
                      fontSize: 20,
                      fontWeight: 'bold',
                      color: '#2f54eb',
                    }}
                  >
                    {formatDollarValue(latest.nominal)}
                  </span>
                </>
              )}
            </div>
            {/* 実質値 */}
            <div>
              <span style={{ fontSize: 12, color: '#666' }}>
                実質値:{' '}
              </span>
              {latest && (
                <>
                  <span
                    style={{
                      fontSize: 20,
                      fontWeight: 'bold',
                      color: '#52c41a',
                    }}
                  >
                    {formatDollarValue(latest.real)}
                  </span>
                </>
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

        <ViewModeButtons />

        {/* グラフ表示 */}
        {viewMode === 'chart' && (
          <>
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
                  domain={['dataMin - 10', 'dataMax + 10']}
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v) => `$${v}B`}
                />
                <Tooltip
                  labelFormatter={formatDateLabel}
                  formatter={(value, name) => {
                    const numValue = typeof value === 'number' ? value : null
                    if (numValue === null) return ['N/A', name]
                    return [`$${numValue.toFixed(1)}B`, name]
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
                  dataKey="nominalB"
                  stroke={COLORS.nominal}
                  strokeWidth={2}
                  dot={false}
                  name="名目値"
                  hide={hiddenSeries.has('nominalB')}
                  isAnimationActive={false}
                  connectNulls={true}
                />
                <Line
                  type="monotone"
                  dataKey="realB"
                  stroke={COLORS.real}
                  strokeWidth={2}
                  dot={false}
                  name="実質値（2017年基準）"
                  hide={hiddenSeries.has('realB')}
                  isAnimationActive={false}
                  connectNulls={true}
                />
              </LineChart>
            </ResponsiveContainer>
          </>
        )}

        {/* テーブル表示 */}
        {viewMode === 'table' && (
          <>
            <div style={{ fontSize: 11, color: '#888', marginBottom: 12 }}>
              ※ 直近10年間のデータ（月末時点）
            </div>
            <DataTable />
          </>
        )}
      </ChartContainer>
    </div>
  )
}
