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
  Bar,
  BarChart,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { DurableGoodsData } from '../../../../hooks/useDashboardData'

interface DurableGoodsChartProps {
  data: DurableGoodsData | null
}

type ViewMode = 'yoy' | 'mom_table' | 'mom_chart'
type DataType = 'total' | 'ex_transport'

// 月名の定義
const MONTH_NAMES = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

export default function DurableGoodsChart({ data }: DurableGoodsChartProps) {
  const [selectedPeriodYoY, setSelectedPeriodYoY] = useState<number | 'all' | 'default'>('default')
  const [selectedPeriodMoM, setSelectedPeriodMoM] = useState<number | 'all' | 'default'>(3)
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')
  const [dataType, setDataType] = useState<DataType>('total')
  const [hiddenSeries, setHiddenSeries] = useState<Set<string>>(new Set())

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    )
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    if (chartData.length === 0) return []

    const selectedPeriod = viewMode === 'mom_chart' ? selectedPeriodMoM : selectedPeriodYoY

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
  }, [chartData, selectedPeriodYoY, selectedPeriodMoM, viewMode])

  // テーブル用データ（年別×月別のマトリックス）- 前月比用
  const momTableData = useMemo(() => {
    if (chartData.length === 0) return { years: [], monthlyData: {} }

    const currentYear = new Date().getFullYear()
    const startYear = currentYear - 9

    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) {
      years.push(y)
    }

    const monthlyData: Record<number, Record<number, { total: number | null; ex_transport: number | null }>> = {}

    chartData.forEach((item) => {
      const date = new Date(item.date)
      const year = date.getFullYear()
      const month = date.getMonth()

      if (year >= startYear && year <= currentYear) {
        if (!monthlyData[year]) {
          monthlyData[year] = {}
        }
        monthlyData[year][month] = {
          total: item.mom,
          ex_transport: item.ex_transport_mom
        }
      }
    })

    return { years, monthlyData }
  }, [chartData])

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="耐久財受注（Durable Goods Orders）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="耐久財受注（Durable Goods Orders）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  const formatValue = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'N/A'
    const sign = value >= 0 ? '+' : ''
    return `${sign}${value.toFixed(2)}%`
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
    yoy: '#1890ff',
    yoy_ex: '#722ed1',
    mom: '#52c41a',
    mom_ex: '#13c2c2',
  }

  const latest = data.latest

  // 表示モード切り替えボタン
  const ViewModeButtons = () => (
    <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
      <button
        onClick={() => setViewMode('yoy')}
        style={{
          padding: '6px 12px',
          border: viewMode === 'yoy' ? '2px solid #1890ff' : '1px solid #d9d9d9',
          borderRadius: 4,
          background: viewMode === 'yoy' ? '#e6f7ff' : '#fff',
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
          border: viewMode === 'mom_table' ? '2px solid #52c41a' : '1px solid #d9d9d9',
          borderRadius: 4,
          background: viewMode === 'mom_table' ? '#f6ffed' : '#fff',
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
          border: viewMode === 'mom_chart' ? '2px solid #52c41a' : '1px solid #d9d9d9',
          borderRadius: 4,
          background: viewMode === 'mom_chart' ? '#f6ffed' : '#fff',
          cursor: 'pointer',
          fontWeight: viewMode === 'mom_chart' ? 'bold' : 'normal',
        }}
      >
        前月比グラフ
      </button>
    </div>
  )

  // データタイプ切り替えボタン
  const DataTypeButtons = () => (
    <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
      <button
        onClick={() => setDataType('total')}
        style={{
          padding: '4px 10px',
          border: dataType === 'total' ? '2px solid #1890ff' : '1px solid #d9d9d9',
          borderRadius: 4,
          background: dataType === 'total' ? '#e6f7ff' : '#fff',
          cursor: 'pointer',
          fontWeight: dataType === 'total' ? 'bold' : 'normal',
          fontSize: 12,
        }}
      >
        総合
      </button>
      <button
        onClick={() => setDataType('ex_transport')}
        style={{
          padding: '4px 10px',
          border: dataType === 'ex_transport' ? '2px solid #722ed1' : '1px solid #d9d9d9',
          borderRadius: 4,
          background: dataType === 'ex_transport' ? '#f9f0ff' : '#fff',
          cursor: 'pointer',
          fontWeight: dataType === 'ex_transport' ? 'bold' : 'normal',
          fontSize: 12,
        }}
      >
        輸送除外
      </button>
    </div>
  )

  // 表示する値を取得
  const getLatestValue = () => {
    if (!latest) return null
    if (viewMode === 'yoy') {
      return dataType === 'total' ? latest.yoy : latest.ex_transport_yoy
    } else {
      return dataType === 'total' ? latest.mom : latest.ex_transport_mom
    }
  }

  // 表示する色を取得
  const getLatestColor = () => {
    if (viewMode === 'yoy') {
      return dataType === 'total' ? COLORS.yoy : COLORS.yoy_ex
    }
    return dataType === 'total' ? COLORS.mom : COLORS.mom_ex
  }

  // テーブルセルの背景色を決定（前月比用）
  const getMomCellColor = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'transparent'
    if (value > 1) return 'rgba(82, 196, 26, 0.3)'
    if (value > 0) return 'rgba(82, 196, 26, 0.15)'
    if (value < -1) return 'rgba(255, 77, 79, 0.3)'
    if (value < 0) return 'rgba(255, 77, 79, 0.15)'
    return 'transparent'
  }

  // 前月比テーブルコンポーネント
  const MoMTable = () => (
    <div style={{ overflowX: 'auto' }}>
      <DataTypeButtons />
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
                const cellData = momTableData.monthlyData[year]?.[month]
                const value = dataType === 'total' ? cellData?.total : cellData?.ex_transport
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
          プラス（+1%以上）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(82, 196, 26, 0.15)', marginRight: 4 }} />
          プラス（0〜+1%）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(255, 77, 79, 0.15)', marginRight: 4 }} />
          マイナス（0〜-1%）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(255, 77, 79, 0.3)', marginRight: 4 }} />
          マイナス（-1%以下）
        </span>
      </div>
    </div>
  )

  return (
    <div id="durable-goods-chart">
      <ChartContainer
        title="耐久財受注（Durable Goods Orders）"
        showPeriodSelector={false}
        dataSource="FRED (Census Bureau)"
        sourceUrl="https://www.census.gov/manufacturing/m3/release_schedule.html"
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
          }}
        >
          <div>
            <span style={{ fontSize: 12, color: '#666' }}>
              最新値（{dataType === 'total' ? '総合' : '輸送除外'}）:{' '}
            </span>
            {latest && (
              <>
                <span
                  style={{
                    fontSize: 20,
                    fontWeight: 'bold',
                    color: getLatestColor(),
                  }}
                >
                  {formatValue(getLatestValue())}
                </span>
                <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>
                  ({formatDateLabel(latest.date)})
                </span>
              </>
            )}
          </div>
          <div style={{ fontSize: 11, color: '#888', textAlign: 'right' }}>
            {data.next_release && (
              <div>次回発表: {data.next_release.date}</div>
            )}
            <div>毎月下旬 8:30 ET</div>
          </div>
        </div>

        <ViewModeButtons />

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
                <Legend
                  onClick={(e) => handleLegendClick(e.dataKey as string)}
                  wrapperStyle={{ cursor: 'pointer' }}
                />
                <ReferenceLine y={0} stroke="#000" strokeWidth={1}/>
                <Line
                  type="monotone"
                  dataKey="yoy"
                  stroke={COLORS.yoy}
                  strokeWidth={2}
                  dot={false}
                  name="耐久財受注 前年比"
                  hide={hiddenSeries.has('yoy')}
                  isAnimationActive={false}
                  connectNulls={true}
                />
                <Line
                  type="monotone"
                  dataKey="ex_transport_yoy"
                  stroke={COLORS.yoy_ex}
                  strokeWidth={2}
                  dot={false}
                  name="輸送除外 前年比"
                  hide={hiddenSeries.has('ex_transport_yoy')}
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
            <DataTypeButtons />
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
                    return [`${sign}${numValue.toFixed(2)}%`, name]
                  }}
                  contentStyle={{
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    border: '1px solid #d9d9d9',
                    borderRadius: 4,
                  }}
                />
                <Legend />
                <ReferenceLine y={0} stroke="#000" strokeWidth={1} />
                {dataType === 'total' ? (
                  <Bar
                    dataKey="mom"
                    fill={COLORS.mom}
                    name="耐久財受注 前月比"
                  />
                ) : (
                  <Bar
                    dataKey="ex_transport_mom"
                    fill={COLORS.mom_ex}
                    name="輸送除外 前月比"
                  />
                )}
              </BarChart>
            </ResponsiveContainer>
          </>
        )}
      </ChartContainer>
    </div>
  )
}
