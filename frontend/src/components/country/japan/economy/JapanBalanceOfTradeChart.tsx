/**
 * 日本貿易収支チャートコンポーネント
 *
 * 貿易収支（Balance of Trade）の推移を表示（通関ベース）
 *
 * データソース:
 * - 財務省貿易統計（税関）
 * - https://www.customs.go.jp/toukei/suii/html/time.htm
 *
 * 通関ベース vs 国際収支ベースの違い:
 * - 通関ベース: 税関を通過した時点で計上、輸入はCIF価格
 * - 国際収支ベース: 所有権移転時に計上、輸入はFOB価格
 * - FMP/Investing.comは通関ベースの数値を報告
 *
 * 単位:
 * - API: 億円（100 million yen）
 * - 表示: 億円（そのまま表示）
 * - 例: -17,922億円
 *
 * 発表スケジュール:
 * - 毎月中旬発表
 */
import { useState, useMemo } from 'react'
import { Tooltip as RechartsTooltip, ReferenceLine, XAxis, YAxis, CartesianGrid, ResponsiveContainer, ComposedChart, Bar, Line } from 'recharts'
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
import type { JapanBalanceOfTradeData } from '../../../../hooks/useDashboardData'

interface JapanBalanceOfTradeChartProps {
  data: JapanBalanceOfTradeData | null
}

type ViewMode = 'trade_balance' | 'exports_imports'

interface ChartDataItem {
  date: string
  value: number
  trade_balance: number
  exports?: number | null
  imports?: number | null
  [key: string]: string | number | boolean | null | undefined
}

export default function JapanBalanceOfTradeChart({ data }: JapanBalanceOfTradeChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('trade_balance')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    trade_balance: 20 as PeriodType,
    exports_imports: 20 as PeriodType,
  })

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataItem[]>(() => {
    if (!data?.data || data.data.length === 0) return []

    const formattedData: ChartDataItem[] = data.data.map((item) => ({
      date: item.date,
      value: item.trade_balance,
      trade_balance: item.trade_balance,
      exports: item.exports,
      imports: item.imports,
    }))

    // 日付でソート（古い順）
    formattedData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return formattedData
  }, [data])

  // 値フォーマット（億円表示）
  const formatOkuYen = (value: number) => {
    return `${value.toLocaleString()}億円`
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
    return <LoadingChart title="貿易収支" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="貿易収支" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const viewModeOptions = [
    { mode: 'trade_balance' as ViewMode, label: '貿易収支' },
    { mode: 'exports_imports' as ViewMode, label: '輸出入' },
  ]

  // 表示ラベルを取得
  const getViewModeLabel = (mode: ViewMode) => {
    switch (mode) {
      case 'trade_balance': return '貿易収支'
      case 'exports_imports': return '輸出入'
    }
  }

  return (
    <div id="japan-balance-of-trade-chart">
      <ChartContainer
        title="貿易収支"
        showPeriodSelector={false}
        dataSource="財務省貿易統計（税関）"
        sourceUrl="https://www.customs.go.jp/toukei/suii/html/time.htm"
      >
        {/* 最新値表示（億円単位） */}
        <SimpleLatestValueBox
          label={getViewModeLabel(viewMode)}
          value={latestValue?.trade_balance}
          valueColor={latestValue && latestValue.trade_balance < 0 ? CHART_COLORS.negative : CHART_COLORS.primary}
          date={latestValue?.date}
          nextRelease={data.next_release?.date ? {
            date: data.next_release.date,
            label: data.next_release.time_jst ? `${data.next_release.time_jst} JST` : undefined
          } : null}
          format="number"
          decimals={0}
          unit="億円"
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
                        onClick={() => window.open('/compare?s=japan_balance_of_trade', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                  {viewMode === 'trade_balance' ? (
                    // 貿易収支の棒グラフ
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
                          tickFormatter={formatOkuYen}
                          tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
                          tickLine={{ stroke: DARK_THEME.borderLight }}
                          axisLine={{ stroke: DARK_THEME.borderLight }}
                        />
                        <ReferenceLine y={0} stroke={DARK_THEME.textTertiary} strokeWidth={1} />
                        <Bar
                          dataKey="trade_balance"
                          name="貿易収支"
                          fill={CHART_COLORS.primary}
                        />
                        <RechartsTooltip
                          content={({ active, payload, label }) => {
                            if (!active || !payload || payload.length === 0) return null
                            const dataItem = payload[0]?.payload as ChartDataItem
                            const value = dataItem.trade_balance ?? 0
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
                                      貿易収支
                                    </span>
                                    <span style={{ fontWeight: 500, color: isNegative ? CHART_COLORS.negative : CHART_COLORS.primary }}>
                                      {value.toLocaleString()}億円
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
                    // 輸出入表示（折れ線グラフ）
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
                          tickFormatter={formatOkuYen}
                          tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
                          tickLine={{ stroke: DARK_THEME.borderLight }}
                          axisLine={{ stroke: DARK_THEME.borderLight }}
                          domain={['dataMin - 2000', 'dataMax + 2000']}
                        />
                        <Line
                          type="monotone"
                          dataKey="exports"
                          name="輸出"
                          stroke="#10b981"
                          strokeWidth={2}
                          dot={false}
                        />
                        <Line
                          type="monotone"
                          dataKey="imports"
                          name="輸入"
                          stroke="#f59e0b"
                          strokeWidth={2}
                          dot={false}
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
                                  {/* 貿易収支 */}
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                                    <span style={{ color: '#f1f5f9', marginRight: 16, fontWeight: 600 }}>
                                      貿易収支
                                    </span>
                                    <span style={{
                                      fontWeight: 600,
                                      color: (dataItem.trade_balance ?? 0) < 0 ? CHART_COLORS.negative : CHART_COLORS.primary
                                    }}>
                                      {(dataItem.trade_balance ?? 0).toLocaleString()}億円
                                    </span>
                                  </div>
                                  {/* 輸出 */}
                                  {dataItem.exports !== undefined && dataItem.exports !== null && (
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
                                        輸出
                                      </span>
                                      <span style={{ fontWeight: 500, color: '#10b981' }}>
                                        {dataItem.exports.toLocaleString()}億円
                                      </span>
                                    </div>
                                  )}
                                  {/* 輸入 */}
                                  {dataItem.imports !== undefined && dataItem.imports !== null && (
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
                                        輸入
                                      </span>
                                      <span style={{ fontWeight: 500, color: '#f59e0b' }}>
                                        {dataItem.imports.toLocaleString()}億円
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
                <MarketImpactTab indicatorId="japan_balance_of_trade" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
