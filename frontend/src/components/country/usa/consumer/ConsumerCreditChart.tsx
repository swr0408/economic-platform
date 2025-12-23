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
import type { ConsumerCreditData } from '../../../../hooks/useDashboardData'

interface ConsumerCreditChartProps {
  data: ConsumerCreditData | null
}

type ViewMode = 'value' | 'yoy' | 'mom'

export default function ConsumerCreditChart({ data }: ConsumerCreditChartProps) {
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
    } else if (viewMode === 'mom') {
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

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="クレジットカードローン残高（月平均）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="クレジットカードローン残高（月平均）" showPeriodSelector={false} showDataSource={false}>
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

  // 月次データなので年月のみ表示
  const formatDateLabel = (dateStr: string): string => {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return `${date.getFullYear()}年${date.getMonth() + 1}月`
  }

  // X軸用の簡略表示
  const formatXAxisLabel = (dateStr: string): string => {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
  }

  // グラフの色
  const COLORS = {
    value: '#eb2f96',
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
          border: viewMode === 'value' ? '2px solid #eb2f96' : '1px solid #d9d9d9',
          borderRadius: 4,
          background: viewMode === 'value' ? '#fff0f6' : '#fff',
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
        onClick={() => setViewMode('mom')}
        style={{
          padding: '6px 12px',
          border: viewMode === 'mom' ? '2px solid #1890ff' : '1px solid #d9d9d9',
          borderRadius: 4,
          background: viewMode === 'mom' ? '#e6f7ff' : '#fff',
          cursor: 'pointer',
          fontWeight: viewMode === 'mom' ? 'bold' : 'normal',
        }}
      >
        前月比
      </button>
    </div>
  )

  return (
    <div id="consumer-credit">
      <ChartContainer
        title="クレジットカードローン残高"
        showPeriodSelector={false}
        dataSource="Federal Reserve"
        sourceUrl="https://www.federalreserve.gov/releases/h8/"
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
            {/* 現在値（10億ドル） */}
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
                  ${latest.value?.toFixed(2) ?? 'N/A'}B
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
                    color: latest.yoy >= 0 ? '#52c41a' : '#ff4d4f',
                  }}
                >
                  {formatValue(latest.yoy)}
                </span>
              </div>
            )}
            {/* 前月比 */}
            {viewMode === 'mom' && latest?.mom !== null && latest?.mom !== undefined && (
              <div>
                <span style={{ fontSize: 12, color: '#666' }}>
                  前月比:{' '}
                </span>
                <span
                  style={{
                    fontSize: 20,
                    fontWeight: 'bold',
                    color: latest.mom >= 0 ? '#1890ff' : '#ff4d4f',
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
                  tickFormatter={formatXAxisLabel}
                  tick={{ fontSize: 11 }}
                  interval="preserveStartEnd"
                />
                <YAxis
                  domain={['dataMin - 50', 'dataMax + 50']}
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v) => `$${v}B`}
                />
                <Tooltip
                  labelFormatter={formatDateLabel}
                  formatter={(value, name) => {
                    const numValue = typeof value === 'number' ? value : null
                    if (numValue === null) return ['N/A', name]
                    return [`$${numValue.toFixed(2)}B`, name]
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
                  name="クレジットカードローン残高"
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
                  tickFormatter={formatXAxisLabel}
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

        {/* 前月比グラフの場合 */}
        {viewMode === 'mom' && (
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
                  tickFormatter={formatXAxisLabel}
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
