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

// 指標種別
type DataKind = 'value' | 'mom'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'value', label: '現数値' },
  { mode: 'mom', label: '前月比' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// カラー設定
const DEFAULT_COLOR = CHART_COLORS.primary

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function ADPEmploymentChart({ data }: ADPEmploymentChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('value')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // 指標種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    value: 10,
    mom: 3,
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

    switch (dataKind) {
      case 'value':
        return [
          { label: 'ADP雇用者数', value: latest.value, color: DEFAULT_COLOR, format: 'number' as const, unit: 'k', decimals: 0 },
        ]
      case 'mom':
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
                  {/* 上段: 指標種別 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />
                    <AntTooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=adp_employment', '_blank')}
                      >
                        データ比較
                      </Button>
                    </AntTooltip>
                  </div>

                  {/* 下段: 表示形式（前月比のときのみ） */}
                  {dataKind === 'mom' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 現数値グラフ */}
                  {dataKind === 'value' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
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

                  {/* 前月比チャート */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
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

                  {/* 前月比ヒートマップ */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
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
