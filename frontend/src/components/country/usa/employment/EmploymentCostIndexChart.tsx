/**
 * 雇用コスト指数（Employment Cost Index）チャートコンポーネント
 *
 * FRED ECIALLCIV（Total Compensation）の前期比データを表示
 * - 前期比テーブル
 * - 前期比グラフ
 * - 四半期ごと発表（1月、4月、7月、10月）8:30 ET
 *
 * 共通コンポーネントを使用
 */
import { useState, useCallback } from 'react'
import { Tabs, Button, Tooltip as AntTooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import MarketImpactTab from '../../../indicator/MarketImpactTab'
import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { EmploymentCostIndexData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  CHANGE_LEGEND_05PCT,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  formatQuarterLabel,
  formatQuarterLabelJP,
  useQuarterlyTableData,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  ViewModeButtonGroup,
  ChangeTooltip,
} from '../common/ChartComponents'
import { QuarterlyTable } from '../common/QuarterlyTable'

// =============================================================================
// 型定義
// =============================================================================

interface EmploymentCostIndexChartProps {
  data: EmploymentCostIndexData | null
}

type ViewMode = 'qoq_table' | 'qoq_chart'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'qoq_table', label: '前期比テーブル' },
  { mode: 'qoq_chart', label: '前期比グラフ' },
]

// カラー設定
const COLORS = {
  qoq: '#1890ff', // 前期比 - 青
}

// 系列名（日本語）
const SERIES_NAMES = {
  qoq: '前期比',
}


// =============================================================================
// メインコンポーネント
// =============================================================================

export default function EmploymentCostIndexChart({ data }: EmploymentCostIndexChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('qoq_table')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    qoq_chart: 'default',
    qoq_table: 'default',
  })

  // データのソート
  const sortedData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // 四半期テーブルデータの生成
  const tableData = useQuarterlyTableData(
    sortedData,
    useCallback((item: { pch?: number | null }) => item.pch ?? null, []),
    10
  )

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="雇用コスト指数（前期比）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="雇用コスト指数（前期比）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latest) return []

    return [
      {
        label: SERIES_NAMES.qoq,
        value: latest.pch !== null ? `${latest.pch >= 0 ? '+' : ''}${latest.pch.toFixed(2)}%` : 'N/A',
        color: latest.pch !== null && latest.pch >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative,
      },
    ]
  }

  return (
    <div id="employment-cost-index">
      <ChartContainer
        title="雇用コスト指数（前期比）"
        showPeriodSelector={false}
        dataSource="FRED - ECIALLCIV"
        sourceUrl="https://www.bls.gov/eci/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latest?.date}
          nextRelease={nextRelease}
          dateFormatter={formatQuarterLabel}
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
                  {/* ビューモード切り替え */}
                  <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />

                  {/* 前期比グラフ */}
                  {viewMode === 'qoq_chart' && (
                    <>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                        <AntTooltip title="比較ページを開く">
                          <Button
                            icon={<AreaChartOutlined />}
                            onClick={() => window.open('/compare?s=employment_cost_index', '_blank')}
                          >
                            データ比較
                          </Button>
                        </AntTooltip>
                      </div>
                      <ResponsiveContainer width="100%" height={450}>
                        <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                          <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                          <XAxis
                            dataKey="date"
                            tickFormatter={formatQuarterLabel}
                            tick={AXIS_STYLE.tick}
                            interval={AXIS_STYLE.interval}
                          />
                          <YAxis
                            tick={AXIS_STYLE.tick}
                            tickFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}`}
                            domain={['dataMin - 0.2', 'dataMax + 0.2']}
                            label={{
                              angle: -90,
                              position: 'insideLeft',
                              dy: 20,
                              style: { fontSize: 11, fill: '#666' }
                            }}
                          />
                          <Tooltip content={<ChangeTooltip unit="%" decimals={2} labelFormatter={formatQuarterLabelJP} />} />
                          <Legend />
                          <ReferenceLine y={0} stroke="#000" strokeWidth={1} />

                          <Bar
                            dataKey="pch"
                            fill={COLORS.qoq}
                            name={SERIES_NAMES.qoq}
                          />
                        </ComposedChart>
                      </ResponsiveContainer>
                    </>
                  )}

                  {/* 前期比テーブル */}
                  {viewMode === 'qoq_table' && <QuarterlyTable data={tableData} legendItems={CHANGE_LEGEND_05PCT} />}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="employment_cost_index" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
