/**
 * ADP雇用者数チャートコンポーネント
 *
 * FRED ADPMNUSNERSA データを使用してADP雇用者数を表示
 *
 * 表示モード:
 * - 現数値（レベル）
 * - 前年比グラフ
 * - 前月比グラフ
 * - 前月比テーブル
 *
 * 共通コンポーネントを使用
 */
import { useState } from 'react'
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
import type { ADPEmploymentData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  CHANGE_LEGEND_200K,
  getChangeCellColor200k,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMonthlyTableData,
  formatDateLabel,
  formatDateLabelJP,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  StandardLineChart,
  ViewModeButtonGroup,
  ChangeTooltip,
} from '../common/ChartComponents'
import { MonthlyTable } from '../common/MonthlyTable'

// =============================================================================
// 型定義
// =============================================================================

interface ADPEmploymentChartProps {
  data: ADPEmploymentData | null
}

type ViewMode = 'value' | 'mom_chart' | 'mom_table'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'value', label: '現数値' },
  { mode: 'mom_chart', label: '前月比' },
  { mode: 'mom_table', label: '前月比（テーブル）' },
]

// カラー設定
const DEFAULT_COLOR = CHART_COLORS.primary

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function ADPEmploymentChart({ data }: ADPEmploymentChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('value')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    value: 'default',
    mom_chart: 3,
    mom_table: 'default',
  })

  // データのソート
  const sortedData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // テーブル用データ（共通フックを使用）
  const changeTableData = useMonthlyTableData(
    sortedData,
    (item) => item.mom,
    10
  )

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="ADP雇用者数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="ADP雇用者数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latest) return []

    switch (viewMode) {
      case 'value':
        return [
          { label: 'ADP雇用者数', value: latest.value, color: DEFAULT_COLOR, format: 'number' as const, unit: 'k', decimals: 0 },
        ]
      case 'mom_chart':
      case 'mom_table':
        return [
          {
            label: 'ADP雇用者数（前月比）',
            value: latest.mom !== null ? `${latest.mom >= 0 ? '+' : ''}${latest.mom.toLocaleString()}k` : 'N/A',
            color: latest.mom !== null && latest.mom >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative,
          },
        ]
      default:
        return []
    }
  }

  return (
    <div id="adp-employment">
      <ChartContainer
        title="ADP雇用者数"
        showPeriodSelector={false}
        dataSource="FRED / ADP"
        sourceUrl="https://adpemploymentreport.com/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latest?.date}
          nextRelease={nextRelease}
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
                  {/* ビューモード切り替え */}
                  <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />

                  {/* 現数値グラフ */}
                  {viewMode === 'value' && (
                    <>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                        <AntTooltip title="比較ページを開く">
                          <Button
                            icon={<AreaChartOutlined />}
                            onClick={() => window.open('/compare?s=adp_employment', '_blank')}
                          >
                            データ比較
                          </Button>
                        </AntTooltip>
                      </div>
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          {
                            dataKey: 'value',
                            color: DEFAULT_COLOR,
                            name: 'ADP雇用者数',
                          },
                        ]}
                        yAxisFormatter={(v) => `${v.toLocaleString()}`}
                        yDomain={['dataMin - 1000', 'dataMax + 1000']}
                        tooltipLabelFormatter={formatDateLabelJP}
                        tooltipFormatter={(value: unknown, name: string) => [
                          `${(value as number).toLocaleString()}k`,
                          name,
                        ]}
                        showZeroLine={false}
                      />
                    </>
                  )}

                  {/* 前月比グラフ */}
                  {viewMode === 'mom_chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <ResponsiveContainer width="100%" height={450}>
                        <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                          <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                          <XAxis
                            dataKey="date"
                            tickFormatter={formatDateLabel}
                            tick={AXIS_STYLE.tick}
                            interval={AXIS_STYLE.interval}
                          />
                          <YAxis
                            tick={AXIS_STYLE.tick}
                            tickFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toLocaleString()}`}
                            domain={['dataMin - 100', 'dataMax + 100']}
                            label={{
                              value: '増減（k）',
                              angle: -90,
                              position: 'insideLeft',
                              dy: 20,
                              style: { fontSize: 11, fill: '#666' }
                            }}
                          />
                          <Tooltip content={<ChangeTooltip unit="k" formatValue={(v) => v.toLocaleString()} />} />
                          <Legend />
                          <ReferenceLine y={0} stroke="#000" strokeWidth={1} />

                          <Bar
                            dataKey="mom"
                            fill={DEFAULT_COLOR}
                            name="ADP雇用者数（前月比）"
                          />
                        </ComposedChart>
                      </ResponsiveContainer>
                    </>
                  )}

                  {/* 前月比テーブル */}
                  {viewMode === 'mom_table' && (
                    <MonthlyTable
                      data={changeTableData}
                      formatValue={(value) => {
                        if (value === null) return '-'
                        return `${value >= 0 ? '+' : ''}${value.toLocaleString()}`
                      }}
                      getCellBgColor={getChangeCellColor200k}
                      legendItems={CHANGE_LEGEND_200K}
                      helperText="※ 直近10年間の前月増減幅データ（単位: 千人）"
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="adp_employment" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
