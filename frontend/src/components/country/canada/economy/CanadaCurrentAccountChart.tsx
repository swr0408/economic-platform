/**
 * カナダ経常収支チャートコンポーネント
 *
 * 経常収支（Current Account Balance）の推移を表示
 *
 * データソース:
 * - Statistics Canada Table 36-10-0018-01
 * - Balance of international payments, current account
 *
 * 発表スケジュール:
 * - 四半期ごと（対象期間終了の約2ヶ月後）
 * - 発表時刻: 08:30 ET
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
  useQuarterlyTableData,
  formatDateLabel,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  ViewModeButtonGroup,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { QuarterlyTable } from '../../usa/common/QuarterlyTable'
import { DARK_THEME, CHART_COLORS } from '../../usa/common/chartConstants'

// 型定義
import type { CaCurrentAccountData } from '../../../../hooks/useDashboardData'

interface CanadaCurrentAccountChartProps {
  data: CaCurrentAccountData | null
}

type ViewMode = 'raw' | 'qoq' | 'qoq_table'

interface ChartDataItem {
  date: string
  value: number
  qoq_change?: number
  [key: string]: string | number | boolean | null | undefined
}

export default function CanadaCurrentAccountChart({ data }: CanadaCurrentAccountChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('raw')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    raw: 'default' as PeriodType,
    qoq: 'default' as PeriodType,
    qoq_table: 'default' as PeriodType,
  })

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataItem[]>(() => {
    if (!data?.data || data.data.length === 0) return []

    const currentViewMode = viewMode === 'qoq_table' ? 'qoq' : viewMode

    const formattedData: ChartDataItem[] = data.data.map((item) => {
      let value = 0
      switch (currentViewMode) {
        case 'raw':
          value = item.value ?? 0
          break
        case 'qoq':
          // 前期比変化額
          value = item.qoq_change ?? 0
          break
      }
      return {
        date: item.date,
        value,
        rawValue: item.value,
        qoq_change: item.qoq_change,
      }
    })

    // 日付でソート（古い順）
    formattedData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return formattedData
  }, [data, viewMode])

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

  // テーブル用データ（前期比変化額）
  const qoqTableData = useQuarterlyTableData(
    chartData,
    (item) => item.qoq_change,
    10
  )

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
    { mode: 'raw' as ViewMode, label: '経常収支' },
    { mode: 'qoq' as ViewMode, label: '前期比変化額' },
    { mode: 'qoq_table' as ViewMode, label: '前期比変化額（テーブル）' },
  ]

  // 表示ラベルを取得
  const getViewModeLabel = (mode: ViewMode) => {
    switch (mode) {
      case 'raw': return '経常収支'
      case 'qoq': return '前期比変化額'
      case 'qoq_table': return '前期比変化額'
    }
  }

  // 最新値を取得（ViewModeに応じて）
  const getLatestValue = () => {
    if (!latestValue) return undefined
    switch (viewMode) {
      case 'raw':
        return latestValue.value
      case 'qoq':
      case 'qoq_table':
        return latestValue.qoq_change
    }
  }

  // 比較ページ用のキーを取得
  const getCompareKey = () => {
    switch (viewMode) {
      case 'raw':
        return 'raw'
      case 'qoq':
      case 'qoq_table':
        return 'qoq'
    }
  }

  return (
    <div id="ca-current-account-chart">
      <ChartContainer
        title="経常収支"
        showPeriodSelector={false}
        dataSource="Statistics Canada"
        sourceUrl="https://www.statcan.gc.ca/en/subjects-start/international_trade"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={getViewModeLabel(viewMode)}
          value={getLatestValue()}
          valueColor={CHART_COLORS.primary}
          date={latestValue?.date}
          nextRelease={data.next_release ? {
            date: data.next_release.date,
            label: data.next_release.time_jst ? `${data.next_release.time_jst} JST` : undefined
          } : null}
          format="number"
          decimals={viewMode === 'raw' ? 0 : 1}
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      options={viewModeOptions}
                      currentMode={viewMode}
                      onChange={setViewMode}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(`/compare?s=ca_current_account_${getCompareKey()}`, '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 前期比変化額テーブル */}
                  {viewMode === 'qoq_table' && (
                    <QuarterlyTable
                      data={qoqTableData}
                      decimals={0}
                      showLegend={false}
                      helperText="※ 直近10年間の前期比変化額データ（単位: M CAD）"
                    />
                  )}

                  {/* グラフ表示 */}
                  {viewMode !== 'qoq_table' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                      {viewMode === 'raw' ? (
                        // 経常収支は棒グラフ
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
                              dataKey="rawValue"
                              name="経常収支"
                              fill={CHART_COLORS.primary}
                            />
                            <RechartsTooltip
                              content={({ active, payload, label }) => {
                                if (!active || !payload || payload.length === 0) return null
                                const dataItem = payload[0]?.payload as ChartDataItem
                                const value = (dataItem.rawValue as number) ?? 0
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
                                          {value.toLocaleString()}M CAD
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
                        // 前期比変化額は棒グラフ
                        <StandardBarChart
                          data={filteredData}
                          bars={[
                            { dataKey: 'value', color: CHART_COLORS.primary, name: '前期比変化額' }
                          ]}
                          height={450}
                          showZeroLine={true}
                          yAxisFormatter={formatMillions}
                          tooltipValueFormatter={(v) => `${v.toLocaleString()}M CAD`}
                          yDomain={['dataMin - 2000', 'dataMax + 2000']}
                        />
                      )}
                    </>
                  )}
                </>
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
