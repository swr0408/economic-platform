/**
 * 連邦財政収支（Federal Budget Balance）チャートコンポーネント
 *
 * Treasury FiscalData API から取得した MTS（Monthly Treasury Statement）データを表示
 * - 歳入（Receipts）: 棒グラフ（青）
 * - 歳出（Outlays）: 棒グラフ（赤）
 * - 財政収支（Deficit/Surplus）: 折れ線グラフ（オレンジ）
 */
import { useState, useMemo } from 'react'
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import { usePeriodFiltering, formatDateLabel, type PeriodType } from '../common/useChartData'
import { NoDataMessage } from '../common/ChartComponents'
import { CHART_COLORS, DARK_THEME, LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../common/chartConstants'
import type { FederalBudgetData, FederalBudgetItem } from '../../../../hooks/useDashboardData'

// Props型定義
interface FederalBudgetChartProps {
  data: FederalBudgetData | null
}

interface ChartDataItem {
  date: string
  receipts: number
  outlays: number
  deficit_surplus: number
  [key: string]: string | number | null | undefined
}

export default function FederalBudgetChart({ data }: FederalBudgetChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(20)

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataItem[]>(() => {
    if (!data || !data.data || data.data.length === 0) return []

    const result: ChartDataItem[] = data.data.map((item: FederalBudgetItem) => ({
      date: item.date,
      receipts: item.receipts,
      outlays: item.outlays,
      deficit_surplus: item.deficit_surplus,
    }))

    // 日付でソート（古い順）
    result.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return result
  }, [data])

  // 値フォーマット（十億ドル単位）
  const formatValue = (value: number) => {
    return `$${value.toFixed(1)}B`
  }

  // Y軸フォーマット
  const formatYAxis = (value: number) => {
    return `${value.toFixed(0)}B`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // X軸の表示間隔を動的に計算
  const xAxisInterval = useMemo(() => {
    const dataLength = filteredData.length
    if (dataLength <= 12) return 0
    if (dataLength <= 24) return 1
    if (dataLength <= 48) return 3
    if (dataLength <= 96) return 5
    return Math.floor(dataLength / 12)
  }, [filteredData.length])

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="連邦財政収支（Federal Budget Balance）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="連邦財政収支（Federal Budget Balance）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="federal-budget-chart">
      <ChartContainer
        title="連邦財政収支（Federal Budget Balance）"
        showPeriodSelector={false}
        dataSource="U.S. Treasury"
        sourceUrl="https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/"
        handbookId="federal-budget"
      >
        {/* 最新値表示 */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary, fontWeight: 'bold' }}>最新値</span>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>歳入:</span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: CHART_COLORS.primary }}>
                {latestValue?.receipts != null ? formatValue(latestValue.receipts) : '-'}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>歳出:</span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: CHART_COLORS.red }}>
                {latestValue?.outlays != null ? formatValue(latestValue.outlays) : '-'}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>財政収支:</span>
              <span
                style={{
                  fontSize: 16,
                  fontWeight: 'bold',
                  color: latestValue?.deficit_surplus != null && latestValue.deficit_surplus >= 0
                    ? CHART_COLORS.green
                    : CHART_COLORS.orange,
                }}
              >
                {latestValue?.deficit_surplus != null ? formatValue(latestValue.deficit_surplus) : '-'}
              </span>
            </div>

            {latestValue?.date && (
              <span style={{ fontSize: 12, color: TEXT_COLORS.tertiary }}>
                ({formatDateLabel(latestValue.date)})
              </span>
            )}
          </div>
        </div>

        <div style={{ marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
        </div>

        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart
            data={filteredData}
            margin={{ top: 10, right: 30, left: 10, bottom: 50 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke={DARK_THEME.borderLight}
              vertical={false}
            />
            <XAxis
              dataKey="date"
              tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
              tickLine={{ stroke: DARK_THEME.borderLight }}
              axisLine={{ stroke: DARK_THEME.borderLight }}
              tickFormatter={formatDateLabel}
              interval={xAxisInterval}
              angle={-45}
              textAnchor="end"
              height={60}
            />
            <YAxis
              tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
              tickLine={{ stroke: DARK_THEME.borderLight }}
              axisLine={{ stroke: DARK_THEME.borderLight }}
              tickFormatter={formatYAxis}
              width={60}
            />
            <ReferenceLine y={0} stroke={DARK_THEME.textSecondary} strokeWidth={1} />
            <RechartsTooltip
              content={({ active, payload, label }) => {
                if (!active || !payload || payload.length === 0) return null
                const dataPoint = payload[0]?.payload as ChartDataItem | undefined
                return (
                  <div
                    style={{
                      backgroundColor: DARK_THEME.bgTertiary,
                      border: `1px solid ${DARK_THEME.borderLight}`,
                      borderRadius: 8,
                      padding: '12px 16px',
                      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
                    }}
                  >
                    <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
                      {String(label).replace(/-/g, '/')}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
                          <span
                            style={{
                              display: 'inline-block',
                              width: 10,
                              height: 10,
                              borderRadius: 2,
                              backgroundColor: CHART_COLORS.primary,
                              marginRight: 6,
                            }}
                          />
                          歳入
                        </span>
                        <span style={{ fontWeight: 500, color: CHART_COLORS.primary }}>
                          {dataPoint?.receipts != null ? formatValue(dataPoint.receipts) : 'N/A'}
                        </span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
                          <span
                            style={{
                              display: 'inline-block',
                              width: 10,
                              height: 10,
                              borderRadius: 2,
                              backgroundColor: CHART_COLORS.red,
                              marginRight: 6,
                            }}
                          />
                          歳出
                        </span>
                        <span style={{ fontWeight: 500, color: CHART_COLORS.red }}>
                          {dataPoint?.outlays != null ? formatValue(dataPoint.outlays) : 'N/A'}
                        </span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
                          <span
                            style={{
                              display: 'inline-block',
                              width: 10,
                              height: 10,
                              borderRadius: 2,
                              backgroundColor: CHART_COLORS.orange,
                              marginRight: 6,
                            }}
                          />
                          財政収支
                        </span>
                        <span style={{ fontWeight: 500, color: dataPoint?.deficit_surplus != null && dataPoint.deficit_surplus >= 0 ? CHART_COLORS.green : CHART_COLORS.orange }}>
                          {dataPoint?.deficit_surplus != null ? formatValue(dataPoint.deficit_surplus) : 'N/A'}
                        </span>
                      </div>
                    </div>
                  </div>
                )
              }}
            />
            <Legend
              wrapperStyle={{ paddingTop: 20 }}
              formatter={(value) => <span style={{ color: DARK_THEME.textPrimary }}>{value}</span>}
            />
            <Bar
              dataKey="receipts"
              fill={CHART_COLORS.primary}
              name="歳入"
              opacity={0.8}
            />
            <Bar
              dataKey="outlays"
              fill={CHART_COLORS.red}
              name="歳出"
              opacity={0.8}
            />
            <Line
              type="monotone"
              dataKey="deficit_surplus"
              stroke={CHART_COLORS.orange}
              name="財政収支"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: CHART_COLORS.orange }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
