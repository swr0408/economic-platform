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
import type { RetailSalesData, RetailControlData } from '../../../../hooks/useDashboardData'

interface RetailSalesChartProps {
  data: RetailSalesData | null
  controlData: RetailControlData | null
}

type ViewMode = 'yoy' | 'mom_table' | 'mom_chart'
type DataType = 'total' | 'ex_auto' | 'control_group'

// 月名の定義
const MONTH_NAMES = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

export default function RetailSalesChart({ data, controlData }: RetailSalesChartProps) {
  const [selectedPeriodYoY, setSelectedPeriodYoY] = useState<number | 'all' | 'default'>('default')
  const [selectedPeriodMoM, setSelectedPeriodMoM] = useState<number | 'all' | 'default'>(3)
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')
  const [dataType, setDataType] = useState<DataType>('total')
  const [hiddenSeries, setHiddenSeries] = useState<Set<string>>(new Set())

  // コントロールグループデータを日付でマッピング
  const controlGroupMap = useMemo(() => {
    if (!controlData?.data) return new Map<string, number>()
    const map = new Map<string, number>()
    controlData.data.forEach((item) => {
      map.set(item.date, item.mom)
    })
    return map
  }, [controlData])

  // データを日付昇順にソートし、コントロールグループの前月比をマージ
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        ...item,
        control_group_mom: controlGroupMap.get(item.date) ?? null,
      }))
  }, [data, controlGroupMap])

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

    const monthlyData: Record<number, Record<number, { total: number | null; ex_auto: number | null; control_group: number | null }>> = {}

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
          ex_auto: item.ex_auto_mom,
          control_group: item.control_group_mom
        }
      }
    })

    return { years, monthlyData }
  }, [chartData])

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="小売売上高（Retail Sales）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="小売売上高（Retail Sales）" showPeriodSelector={false} showDataSource={false}>
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
    yoy: '#52c41a',
    yoy_ex: '#722ed1',
    yoy_cg: '#13c2c2',
    mom: '#52c41a',
    mom_ex: '#722ed1',
    mom_cg: '#13c2c2',
  }

  const latest = data.latest

  // 表示モード切り替えボタン
  const ViewModeButtons = () => (
    <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
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

  // データタイプ切り替えボタン（前月比用）
  const DataTypeButtons = () => (
    <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
      <button
        onClick={() => setDataType('total')}
        style={{
          padding: '4px 10px',
          border: dataType === 'total' ? '2px solid #52c41a' : '1px solid #d9d9d9',
          borderRadius: 4,
          background: dataType === 'total' ? '#f6ffed' : '#fff',
          cursor: 'pointer',
          fontWeight: dataType === 'total' ? 'bold' : 'normal',
          fontSize: 12,
        }}
      >
        総合
      </button>
      <button
        onClick={() => setDataType('ex_auto')}
        style={{
          padding: '4px 10px',
          border: dataType === 'ex_auto' ? '2px solid #722ed1' : '1px solid #d9d9d9',
          borderRadius: 4,
          background: dataType === 'ex_auto' ? '#f9f0ff' : '#fff',
          cursor: 'pointer',
          fontWeight: dataType === 'ex_auto' ? 'bold' : 'normal',
          fontSize: 12,
        }}
      >
        自動車除く
      </button>
      <button
        onClick={() => setDataType('control_group')}
        style={{
          padding: '4px 10px',
          border: dataType === 'control_group' ? '2px solid #13c2c2' : '1px solid #d9d9d9',
          borderRadius: 4,
          background: dataType === 'control_group' ? '#e6fffb' : '#fff',
          cursor: 'pointer',
          fontWeight: dataType === 'control_group' ? 'bold' : 'normal',
          fontSize: 12,
        }}
      >
        コントロールグループ
      </button>
    </div>
  )

  // コントロールグループの最新日付取得
  const getLatestDate = () => {
    if (dataType === 'control_group' && controlData?.latest) {
      return controlData.latest.date
    }
    return latest?.date
  }

  // 表示する値を取得
  const getLatestValue = () => {
    if (!latest) return null
    if (viewMode === 'yoy') {
      // 前年比はコントロールグループなし
      if (dataType === 'total') return latest.yoy
      if (dataType === 'ex_auto') return latest.ex_auto_yoy
      return null  // コントロールグループは前年比なし
    } else {
      if (dataType === 'total') return latest.mom
      if (dataType === 'ex_auto') return latest.ex_auto_mom
      // コントロールグループはcontrolDataから取得
      return controlData?.latest?.mom ?? null
    }
  }

  // 表示する色を取得
  const getLatestColor = () => {
    if (viewMode === 'yoy') {
      if (dataType === 'total') return COLORS.yoy
      if (dataType === 'ex_auto') return COLORS.yoy_ex
      return COLORS.yoy_cg
    }
    if (dataType === 'total') return COLORS.mom
    if (dataType === 'ex_auto') return COLORS.mom_ex
    return COLORS.mom_cg
  }

  // データタイプのラベル
  const getDataTypeLabel = () => {
    if (dataType === 'total') return '総合'
    if (dataType === 'ex_auto') return '自動車除く'
    return 'コントロールグループ'
  }

  // テーブルセルの背景色を決定（前月比用）
  const getMomCellColor = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'transparent'
    if (value > 0.5) return 'rgba(82, 196, 26, 0.3)'
    if (value > 0) return 'rgba(82, 196, 26, 0.15)'
    if (value < -0.5) return 'rgba(255, 77, 79, 0.3)'
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
                let value: number | null | undefined
                if (dataType === 'total') value = cellData?.total
                else if (dataType === 'ex_auto') value = cellData?.ex_auto
                else value = cellData?.control_group

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
          プラス（+0.5%以上）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(82, 196, 26, 0.15)', marginRight: 4 }} />
          プラス（0〜+0.5%）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(255, 77, 79, 0.15)', marginRight: 4 }} />
          マイナス（0〜-0.5%）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(255, 77, 79, 0.3)', marginRight: 4 }} />
          マイナス（-0.5%以下）
        </span>
      </div>
    </div>
  )

  return (
    <div id="retail-sales">
      <ChartContainer
        title="小売売上高（Retail Sales）"
        showPeriodSelector={false}
        dataSource="FRED (Census Bureau)"
        sourceUrl="https://www.census.gov/retail/release_schedule.html"
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
              最新値（{getDataTypeLabel()}）:{' '}
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
                  ({getLatestDate() ? formatDateLabel(getLatestDate()!) : ''})
                </span>
              </>
            )}
          </div>
          <div style={{ fontSize: 11, color: '#888', textAlign: 'right' }}>
            {data.next_release && (
              <div>次回発表: {data.next_release.date}</div>
            )}
            <div>毎月中旬 8:30 ET</div>
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
                  name="小売売上高 前年比"
                  hide={hiddenSeries.has('yoy')}
                  isAnimationActive={false}
                  connectNulls={true}
                />
                <Line
                  type="monotone"
                  dataKey="ex_auto_yoy"
                  stroke={COLORS.yoy_ex}
                  strokeWidth={2}
                  dot={false}
                  name="自動車除く 前年比"
                  hide={hiddenSeries.has('ex_auto_yoy')}
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
                  domain={['dataMin - 1', 'dataMax + 1']}
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
                {dataType === 'total' && (
                  <Bar
                    dataKey="mom"
                    fill={COLORS.mom}
                    name="小売売上高 前月比"
                  />
                )}
                {dataType === 'ex_auto' && (
                  <Bar
                    dataKey="ex_auto_mom"
                    fill={COLORS.mom_ex}
                    name="自動車除く 前月比"
                  />
                )}
                {dataType === 'control_group' && (
                  <Bar
                    dataKey="control_group_mom"
                    fill={COLORS.mom_cg}
                    name="コントロールグループ 前月比"
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
