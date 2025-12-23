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
  ComposedChart,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { IndustrialProductionData } from '../../../../hooks/useDashboardData'

interface IndustrialProductionChartProps {
  data: IndustrialProductionData | null
}

type ViewMode = 'yoy' | 'mom_table' | 'mom_chart'

// 月名の定義
const MONTH_NAMES = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

export default function IndustrialProductionChart({ data }: IndustrialProductionChartProps) {
  const [selectedPeriodYoY, setSelectedPeriodYoY] = useState<number | 'all' | 'default'>('default')
  const [selectedPeriodMoM, setSelectedPeriodMoM] = useState<number | 'all' | 'default'>(3) // 前月比はデフォルト3年
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')
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

    // 前月比グラフと前年比で別々の期間設定を使用
    const selectedPeriod = viewMode === 'mom_chart' ? selectedPeriodMoM : selectedPeriodYoY

    if (selectedPeriod === 'all') {
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
  }, [chartData, selectedPeriodYoY, selectedPeriodMoM, viewMode])

  // テーブル用データ（年別×月別のマトリックス）- 前月比用
  const momTableData = useMemo(() => {
    if (chartData.length === 0) return { years: [], monthlyData: {} }

    // 直近10年分のデータを抽出
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
      const month = date.getMonth() // 0-11

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

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="鉱工業生産（Industrial Production）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="鉱工業生産（Industrial Production）" showPeriodSelector={false} showDataSource={false}>
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

  // グラフの色
  const COLORS = {
    yoy: '#1890ff',  // 前年比: 青
    mom: '#52c41a',  // 前月比: 緑
  }

  // 最新値
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

  // 表示する値を取得
  const getLatestValue = () => {
    if (!latest) return null
    return viewMode === 'yoy' ? latest.yoy : latest.mom
  }

  // 表示する色を取得
  const getLatestColor = () => {
    return viewMode === 'yoy' ? COLORS.yoy : COLORS.mom
  }

  // テーブルセルの背景色を決定（前月比用）
  const getMomCellColor = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'transparent'
    if (value > 0.5) return 'rgba(82, 196, 26, 0.3)'  // 強いプラス: 緑
    if (value > 0) return 'rgba(82, 196, 26, 0.15)'   // 弱いプラス: 薄緑
    if (value < -0.5) return 'rgba(255, 77, 79, 0.3)' // 強いマイナス: 赤
    if (value < 0) return 'rgba(255, 77, 79, 0.15)'   // 弱いマイナス: 薄赤
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
    <div id="industrial-production-chart">
      <ChartContainer
        title="鉱工業生産"
        showPeriodSelector={false}
        dataSource="FRED (FRB)"
        sourceUrl="https://www.federalreserve.gov/releases/G17/default.htm"
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
            <span style={{ fontSize: 12, color: '#666' }}>最新値: </span>
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
          </div>
        </div>

        <ViewModeButtons />

        {/* 前年比グラフの場合は期間セレクター表示 */}
        {viewMode === 'yoy' && (
          <PeriodSelector onPeriodChange={setSelectedPeriodYoY} selectedPeriod={selectedPeriodYoY} />
        )}
        {viewMode === 'mom_table' && (
          <div style={{ fontSize: 11, color: '#888', marginBottom: 12 }}>
            ※ 直近10年間の前月比データ（単位: %）
          </div>
        )}
        {viewMode === 'mom_chart' && (
          <PeriodSelector onPeriodChange={setSelectedPeriodMoM} selectedPeriod={selectedPeriodMoM} />
        )}

        {/* コンテンツ表示 */}
        {viewMode === 'mom_table' ? (
          <MoMTable />
        ) : (
          <ResponsiveContainer width="100%" height={450}>
            {viewMode === 'mom_chart' ? (
              // 前月比はバーチャート
              <ComposedChart
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
                  domain={['auto', 'auto']}
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
                <Bar
                  dataKey="mom"
                  fill={COLORS.mom}
                  name="鉱工業生産（前月比）"
                  hide={hiddenSeries.has('mom')}
                />
              </ComposedChart>
            ) : (
              // 前年比はラインチャート
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
                  domain={['auto', 'auto']}
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
                <ReferenceLine y={0} stroke="#000" strokeWidth={1} />
                <Line
                  type="monotone"
                  dataKey="yoy"
                  stroke={COLORS.yoy}
                  strokeWidth={2}
                  dot={false}
                  name="鉱工業生産（前年比）"
                  hide={hiddenSeries.has('yoy')}
                  isAnimationActive={false}
                  connectNulls={true}
                />
              </LineChart>
            )}
          </ResponsiveContainer>
        )}
      </ChartContainer>
    </div>
  )
}
