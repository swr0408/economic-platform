/**
 * カナダ貿易収支チャートコンポーネント
 *
 * 貿易収支（Trade Balance）、輸出・輸入の推移を表示
 *
 * データソース:
 * - Statistics Canada Table 12-10-0011-01
 * - Canadian international merchandise trade
 *
 * 発表スケジュール:
 * - 月次（対象月の約2ヶ月後）
 * - 発表時刻: 08:30 ET
 */
import { useState, useMemo } from 'react'
import { Tooltip as RechartsTooltip, ReferenceLine, XAxis, YAxis, CartesianGrid, ResponsiveContainer, ComposedChart, Bar, Line, Legend } from 'recharts'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// 共通モジュールのインポート
import {
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMonthlyTableData,
  formatDateLabel,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  ViewModeButtonGroup,
  MOM_LEGEND_DEFAULT,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'
import { DARK_THEME, CHART_COLORS } from '../../usa/common/chartConstants'

// 型定義
import type { CaTradeBalanceData } from '../../../../hooks/useDashboardData'

interface CanadaTradeBalanceChartProps {
  data: CaTradeBalanceData | null
}

type DataKind = 'balance' | 'exports_imports' | 'mom'
type DisplayMode = 'chart' | 'heatmap'

// 指標種別設定
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'balance', label: '貿易収支' },
  { mode: 'exports_imports', label: '輸出・輸入' },
  { mode: 'mom', label: '前月増減幅' },
]

// 表示モード設定
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

interface ChartDataItem {
  date: string
  value: number
  balance?: number
  exports?: number
  imports?: number
  mom_change?: number
  [key: string]: string | number | boolean | null | undefined
}

