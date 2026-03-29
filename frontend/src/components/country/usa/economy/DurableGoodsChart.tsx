/**
 * 耐久財受注チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { DurableGoodsData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  LATEST_VALUE_BOX_STYLE,
  TEXT_COLORS,
  DURABLE_GOODS_DATA_TYPE_OPTIONS,
  type DurableGoodsDataType,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMultiValueMonthlyTableData,
  useHiddenSeries,
  formatPercent,
  formatDateLabel,
} from '../common/useChartData'
import {
  ViewModeButtonGroup,
  DataTypeButtonGroup,
  NoDataMessage,
  StandardLineChart,
  StandardBarChart,
} from '../common/ChartComponents'
import { MonthlyTableWithDataTypes } from '../common/MonthlyTable'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// =============================================================================
// 型定義
// =============================================================================

interface DurableGoodsChartProps {
  data: DurableGoodsData | null
}

// 指標種別
type DataKind = 'yoy' | 'mom'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// カラー設定
const COLORS = {
  yoy: CHART_COLORS.primary,
  yoy_ex: CHART_COLORS.purple,
  core_orders: CHART_COLORS.orange,
  core_shipments: CHART_COLORS.cyan,
  mom: CHART_COLORS.positive,
  mom_ex: CHART_COLORS.purple,
  mom_core_orders: CHART_COLORS.orange,
  mom_core_shipments: CHART_COLORS.cyan,
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function DurableGoodsChart({ data }: DurableGoodsChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [dataType, setDataType] = useState<DurableGoodsDataType>('total')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // 指標種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 10,
    mom: 3,
  })

  // データを日付昇順にソート
  const chartData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // テーブル用データ（共通フックを使用）
  const momTableData = useMultiValueMonthlyTableData(
    chartData,
    {
      total: (item) => item.mom,
      ex_transport: (item) => item.ex_transport_mom,
      core_orders: (item) => item.core_orders_mom,
      core_shipments: (item) => item.core_shipments_mom,
    },
    10
  )

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="耐久財受注（Durable Goods Orders）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="耐久財受注（Durable Goods Orders）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="durable-goods-chart">
      <ChartContainer
        title="耐久財受注"
        showPeriodSelector={false}
        dataSource="FRED (Census Bureau)"
        sourceUrl="https://www.census.gov/manufacturing/m3/release_schedule.html"
        handbookId="durable-goods"
      >
        {/* 最新値表示 */}
        {(() => {
          const getValue = (yoy: number | null | undefined, mom: number | null | undefined) =>
            dataKind === 'yoy' ? yoy : mom
          const items = [
            { label: '総合', value: getValue(latest?.yoy, latest?.mom), color: COLORS.yoy },
            { label: '輸送除外', value: getValue(latest?.ex_transport_yoy, latest?.ex_transport_mom), color: COLORS.yoy_ex },
            { label: 'コア受注', value: getValue(latest?.core_orders_yoy, latest?.core_orders_mom), color: COLORS.core_orders },
            { label: 'コア出荷', value: getValue(latest?.core_shipments_yoy, latest?.core_shipments_mom), color: COLORS.core_shipments },
          ]
          return (
            <div style={LATEST_VALUE_BOX_STYLE}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 12, color: TEXT_COLORS.secondary, fontWeight: 'bold' }}>最新値</span>
                {items.map((item) => (
                  <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>{item.label}:</span>
                    <span style={{ fontSize: 16, fontWeight: 'bold', color: item.color }}>
                      {formatPercent(item.value)}
                    </span>
                  </div>
                ))}
                {latest?.date && (
                  <span style={{ fontSize: 11, color: TEXT_COLORS.tertiary }}>
                    ({formatDateLabel(latest.date)})
                  </span>
                )}
              </div>
              {data.next_release && (
                <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, textAlign: 'right' }}>
                  次回発表: {data.next_release.date}
                </div>
              )}
            </div>
          )
        })()}

        {/* タブ切替 */}
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
                    <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=durable_goods_value', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 下段: 表示形式（前月比のときのみ） */}
                  {dataKind === 'mom' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 前年比グラフ */}
                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'yoy', color: COLORS.yoy, name: '耐久財受注（前年比）', hide: hiddenSeries.has('yoy') },
                          { dataKey: 'ex_transport_yoy', color: COLORS.yoy_ex, name: '輸送除外（前年比）', hide: hiddenSeries.has('ex_transport_yoy') },
                          { dataKey: 'core_orders_yoy', color: COLORS.core_orders, name: 'コア受注（前年比）', hide: hiddenSeries.has('core_orders_yoy') },
                          { dataKey: 'core_shipments_yoy', color: COLORS.core_shipments, name: 'コア出荷（前年比）', hide: hiddenSeries.has('core_shipments_yoy') },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 5', 'dataMax + 5']}
                        onLegendClick={handleLegendClick}
                      />
                    </>
                  )}

                  {/* 前月比ヒートマップ */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTableWithDataTypes
                      data={momTableData}
                      dataTypes={DURABLE_GOODS_DATA_TYPE_OPTIONS}
                      selectedType={dataType}
                      onTypeChange={setDataType}
                    />
                  )}

                  {/* 前月比チャート */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <DataTypeButtonGroup options={DURABLE_GOODS_DATA_TYPE_OPTIONS} currentType={dataType} onChange={setDataType} />
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          dataType === 'total'
                            ? { dataKey: 'mom', color: COLORS.mom, name: '耐久財受注（前月比）' }
                            : dataType === 'ex_transport'
                            ? { dataKey: 'ex_transport_mom', color: COLORS.mom_ex, name: '輸送除外（前月比）' }
                            : dataType === 'core_orders'
                            ? { dataKey: 'core_orders_mom', color: COLORS.mom_core_orders, name: 'コア受注（前月比）' }
                            : { dataKey: 'core_shipments_mom', color: COLORS.mom_core_shipments, name: 'コア出荷（前月比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 2', 'dataMax + 2']}
                      />
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="durable_goods_mom" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
