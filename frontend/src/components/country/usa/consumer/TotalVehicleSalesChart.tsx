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
  Bar,
  BarChart,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { TotalVehicleSalesData } from '../../../../hooks/useDashboardData'

interface TotalVehicleSalesChartProps {
  data: TotalVehicleSalesData | null
}

type ViewMode = 'value' | 'yoy' | 'mom_table' | 'mom_chart'

// 月名の定義
const MONTH_NAMES = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

export default function TotalVehicleSalesChart({ data }: TotalVehicleSalesChartProps) {
  const [selectedPeriodValue, setSelectedPeriodValue] = useState<number | 'all' | 'default'>('default')
  const [selectedPeriodYoY, setSelectedPeriodYoY] = useState<number | 'all' | 'default'>('default')
  const [selectedPeriodMoM, setSelectedPeriodMoM] = useState<number | 'all' | 'default'>(3)
  const [viewMode, setViewMode] = useState<ViewMode>('value')

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    if (chartData.length === 0) return []

    let selectedPeriod: number | 'all' | 'default'
    if (viewMode === 'value') {
      selectedPeriod = selectedPeriodValue
    } else if (viewMode === 'mom_chart') {
      selectedPeriod = selectedPeriodMoM
    } else {
      selectedPeriod = selectedPeriodYoY
    }

    if (selectedPeriod === 'all') {
      return chartData
    }

    const cutoffDate = new Date()

    if (selectedPeriod === 'default') {
      cutoffDate.setFullYear(2010, 0, 1)
    } else {
      cutoffDate.setFullYear(cutoffDate.getFullYear() - selectedPeriod)
    }

    return chartData.filter((item) => {
      const itemDate = new Date(item.date)
      return itemDate >= cutoffDate
    })
  }, [chartData, selectedPeriodValue, selectedPeriodYoY, selectedPeriodMoM, viewMode])

  // テーブル用データ（年別×月別のマトリックス）- 前月比用
  const momTableData = useMemo(() => {
    if (chartData.length === 0) return { years: [], monthlyData: {} }

    const currentYear = new Date().getFullYear()
    const startYear = currentYear - 9

    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) {
      years.push(y)
    }

    const monthlyData: Record<number, Record<number, number | null>> = {}

    chartData.forEach((item) => {
      const date = new Date(item.date)
      const year = date.getFullYear()
      const month = date.getMonth()

      if (year >= startYear && year <= currentYear) {
        if (!monthlyData[year]) {
          monthlyData[year] = {}
        }
        monthlyData[year][month] = item.mom
      }
    })

    return { years, monthlyData }
  }, [chartData])

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="自動車販売台数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="自動車販売台数" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  const formatValue = (value: number | null | undefined, decimals: number = 2) => {
    if (value === null || value === undefined) return 'N/A'
    const sign = value >= 0 ? '+' : ''
    return `${sign}${value.toFixed(decimals)}%`
  }

  const formatDateLabel = (dateStr: string): string => {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
  }

  // グラフの色
  const COLORS = {
    value: '#722ed1',
    yoy: '#52c41a',
    mom: '#1890ff',
  }

  const latest = data.latest

  // 表示モード切り替えボタン
  const ViewModeButtons = () => (
    <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
      <button
        onClick={() => setViewMode('value')}
        style={{
          padding: '6px 12px',
          border: viewMode === 'value' ? '2px solid #722ed1' : '1px solid #d9d9d9',
          borderRadius: 4,
          background: viewMode === 'value' ? '#f9f0ff' : '#fff',
          cursor: 'pointer',
          fontWeight: viewMode === 'value' ? 'bold' : 'normal',
        }}
      >
        原数値
      </button>
      <button
        onClick={() => setViewMode('yoy')}
        style={{
          padding: '6px 12px',
          border: viewMode === 'yoy' ? '2px solid #52c41a' : '1px solid #d9d9d9',
          borderRadius: 4,
          background: viewMode === 'yoy' ? '#f6ffed' : '#fff',
          cursor: 'pointer',
          fontWeight: viewMode === 'yoy' ? 'bold' : 'normal',
        }}
      >
        前年比
      </button>
      <button
        onClick={() => setViewMode('mom_table')}
        style={{
          padding: '6px 12px',
          border: viewMode === 'mom_table' ? '2px solid #1890ff' : '1px solid #d9d9d9',
          borderRadius: 4,
          background: viewMode === 'mom_table' ? '#e6f7ff' : '#fff',
          cursor: 'pointer',
          fontWeight: viewMode === 'mom_table' ? 'bold' : 'normal',
        }}
      >
        前月比テーブル
      </button>
      <button
        onClick={() => setViewMode('mom_chart')}
        style={{
          padding: '6px 12px',
          border: viewMode === 'mom_chart' ? '2px solid #1890ff' : '1px solid #d9d9d9',
          borderRadius: 4,
          background: viewMode === 'mom_chart' ? '#e6f7ff' : '#fff',
          cursor: 'pointer',
          fontWeight: viewMode === 'mom_chart' ? 'bold' : 'normal',
        }}
      >
        前月比グラフ
      </button>
    </div>
  )

  // テーブルセルの背景色を決定（前月比用）
  const getMomCellColor = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'transparent'
    if (value > 2) return 'rgba(82, 196, 26, 0.3)'
    if (value > 0) return 'rgba(82, 196, 26, 0.15)'
    if (value < -2) return 'rgba(255, 77, 79, 0.3)'
    if (value < 0) return 'rgba(255, 77, 79, 0.15)'
    return 'transparent'
  }

  // 前月比テーブルコンポーネント
  const MoMTable = () => (
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
                  minWidth: 50,
                }}
              >
                {month}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {momTableData.years.map((year: number) => (
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
                const value = momTableData.monthlyData[year]?.[month]

                return (
                  <td
                    key={month}
                    style={{
                      padding: '6px 4px',
                      borderBottom: '1px solid #e8e8e8',
                      backgroundColor: getMomCellColor(value),
                    }}
                  >
                    {value !== null && value !== undefined ? (
                      <span style={{ color: value >= 0 ? '#389e0d' : '#cf1322' }}>
                        {value >= 0 ? '+' : ''}{value.toFixed(2)}
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
      <div style={{ marginTop: 8, fontSize: 11, color: '#888', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(82, 196, 26, 0.3)', marginRight: 4 }} />
          プラス（+2%以上）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(82, 196, 26, 0.15)', marginRight: 4 }} />
          プラス（0〜+2%）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(255, 77, 79, 0.15)', marginRight: 4 }} />
          マイナス（0〜-2%）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(255, 77, 79, 0.3)', marginRight: 4 }} />
          マイナス（-2%以下）
        </span>
      </div>
    </div>
  )

  return (
    <div id="total-vehicle-sales">
      <ChartContainer
        title="自動車販売台数"
        showPeriodSelector={false}
        dataSource="U.S. Bureau of Economic Analysis"
        sourceUrl="https://fred.stlouisfed.org/series/TOTALSA"
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
            {/* 現在値（百万台） */}
            <div>
              <span style={{ fontSize: 12, color: '#666' }}>
                最新値:{' '}
              </span>
              {latest && (
                <span
                  style={{
                    fontSize: 20,
                    fontWeight: 'bold',
                    color: '#333',
                  }}
                >
                  {latest.value?.toFixed(2) ?? 'N/A'}M
                </span>
              )}
            </div>
            {/* 前年比 */}
            {viewMode === 'yoy' && latest?.yoy !== null && latest?.yoy !== undefined && (
              <div>
                <span style={{ fontSize: 12, color: '#666' }}>
                  前年比:{' '}
                </span>
                <span
                  style={{
                    fontSize: 20,
                    fontWeight: 'bold',
                    color: COLORS.yoy,
                  }}
                >
                  {formatValue(latest.yoy)}
                </span>
              </div>
            )}
            {/* 前月比 */}
            {(viewMode === 'mom_table' || viewMode === 'mom_chart') && latest?.mom !== null && latest?.mom !== undefined && (
              <div>
                <span style={{ fontSize: 12, color: '#666' }}>
                  前月比:{' '}
                </span>
                <span
                  style={{
                    fontSize: 20,
                    fontWeight: 'bold',
                    color: COLORS.mom,
                  }}
                >
                  {formatValue(latest.mom)}
                </span>
              </div>
            )}
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

        {/* 原数値グラフの場合 */}
        {viewMode === 'value' && (
          <>
            <PeriodSelector onPeriodChange={setSelectedPeriodValue} selectedPeriod={selectedPeriodValue} />
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
                  tickFormatter={(v) => `${v}M`}
                />
                <Tooltip
                  labelFormatter={formatDateLabel}
                  formatter={(value, name) => {
                    const numValue = typeof value === 'number' ? value : null
                    if (numValue === null) return ['N/A', name]
                    return [`${numValue.toFixed(2)}M`, name]
                  }}
                  contentStyle={{
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    border: '1px solid #d9d9d9',
                    borderRadius: 4,
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke={COLORS.value}
                  strokeWidth={2}
                  dot={false}
                  name="自動車販売台数"
                  isAnimationActive={false}
                  connectNulls={true}
                />
              </LineChart>
            </ResponsiveContainer>
          </>
        )}

        {/* 前年比グラフの場合 */}
        {viewMode === 'yoy' && (
          <>
            <PeriodSelector onPeriodChange={setSelectedPeriodYoY} selectedPeriod={selectedPeriodYoY} />
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
                    return [`${sign}${numValue.toFixed(2)}%`, name]
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
                  dataKey="yoy"
                  stroke={COLORS.yoy}
                  strokeWidth={2}
                  dot={false}
                  name="前年比"
                  isAnimationActive={false}
                  connectNulls={true}
                />
              </LineChart>
            </ResponsiveContainer>
          </>
        )}

        {/* 前月比テーブルの場合 */}
        {viewMode === 'mom_table' && (
          <>
            <div style={{ fontSize: 11, color: '#888', marginBottom: 12 }}>
              ※ 直近10年間の前月比データ（単位: %）
            </div>
            <MoMTable />
          </>
        )}

        {/* 前月比グラフの場合 */}
        {viewMode === 'mom_chart' && (
          <>
            <PeriodSelector onPeriodChange={setSelectedPeriodMoM} selectedPeriod={selectedPeriodMoM} />
            <ResponsiveContainer width="100%" height={450}>
              <BarChart
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
                  domain={['dataMin - 3', 'dataMax + 3']}
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v) => `${v}%`}
                />
                <Tooltip
                  labelFormatter={formatDateLabel}
                  formatter={(value, name) => {
                    const numValue = typeof value === 'number' ? value : null
                    if (numValue === null) return ['N/A', name]
                    const sign = numValue >= 0 ? '+' : ''
                    return [`${sign}${numValue.toFixed(2)}%`, name]
                  }}
                  contentStyle={{
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    border: '1px solid #d9d9d9',
                    borderRadius: 4,
                  }}
                />
                <ReferenceLine y={0} stroke="#000" strokeWidth={1} />
                <Bar
                  dataKey="mom"
                  fill={COLORS.mom}
                  name="前月比"
                />
              </BarChart>
            </ResponsiveContainer>
          </>
        )}
      </ChartContainer>
    </div>
  )
}
