/**
 * 小売売上高チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { RetailSalesData, RetailControlData } from '../../../../hooks/useDashboardData'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  RETAIL_DATA_TYPE_OPTIONS,
  RETAIL_DATA_TYPE_BUTTON_OPTIONS,
  type RetailDataType,
} from '../common/chartConstants'
import {
  usePeriodFiltering,
  useViewModePeriodManagement,
  useHiddenSeries,
  useMultiValueMonthlyTableData,
} from '../common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
  StandardBarChart,
} from '../common/ChartComponents'
import { MonthlyTableWithDataTypes } from '../common/MonthlyTable'

// =============================================================================
// 型定義
// =============================================================================

interface RetailSalesChartProps {
  data: RetailSalesData | null
  controlData: RetailControlData | null
}

// 指標種別
type DataKind = 'mom' | 'yoy'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'mom', label: '前月比' },
  { mode: 'yoy', label: '前年比' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// カラー設定
const COLORS = {
  yoy: CHART_COLORS.positive,
  yoy_ex: CHART_COLORS.purple,
  yoy_cg: CHART_COLORS.cyan,
  mom: CHART_COLORS.positive,
  mom_ex: CHART_COLORS.purple,
  mom_cg: CHART_COLORS.cyan,
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function RetailSalesChart({ data, controlData }: RetailSalesChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('mom')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [dataType, setDataType] = useState<RetailDataType>('total')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // 指標種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    mom: 3,
    yoy: 10,
  })

  // コントロールグループデータを日付でマッピング
  const controlGroupMap = useMemo(() => {
    if (!controlData?.data) return new Map<string, number>()
    const map = new Map<string, number>()
    controlData.data.forEach((item) => {
      map.set(item.date, item.mom)
    })
    return map
  }, [controlData])

  // データを日付昇順にソートし、コントロールグループの前月比をマージ
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        ...item,
        control_group_mom: controlGroupMap.get(item.date) ?? null,
      }))
  }, [data, controlGroupMap])

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
      ex_auto: (item) => item.ex_auto_mom,
      control_group: (item) => item.control_group_mom,
    },
    10
  )

  const hasData = chartData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="小売売上高（Retail Sales）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="小売売上高（Retail Sales）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="retail-sales">
      <ChartContainer
        title="小売売上高"
        showPeriodSelector={false}
        dataSource="FRED (Census Bureau)"
        sourceUrl="https://www.census.gov/retail/index.html"
        handbookId="retail-sales"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '総合',
              value: dataKind === 'yoy' ? latest?.yoy : latest?.mom,
              color: COLORS.yoy,
              format: 'percent',
            },
            {
              label: '自動車除く',
              value: dataKind === 'yoy' ? latest?.ex_auto_yoy : latest?.ex_auto_mom,
              color: COLORS.yoy_ex,
              format: 'percent',
            },
            ...(dataKind !== 'yoy' && controlData?.latest
              ? [{
                label: 'コントロールグループ',
                value: controlData.latest.mom,
                color: COLORS.yoy_cg,
                format: 'percent' as const,
              }]
              : []),
          ]}
          date={latest?.date}
          nextRelease={data.next_release}
        />

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
                        onClick={() => window.open('/compare?s=retail_sales_value', '_blank')}
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
                          { dataKey: 'yoy', color: COLORS.yoy, name: '小売売上高（前年比）', hide: hiddenSeries.has('yoy') },
                          { dataKey: 'ex_auto_yoy', color: COLORS.yoy_ex, name: '自動車除く（前年比）', hide: hiddenSeries.has('ex_auto_yoy') },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 3', 'dataMax + 3']}
                        onLegendClick={handleLegendClick}
                      />
                    </>
                  )}

                  {/* 前月比ヒートマップ */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTableWithDataTypes
                      data={momTableData}
                      dataTypes={RETAIL_DATA_TYPE_OPTIONS}
                      selectedType={dataType}
                      onTypeChange={setDataType}
                    />
                  )}

                  {/* 前月比チャート */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <div style={{ marginBottom: 8 }}>
                        <ViewModeButtonGroup options={RETAIL_DATA_TYPE_BUTTON_OPTIONS} currentMode={dataType} onChange={setDataType} />
                      </div>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          dataType === 'total'
                            ? { dataKey: 'mom', color: COLORS.mom, name: '小売売上高（前月比）' }
                            : dataType === 'ex_auto'
                              ? { dataKey: 'ex_auto_mom', color: COLORS.mom_ex, name: '自動車除く（前月比）' }
                              : { dataKey: 'control_group_mom', color: COLORS.mom_cg, name: 'コントロールグループ（前月比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
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
                <MarketImpactTab indicatorId="retail_sales_mom" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
