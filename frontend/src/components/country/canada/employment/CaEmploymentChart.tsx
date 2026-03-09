/**
 * カナダ雇用者数チャートコンポーネント
 *
 * 総雇用者数（原数値・前月比変化・前月増減幅テーブル）を表示
 *
 * データソース:
 * - Statistics Canada Table 14-10-0287-01
 * - Labour force characteristics by sex and detailed age group, monthly, seasonally adjusted
 *
 * 発表スケジュール:
 * - 毎月発表
 * - 発表時刻: 08:30 ET
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip as AntTooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import {
  ComposedChart,
  Line,
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
import type { CaEmploymentData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  VALUE_CHANGE_DATA_KIND_OPTIONS,
  type ValueChangeDataKind,
  DISPLAY_MODE_OPTIONS,
  type DisplayMode,
  CHANGE_LEGEND_100K,
  getChangeCellColor100k,
} from '../../usa/common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMonthlyTableData,
  formatDateLabel,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  ViewModeButtonGroup,
  ChangeTooltip,
  ValueTooltip,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// =============================================================================
// 型定義
// =============================================================================

interface CaEmploymentChartProps {
  data: CaEmploymentData | null
}

// カラー設定
const COLORS = {
  employment: '#DC143C',  // カナダカラー（クリムゾン）
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CaEmploymentChart({ data }: CaEmploymentChartProps) {
  const [dataKind, setDataKind] = useState<ValueChangeDataKind>('change')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { handleLegendClick, isHidden } = useHiddenSeries<'employment'>()

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    value: 10,
    change: 3,
  })

  // データを日付昇順にソート
  const sortedData = useSortedData(data?.data)

  // チャート用データに変換
  const chartData = useMemo(() => {
    return sortedData.map(item => ({
      date: item.date,
      employment: item.employment ?? null,
      employment_change: item.employment_change ?? null,
    }))
  }, [sortedData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ（共通フックを使用）
  const changeTableData = useMonthlyTableData(
    chartData,
    (item) => item.employment_change,
    10
  )

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValues = useMemo(() => {
    if (!data?.latest) return null
    return data.latest
  }, [data])

  // 最新の前月増減幅
  const latestChange = chartData.length >= 1 ? chartData[chartData.length - 1] : null

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="カナダ雇用者数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="カナダ雇用者数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (dataKind === 'value') {
      return latestValues ? [
        { label: '雇用者数', value: latestValues.employment, color: COLORS.employment, format: 'number' as const, unit: '千人', decimals: 1 },
      ] : []
    } else {
      // 前月増減幅モード
      if (!latestChange) return []
      const change = latestChange.employment_change
      return [
        {
          label: '雇用者数（増減）',
          value: change !== null ? `${change >= 0 ? '+' : ''}${change.toLocaleString()}千人` : 'N/A',
          color: change !== null && change >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative,
        },
      ]
    }
  }

  // 比較ボタンのURLを生成
  const getCompareUrl = () => {
    if (dataKind === 'value') {
      return '/compare?s=ca_employment'
    } else {
      return '/compare?s=ca_employment_change'
    }
  }

  return (
    <div id="ca-employment-chart">
      <ChartContainer
        title="雇用者数"
        showPeriodSelector={false}
        dataSource="Statistics Canada"
        sourceUrl="https://www.statcan.gc.ca/en/subjects-start/labour_"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latestChange?.date || latestValues?.date}
          nextRelease={data.next_release ? {
            date: data.next_release.date,
            time_jst: data.next_release.time_jst,
          } : undefined}
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
                  {/* 上段: データ種別 */}
                  <div style={{ marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      options={VALUE_CHANGE_DATA_KIND_OPTIONS}
                      currentMode={dataKind}
                      onChange={setDataKind}
                    />
                  </div>

                  {/* 下段: 表示形式（changeのときのみ） */}
                  {dataKind === 'change' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 現数値グラフ */}
                  {dataKind === 'value' && (
                    <>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                        <AntTooltip title="比較ページを開く">
                          <Button
                            icon={<AreaChartOutlined />}
                            onClick={() => window.open(getCompareUrl(), '_blank')}
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
                            tickFormatter={formatDateLabel}
                            tick={AXIS_STYLE.tick}
                            interval={AXIS_STYLE.interval}
                          />
                          <YAxis
                            domain={['dataMin - 500', 'dataMax + 500']}
                            tick={AXIS_STYLE.tick}
                            tickFormatter={(v) => `${(v / 1000).toFixed(1)}M`}
                            label={{
                              value: '雇用者数（千人）',
                              angle: -90,
                              position: 'insideLeft',
                              style: { fontSize: 11, fill: COLORS.employment }
                            }}
                          />
                          <Tooltip content={<ValueTooltip unit="千人" />} />
                          <Legend
                            onClick={(e) => handleLegendClick(e.dataKey as string)}
                            wrapperStyle={{ cursor: 'pointer' }}
                          />

                          <Line
                            type="monotone"
                            dataKey="employment"
                            stroke={COLORS.employment}
                            strokeWidth={2}
                            dot={false}
                            name="雇用者数"
                            hide={isHidden('employment')}
                            isAnimationActive={false}
                            connectNulls={true}
                          />
                        </ComposedChart>
                      </ResponsiveContainer>
                    </>
                  )}

                  {/* 前月増減幅グラフ */}
                  {dataKind === 'change' && displayMode === 'chart' && (
                    <>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                        <AntTooltip title="比較ページを開く">
                          <Button
                            icon={<AreaChartOutlined />}
                            onClick={() => window.open(getCompareUrl(), '_blank')}
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
                            tickFormatter={formatDateLabel}
                            tick={AXIS_STYLE.tick}
                            interval={AXIS_STYLE.interval}
                          />
                          <YAxis
                            tick={AXIS_STYLE.tick}
                            tickFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(0)}`}
                            domain={['dataMin - 50', 'dataMax + 50']}
                            label={{
                              value: '増減（千人）',
                              angle: -90,
                              position: 'insideLeft',
                              dy: 20,
                              style: { fontSize: 11, fill: '#666' }
                            }}
                          />
                          <Tooltip content={<ChangeTooltip unit="千人" formatValue={(v) => v.toFixed(1)} />} />
                          <Legend />
                          <ReferenceLine y={0} stroke="#000" strokeWidth={1} />

                          <Bar
                            dataKey="employment_change"
                            fill={COLORS.employment}
                            name="雇用者数（増減）"
                          />
                        </ComposedChart>
                      </ResponsiveContainer>
                    </>
                  )}

                  {/* 前月増減幅テーブル */}
                  {dataKind === 'change' && displayMode === 'heatmap' && (
                    <MonthlyTable
                      data={changeTableData}
                      helperText="※ 直近10年間の前月増減幅データ（単位: 千人）"
                      formatValue={(value) => {
                        if (value === null) return '-'
                        return `${value >= 0 ? '+' : ''}${value.toFixed(1)}`
                      }}
                      getCellBgColor={getChangeCellColor100k}
                      legendItems={CHANGE_LEGEND_100K}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="ca_employment" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
