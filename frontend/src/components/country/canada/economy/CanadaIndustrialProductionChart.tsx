/**
 * カナダ鉱工業生産チャートコンポーネント
 *
 * 鉱工業生産成長率（前月比・前年比）の推移を表示
 *
 * データソース:
 * - Statistics Canada Table 36-10-0434-01
 * - Industrial production [T010]（SAAR, Chained 2017 dollars）
 *
 * 発表スケジュール:
 * - 月次（GDP by industry と同時発表）
 * - 発表時刻: 08:30 ET
 *
 * 注意:
 * - SAAR版を採用（ノイズが少なく、StatCanのDaily解説と整合）
 * - Trading Economicsとは値が異なる場合あり
 */
import { useState, useMemo } from 'react'
import { Tooltip as RechartsTooltip } from 'recharts'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
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
import type { CaIndustrialProductionData } from '../../../../hooks/useDashboardData'

interface CanadaIndustrialProductionChartProps {
  data: CaIndustrialProductionData | null
}

type DataKind = 'yoy' | 'mom'
type DisplayMode = 'chart' | 'heatmap'

// 指標種別設定
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'mom', label: '前月比' },
  { mode: 'yoy', label: '前年比' },
]

// 表示モード設定
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

interface ChartDataItem {
  date: string
  value: number
  mom?: number
  yoy?: number
  [key: string]: string | number | boolean | null | undefined
}

export default function CanadaIndustrialProductionChart({ data }: CanadaIndustrialProductionChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    mom: 10 as PeriodType,
    yoy: 10 as PeriodType,
  })

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataItem[]>(() => {
    if (!data?.data || data.data.length === 0) return []

    const formattedData: ChartDataItem[] = data.data.map((item) => ({
      date: item.date,
      value: dataKind === 'mom' ? (item.mom ?? 0) : (item.yoy ?? 0),
      mom: item.mom,
      yoy: item.yoy,
    }))

    // 日付でソート（古い順）
    formattedData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return formattedData
  }, [data, dataKind])

  const formatPercentage = (value: number) => {
    return `${value.toFixed(2)}%`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ（前月比）
  const momTableData = useMonthlyTableData(
    chartData,
    (item) => item.mom,
    10
  )

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="鉱工業生産" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="鉱工業生産" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 表示ラベルを取得
  const getDataKindLabel = (kind: DataKind) => {
    switch (kind) {
      case 'mom': return '前月比'
      case 'yoy': return '前年比'
    }
  }

  // 最新値を取得（DataKindに応じて）
  const getLatestValue = () => {
    if (!latestValue) return undefined
    switch (dataKind) {
      case 'mom': return latestValue.mom
      case 'yoy': return latestValue.yoy
    }
  }

  // 比較ページ用のキーを取得
  const getCompareKey = () => {
    switch (dataKind) {
      case 'mom': return 'mom'
      case 'yoy': return 'yoy'
    }
  }

  return (
    <div id="ca-industrial-production-chart">
      <ChartContainer
        title="鉱工業生産"
        showPeriodSelector={false}
        dataSource="Statistics Canada"
        sourceUrl="https://www.statcan.gc.ca/en/subjects-start/economic_accounts"
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
          format="percent"
          decimals={2}
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
                        onClick={() => window.open(`/compare?s=ca_industrial_production_${getCompareKey()}`, '_blank')}
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

                  {/* 前月比ヒートマップ */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTable
                      data={momTableData}
                      decimals={2}
                      showLegend={true}
                      legendItems={MOM_LEGEND_DEFAULT}
                      helperText="※ 直近10年間の前月比データ（単位: %）"
                    />
                  )}

                  {/* 前月比グラフ（棒グラフ） */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'value', color: CHART_COLORS.primary, name: '前月比' }
                        ]}
                        height={450}
                        showZeroLine={true}
                        yAxisFormatter={(v: number) => `${v.toFixed(1)}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                      />
                    </>
                  )}

                  {/* 前年比グラフ（線グラフ） */}
                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <ZoomableChart
                        data={filteredData}
                        dataKey="value"
                        color={CHART_COLORS.primary}
                        name="鉱工業生産（前年比）"
                        height={450}
                        tickFormatter={formatPercentage}
                        xAxisTickFormatter={formatDateLabel}
                        enableDynamicTicks={true}
                        showZeroLine={true}
                        showFiftyLine={false}
                        connectNulls={true}
                        hideLegend={true}
                        showDefaultTooltip={false}
                        domain={['dataMin - 0.5', 'dataMax + 0.5']}
                      >
                        <RechartsTooltip
                          content={({ active, payload, label }) => {
                            if (!active || !payload || payload.length === 0) return null
                            const dataItem = payload[0]?.payload as ChartDataItem
                            const displayValue = dataItem.value
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
                                <div
                                  style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    fontSize: 13,
                                  }}
                                >
                                  <span style={{ color: '#f1f5f9', marginRight: 16 }}>
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
                                    前年比
                                  </span>
                                  <span style={{ fontWeight: 500, color: CHART_COLORS.primary }}>
                                    {formatPercentage(displayValue)}
                                  </span>
                                </div>
                              </div>
                            )
                          }}
                        />
                      </ZoomableChart>
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              // GDP monthlyと同時発表のため、同じindicatorIdを使用
              children: <MarketImpactTab indicatorId="ca_gdp_monthly" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
