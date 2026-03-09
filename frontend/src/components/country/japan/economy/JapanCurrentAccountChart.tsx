/**
 * 日本経常収支チャートコンポーネント
 *
 * 経常収支（Current Account Balance）の推移を表示
 *
 * データソース:
 * - 財務省国際収支統計
 * - https://www.mof.go.jp/policy/international_policy/reference/balance_of_payments/
 *
 * 単位:
 * - API: 億円（100 million yen）
 * - 表示: 兆円（trillion yen）に変換
 * - 例: 7288億円 → 0.73兆円
 *
 * 発表スケジュール:
 * - 毎月上旬発表（前々月データ）
 */
import { useState, useMemo } from 'react'
import { Tooltip as RechartsTooltip, ReferenceLine, XAxis, YAxis, CartesianGrid, ResponsiveContainer, ComposedChart, Bar } from 'recharts'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import {
  usePeriodFiltering,
  useViewModePeriodManagement,
  formatDateLabel,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import { DARK_THEME, CHART_COLORS } from '../../usa/common/chartConstants'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// 型定義
import type { JapanCurrentAccountData } from '../../../../hooks/useDashboardData'

interface JapanCurrentAccountChartProps {
  data: JapanCurrentAccountData | null
}

type ViewMode = 'current_account' | 'breakdown'

interface ChartDataItem {
  date: string
  value: number
  current_account: number
  goods_services?: number | null
  primary_income?: number | null
  secondary_income?: number | null
  [key: string]: string | number | boolean | null | undefined
}

export default function JapanCurrentAccountChart({ data }: JapanCurrentAccountChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('current_account')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    current_account: 20 as PeriodType,
    breakdown: 20 as PeriodType,
  })

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataItem[]>(() => {
    if (!data?.data || data.data.length === 0) return []

    const formattedData: ChartDataItem[] = data.data.map((item) => ({
      date: item.date,
      value: item.current_account,
      current_account: item.current_account,
      goods_services: item.goods_services,
      primary_income: item.primary_income,
      secondary_income: item.secondary_income,
    }))

    // 日付でソート（古い順）
    formattedData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return formattedData
  }, [data])

  // 値フォーマット（兆円表示）
  // データは億円（100 million yen）単位 → 兆円に変換して表示
  // 例: 7288億円 → 0.73兆円、36741億円 → 3.67兆円
  const formatTrillionYen = (value: number) => {
    // 億円 → 兆円に変換（10000億円 = 1兆円）
    const trillionValue = value / 10000
    return `${trillionValue.toFixed(2)}兆円`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="経常収支" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="経常収支" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const viewModeOptions = [
    { mode: 'current_account' as ViewMode, label: '経常収支' },
    { mode: 'breakdown' as ViewMode, label: '内訳' },
  ]

  // 表示ラベルを取得
  const getViewModeLabel = (mode: ViewMode) => {
    switch (mode) {
      case 'current_account': return '経常収支'
      case 'breakdown': return '経常収支内訳'
    }
  }

  return (
    <div id="japan-current-account-chart">
      <ChartContainer
        title="経常収支"
        showPeriodSelector={false}
        dataSource="財務省"
        sourceUrl="https://www.mof.go.jp/policy/international_policy/reference/balance_of_payments/"
      >
        {/* 最新値表示（兆円単位） */}
        <SimpleLatestValueBox
          label={getViewModeLabel(viewMode)}
          value={latestValue?.current_account != null ? latestValue.current_account / 10000 : null}
          valueColor={latestValue && latestValue.current_account < 0 ? CHART_COLORS.negative : CHART_COLORS.primary}
          date={latestValue?.date}
          nextRelease={data.next_release?.date ? {
            date: data.next_release.date,
            label: data.next_release.time_jst ? `${data.next_release.time_jst} JST` : undefined
          } : null}
          format="number"
          decimals={2}
          unit="兆円"
        />

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      options={viewModeOptions}
                      currentMode={viewMode}
                      onChange={setViewMode}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=japan_current_account', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                  {viewMode === 'current_account' ? (
                    // 経常収支合計の棒グラフ
                    <ResponsiveContainer width="100%" height={450}>
                      <ComposedChart
                        data={filteredData}
                        margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.borderLight} />
                        <XAxis
                          dataKey="date"
                          tickFormatter={formatDateLabel}
                          tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
                          tickLine={{ stroke: DARK_THEME.borderLight }}
                          axisLine={{ stroke: DARK_THEME.borderLight }}
                        />
                        <YAxis
                          tickFormatter={formatTrillionYen}
                          tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
                          tickLine={{ stroke: DARK_THEME.borderLight }}
                          axisLine={{ stroke: DARK_THEME.borderLight }}
                        />
                        <ReferenceLine y={0} stroke={DARK_THEME.textTertiary} strokeWidth={1} />
                        <Bar
                          dataKey="current_account"
                          name="経常収支"
                          fill={CHART_COLORS.primary}
                        />
                        <RechartsTooltip
                          content={({ active, payload, label }) => {
                            if (!active || !payload || payload.length === 0) return null
                            const dataItem = payload[0]?.payload as ChartDataItem
                            const value = dataItem.current_account ?? 0
                            const isNegative = value < 0
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
                                  {formatDateLabel(String(label))}
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <span style={{ color: '#f1f5f9', marginRight: 16 }}>
                                      <span
                                        style={{
                                          display: 'inline-block',
                                          width: 10,
                                          height: 10,
                                          borderRadius: 2,
                                          backgroundColor: isNegative ? CHART_COLORS.negative : CHART_COLORS.primary,
                                          marginRight: 6,
                                        }}
                                      />
                                      経常収支
                                    </span>
                                    <span style={{ fontWeight: 500, color: isNegative ? CHART_COLORS.negative : CHART_COLORS.primary }}>
                                      {(value / 10000).toFixed(2)}兆円
                                    </span>
                                  </div>
                                </div>
                              </div>
                            )
                          }}
                        />
                      </ComposedChart>
                    </ResponsiveContainer>
                  ) : (
                    // 内訳表示（積み上げ棒グラフ）
                    <ResponsiveContainer width="100%" height={450}>
                      <ComposedChart
                        data={filteredData}
                        margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.borderLight} />
                        <XAxis
                          dataKey="date"
                          tickFormatter={formatDateLabel}
                          tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
                          tickLine={{ stroke: DARK_THEME.borderLight }}
                          axisLine={{ stroke: DARK_THEME.borderLight }}
                        />
                        <YAxis
                          tickFormatter={formatTrillionYen}
                          tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
                          tickLine={{ stroke: DARK_THEME.borderLight }}
                          axisLine={{ stroke: DARK_THEME.borderLight }}
                        />
                        <ReferenceLine y={0} stroke={DARK_THEME.textTertiary} strokeWidth={1} />
                        <Bar
                          dataKey="goods_services"
                          name="商品・サービス収支"
                          stackId="a"
                          fill="#f59e0b"
                        />
                        <Bar
                          dataKey="primary_income"
                          name="一次所得収支"
                          stackId="a"
                          fill="#10b981"
                        />
                        <Bar
                          dataKey="secondary_income"
                          name="二次所得収支"
                          stackId="a"
                          fill="#8b5cf6"
                        />
                        <RechartsTooltip
                          content={({ active, payload, label }) => {
                            if (!active || !payload || payload.length === 0) return null
                            const dataItem = payload[0]?.payload as ChartDataItem
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
                                  {formatDateLabel(String(label))}
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
                                  {/* 経常収支合計 */}
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                                    <span style={{ color: '#f1f5f9', marginRight: 16, fontWeight: 600 }}>
                                      経常収支合計
                                    </span>
                                    <span style={{
                                      fontWeight: 600,
                                      color: (dataItem.current_account ?? 0) < 0 ? CHART_COLORS.negative : CHART_COLORS.primary
                                    }}>
                                      {((dataItem.current_account ?? 0) / 10000).toFixed(2)}兆円
                                    </span>
                                  </div>
                                  {/* 商品・サービス収支 */}
                                  {dataItem.goods_services !== undefined && dataItem.goods_services !== null && (
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                      <span style={{ color: '#f1f5f9', marginRight: 16 }}>
                                        <span
                                          style={{
                                            display: 'inline-block',
                                            width: 10,
                                            height: 10,
                                            borderRadius: 2,
                                            backgroundColor: '#f59e0b',
                                            marginRight: 6,
                                          }}
                                        />
                                        商品・サービス収支
                                      </span>
                                      <span style={{ fontWeight: 500, color: '#f59e0b' }}>
                                        {(dataItem.goods_services / 10000).toFixed(2)}兆円
                                      </span>
                                    </div>
                                  )}
                                  {/* 一次所得収支 */}
                                  {dataItem.primary_income !== undefined && dataItem.primary_income !== null && (
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                      <span style={{ color: '#f1f5f9', marginRight: 16 }}>
                                        <span
                                          style={{
                                            display: 'inline-block',
                                            width: 10,
                                            height: 10,
                                            borderRadius: 2,
                                            backgroundColor: '#10b981',
                                            marginRight: 6,
                                          }}
                                        />
                                        一次所得収支
                                      </span>
                                      <span style={{ fontWeight: 500, color: '#10b981' }}>
                                        {(dataItem.primary_income / 10000).toFixed(2)}兆円
                                      </span>
                                    </div>
                                  )}
                                  {/* 二次所得収支 */}
                                  {dataItem.secondary_income !== undefined && dataItem.secondary_income !== null && (
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                      <span style={{ color: '#f1f5f9', marginRight: 16 }}>
                                        <span
                                          style={{
                                            display: 'inline-block',
                                            width: 10,
                                            height: 10,
                                            borderRadius: 2,
                                            backgroundColor: '#8b5cf6',
                                            marginRight: 6,
                                          }}
                                        />
                                        二次所得収支
                                      </span>
                                      <span style={{ fontWeight: 500, color: '#8b5cf6' }}>
                                        {(dataItem.secondary_income / 10000).toFixed(2)}兆円
                                      </span>
                                    </div>
                                  )}
                                </div>
                              </div>
                            )
                          }}
                        />
                      </ComposedChart>
                    </ResponsiveContainer>
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="japan_current_account" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