export default function CanadaTradeBalanceChart({ data }: CanadaTradeBalanceChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('balance')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    balance: 10 as PeriodType,
    exports_imports: 10 as PeriodType,
    mom: 10 as PeriodType,
  })

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataItem[]>(() => {
    if (!data?.data || data.data.length === 0) return []

    const formattedData: ChartDataItem[] = data.data.map((item) => {
      let value = 0
      switch (dataKind) {
        case 'balance':
        case 'exports_imports':
          value = item.balance ?? 0
          break
        case 'mom':
          // 前月増減幅
          value = item.mom_change ?? 0
          break
      }
      return {
        date: item.date,
        value,
        balance: item.balance,
        exports: item.exports,
        imports: item.imports,
        mom_change: item.mom_change,
      }
    })

    // 日付でソート（古い順）
    formattedData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return formattedData
  }, [data, dataKind])

  const formatMillions = (value: number) => {
    if (Math.abs(value) >= 1000) {
      return `${(value / 1000).toFixed(1)}B`
    }
    return `${value.toFixed(0)}M`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ（前月増減幅）
  const momTableData = useMonthlyTableData(
    chartData,
    (item) => item.mom_change,
    10
  )

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

  // 表示ラベルを取得
  const getDataKindLabel = (kind: DataKind) => {
    switch (kind) {
      case 'balance': return '貿易収支'
      case 'exports_imports': return '貿易収支'
      case 'mom': return '前月増減幅'
    }
  }

  // 最新値を取得（DataKindに応じて）
  const getLatestValue = () => {
    if (!latestValue) return undefined
    switch (dataKind) {
      case 'balance':
      case 'exports_imports':
        return latestValue.balance
      case 'mom':
        return latestValue.mom_change
    }
  }

  // 比較ページ用のキーを取得
  const getCompareKey = () => {
    switch (dataKind) {
      case 'balance':
      case 'exports_imports':
        return 'raw'
      case 'mom':
        return 'mom'
    }
  }

  return (
    <div id="ca-trade-balance-chart">
      <ChartContainer
        title="貿易収支"
        showPeriodSelector={false}
        dataSource="Statistics Canada"
        sourceUrl="https://www.statcan.gc.ca/en/subjects-start/international_trade"
        handbookId="trade-balance"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={getDataKindLabel(dataKind)}
          value={getLatestValue()}
          valueColor={CHART_COLORS.primary}
          date={latestValue?.date}
          nextRelease={data.next_release ? {
            date: data.next_release.date,
            label: data.next_release.time_jst ? `${data.next_release.time_jst} JST` : undefined
          } : null}
          format="number"
          decimals={dataKind === 'balance' || dataKind === 'exports_imports' ? 0 : 1}
          unit="M CAD"
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
                  {/* 上段: 指標種別 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      options={DATA_KIND_OPTIONS}
                      currentMode={dataKind}
                      onChange={setDataKind}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(`/compare?s=ca_trade_balance_${getCompareKey()}`, '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
                  {dataKind === 'mom' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 前月増減幅ヒートマップ */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTable
                      data={momTableData}
                      decimals={0}
                      showLegend={true}
                      legendItems={MOM_LEGEND_DEFAULT}
                      helperText="※ 直近10年間の前月増減幅データ（単位: M CAD）"
                    />
                  )}

                  {/* グラフ表示 */}
                  {!(dataKind === 'mom' && displayMode === 'heatmap') && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                      {dataKind === 'balance' ? (
                        // 貿易収支は棒グラフ
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
                              tickFormatter={formatMillions}
                              tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
                              tickLine={{ stroke: DARK_THEME.borderLight }}
                              axisLine={{ stroke: DARK_THEME.borderLight }}
                            />
                            <ReferenceLine y={0} stroke={DARK_THEME.textTertiary} strokeWidth={1} />
                            <Bar
                              dataKey="balance"
                              name="貿易収支"
                              fill={CHART_COLORS.primary}
                            />
                            <RechartsTooltip
                              content={({ active, payload, label }) => {
                                if (!active || !payload || payload.length === 0) return null
                                const dataItem = payload[0]?.payload as ChartDataItem
                                const balance = dataItem.balance ?? 0
                                const isNegative = balance < 0
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
                                          {balance.toLocaleString()}M CAD
                                        </span>
                                      </div>
                                      {dataItem.exports !== undefined && (
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                          <span style={{ color: '#f1f5f9', marginRight: 16 }}>輸出</span>
                                          <span style={{ fontWeight: 500, color: DARK_THEME.textPrimary }}>
                                            {dataItem.exports?.toLocaleString()}M CAD
                                          </span>
                                        </div>
                                      )}
                                      {dataItem.imports !== undefined && (
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                          <span style={{ color: '#f1f5f9', marginRight: 16 }}>輸入</span>
                                          <span style={{ fontWeight: 500, color: DARK_THEME.textPrimary }}>
                                            {dataItem.imports?.toLocaleString()}M CAD
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
                      ) : dataKind === 'exports_imports' ? (
                        // 輸出・輸入は線グラフ
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
                              tickFormatter={formatMillions}
                              tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
                              tickLine={{ stroke: DARK_THEME.borderLight }}
                              axisLine={{ stroke: DARK_THEME.borderLight }}
                              domain={['dataMin - 2000', 'dataMax + 2000']}
                            />
                            <Legend
                              wrapperStyle={{ paddingTop: 10 }}
                              formatter={(value) => <span style={{ color: DARK_THEME.textPrimary }}>{value}</span>}
                            />
                            <Line
                              type="monotone"
                              dataKey="exports"
                              name="輸出"
                              stroke={CHART_COLORS.positive}
                              strokeWidth={2}
                              dot={false}
                              connectNulls
                            />
                            <Line
                              type="monotone"
                              dataKey="imports"
                              name="輸入"
                              stroke={CHART_COLORS.orange}
                              strokeWidth={2}
                              dot={false}
                              connectNulls
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
                                      {dataItem.exports !== undefined && (
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                          <span style={{ color: '#f1f5f9', marginRight: 16 }}>
                                            <span
                                              style={{
                                                display: 'inline-block',
                                                width: 10,
                                                height: 10,
                                                borderRadius: 2,
                                                backgroundColor: CHART_COLORS.positive,
                                                marginRight: 6,
                                              }}
                                            />
                                            輸出
                                          </span>
                                          <span style={{ fontWeight: 500, color: CHART_COLORS.positive }}>
                                            {dataItem.exports?.toLocaleString()}M CAD
                                          </span>
                                        </div>
                                      )}
                                      {dataItem.imports !== undefined && (
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                          <span style={{ color: '#f1f5f9', marginRight: 16 }}>
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
                                            輸入
                                          </span>
                                          <span style={{ fontWeight: 500, color: CHART_COLORS.orange }}>
                                            {dataItem.imports?.toLocaleString()}M CAD
                                          </span>
                                        </div>
                                      )}
                                      {dataItem.balance !== undefined && (
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: `1px solid ${DARK_THEME.borderLight}`, paddingTop: 4, marginTop: 4 }}>
                                          <span style={{ color: '#f1f5f9', marginRight: 16 }}>貿易収支</span>
                                          <span style={{ fontWeight: 500, color: (dataItem.balance ?? 0) < 0 ? CHART_COLORS.negative : CHART_COLORS.primary }}>
                                            {dataItem.balance?.toLocaleString()}M CAD
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
                      ) : (
                        // 前月増減幅は棒グラフ
                        <StandardBarChart
                          data={filteredData}
                          bars={[
                            { dataKey: 'value', color: CHART_COLORS.primary, name: '前月増減幅' }
                          ]}
                          height={450}
                          showZeroLine={true}
                          yAxisFormatter={formatMillions}
                          tooltipValueFormatter={(v) => `${v.toLocaleString()}M CAD`}
                          yDomain={['dataMin - 500', 'dataMax + 500']}
                        />
                      )}
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="ca_international_merchandise_trade" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
