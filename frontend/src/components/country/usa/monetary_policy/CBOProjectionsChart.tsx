/**
 * CBO財政見通し（CBO Budget Projections）チャートコンポーネント
 *
 * Congressional Budget Office (CBO) のベースライン見通しデータを表示
 * - 債務（Debt）: 棒グラフ
 * - 歳入（Revenue）: 折れ線
 * - 歳出（Outlay）: 折れ線
 * - 財政赤字（Deficit）: 棒グラフ（マイナス値）
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
import { Radio } from 'antd'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'

// 共通モジュールのインポート
import { NoDataMessage } from '../common/ChartComponents'
import { CHART_COLORS, DARK_THEME, LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../common/chartConstants'
import type { CBOProjectionsData } from '../../../../hooks/useDashboardData'

// Props型定義
interface CBOProjectionsChartProps {
  data: CBOProjectionsData | null
}

type ViewType = 'deficit_debt' | 'revenue_outlay'

interface ChartDataItem {
  fiscal_year: number
  debt?: number
  deficit?: number
  revenue?: number
  outlay?: number
}

export default function CBOProjectionsChart({ data }: CBOProjectionsChartProps) {
  const [viewType, setViewType] = useState<ViewType>('deficit_debt')

  // データをチャート用に変換
  const chartData = useMemo<ChartDataItem[]>(() => {
    if (!data || !data.data) return []

    const { debt, deficit, revenue, outlay } = data.data
    const years = data.projection_years || []

    return years.map((year) => {
      const debtItem = debt?.find((d) => d.fiscal_year === year)
      const deficitItem = deficit?.find((d) => d.fiscal_year === year)
      const revenueItem = revenue?.find((d) => d.fiscal_year === year)
      const outlayItem = outlay?.find((d) => d.fiscal_year === year)

      return {
        fiscal_year: year,
        debt: debtItem?.value,
        deficit: deficitItem?.value,
        revenue: revenueItem?.value,
        outlay: outlayItem?.value,
      }
    })
  }, [data])

  // 値フォーマット（兆ドル単位）
  const formatValueTrillion = (value: number) => {
    return `$${(value / 1000).toFixed(1)}T`
  }

  // 値フォーマット（十億ドル単位）
  const formatValueBillion = (value: number) => {
    return `$${value.toFixed(0)}B`
  }

  // Y軸フォーマット（兆ドル単位）
  const formatYAxisTrillion = (value: number) => {
    return `${(value / 1000).toFixed(1)}T`
  }

  // Y軸フォーマット（十億ドル単位）
  const formatYAxisBillion = (value: number) => {
    return `${value.toFixed(0)}B`
  }

  const hasData = chartData.length > 0

  // 最新の見通し値（最終年度）
  const latestProjection = chartData.length > 0 ? chartData[chartData.length - 1] : null
  const firstYear = chartData.length > 0 ? chartData[0] : null

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="CBO財政見通し（CBO Budget Projections）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="CBO財政見通し（CBO Budget Projections）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="cbo-projections-chart">
      <ChartContainer
        title="CBO財政見通し（CBO Budget Projections）"
        showPeriodSelector={false}
        dataSource="CBO"
        sourceUrl="https://github.com/US-CBO/eval-projections"
        handbookId="cbo-projections"
      >
        {/* ベースライン日付表示 */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary, fontWeight: 'bold' }}>
              ベースライン: {data.latest_baseline_date || '-'}
            </span>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>FY{firstYear?.fiscal_year}債務:</span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: CHART_COLORS.cyan }}>
                {firstYear?.debt != null ? formatValueTrillion(firstYear.debt) : '-'}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>→ FY{latestProjection?.fiscal_year}:</span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: CHART_COLORS.cyan }}>
                {latestProjection?.debt != null ? formatValueTrillion(latestProjection.debt) : '-'}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>FY{firstYear?.fiscal_year}赤字:</span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: CHART_COLORS.orange }}>
                {firstYear?.deficit != null ? formatValueBillion(Math.abs(firstYear.deficit)) : '-'}
              </span>
            </div>
          </div>
        </div>

        {/* ビュー切り替え */}
        <div style={{ marginBottom: 16 }}>
          <Radio.Group
            value={viewType}
            onChange={(e) => setViewType(e.target.value)}
            buttonStyle="solid"
            size="middle"
          >
            <Radio.Button value="deficit_debt">財政赤字・債務</Radio.Button>
            <Radio.Button value="revenue_outlay">歳入・歳出</Radio.Button>
          </Radio.Group>
        </div>

        {viewType === 'deficit_debt' ? (
          <ResponsiveContainer width="100%" height={450}>
            <ComposedChart
              data={chartData}
              margin={{ top: 20, right: 60, left: 20, bottom: 20 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke={DARK_THEME.borderLight}
                vertical={false}
              />
              <XAxis
                dataKey="fiscal_year"
                tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
                tickLine={{ stroke: DARK_THEME.borderLight }}
                axisLine={{ stroke: DARK_THEME.borderLight }}
                tickFormatter={(value) => `FY${value}`}
              />
              <YAxis
                yAxisId="left"
                tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
                tickLine={{ stroke: DARK_THEME.borderLight }}
                axisLine={{ stroke: DARK_THEME.borderLight }}
                tickFormatter={formatYAxisBillion}
                width={70}
                label={{ value: '赤字 (B)', angle: -90, position: 'insideLeft', fill: DARK_THEME.textSecondary, fontSize: 11 }}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
                tickLine={{ stroke: DARK_THEME.borderLight }}
                axisLine={{ stroke: DARK_THEME.borderLight }}
                tickFormatter={formatYAxisTrillion}
                width={70}
                label={{ value: '債務 (T)', angle: 90, position: 'insideRight', fill: DARK_THEME.textSecondary, fontSize: 11 }}
              />
              <ReferenceLine y={0} yAxisId="left" stroke={DARK_THEME.textSecondary} strokeWidth={1} />
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
                        FY{label}
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
                                backgroundColor: CHART_COLORS.orange,
                                marginRight: 6,
                              }}
                            />
                            財政赤字
                          </span>
                          <span style={{ fontWeight: 500, color: CHART_COLORS.orange }}>
                            {dataPoint?.deficit != null ? formatValueBillion(Math.abs(dataPoint.deficit)) : 'N/A'}
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
                                backgroundColor: CHART_COLORS.cyan,
                                marginRight: 6,
                              }}
                            />
                            債務残高
                          </span>
                          <span style={{ fontWeight: 500, color: CHART_COLORS.cyan }}>
                            {dataPoint?.debt != null ? formatValueTrillion(dataPoint.debt) : 'N/A'}
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
                yAxisId="left"
                dataKey="deficit"
                fill={CHART_COLORS.orange}
                name="財政赤字"
                opacity={0.8}
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="debt"
                stroke={CHART_COLORS.cyan}
                name="債務残高"
                strokeWidth={2}
                dot={{ r: 3, fill: CHART_COLORS.cyan }}
                activeDot={{ r: 5, fill: CHART_COLORS.cyan }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        ) : (
          <ResponsiveContainer width="100%" height={450}>
            <ComposedChart
              data={chartData}
              margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke={DARK_THEME.borderLight}
                vertical={false}
              />
              <XAxis
                dataKey="fiscal_year"
                tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
                tickLine={{ stroke: DARK_THEME.borderLight }}
                axisLine={{ stroke: DARK_THEME.borderLight }}
                tickFormatter={(value) => `FY${value}`}
              />
              <YAxis
                tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
                tickLine={{ stroke: DARK_THEME.borderLight }}
                axisLine={{ stroke: DARK_THEME.borderLight }}
                tickFormatter={formatYAxisTrillion}
                width={60}
              />
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
                        FY{label}
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
                            {dataPoint?.revenue != null ? formatValueTrillion(dataPoint.revenue) : 'N/A'}
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
                            {dataPoint?.outlay != null ? formatValueTrillion(dataPoint.outlay) : 'N/A'}
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
              <Line
                type="monotone"
                dataKey="revenue"
                stroke={CHART_COLORS.primary}
                name="歳入"
                strokeWidth={2}
                dot={{ r: 3, fill: CHART_COLORS.primary }}
                activeDot={{ r: 5, fill: CHART_COLORS.primary }}
              />
              <Line
                type="monotone"
                dataKey="outlay"
                stroke={CHART_COLORS.red}
                name="歳出"
                strokeWidth={2}
                dot={{ r: 3, fill: CHART_COLORS.red }}
                activeDot={{ r: 5, fill: CHART_COLORS.red }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </ChartContainer>
    </div>
  )
}
