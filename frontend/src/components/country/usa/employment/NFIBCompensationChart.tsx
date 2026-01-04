/**
 * NFIB中小企業人件費・雇用計画チャートコンポーネント
 *
 * NFIB PDF レポートからのデータを使用:
 * - Compensation Plans: 人件費計画（%）
 * - Hiring Plans: 雇用計画（%）
 *
 * 表示モード:
 * - 原数値グラフのみ
 *
 * 毎月第2火曜日 6:00 ET発表
 *
 * 共通コンポーネントを使用
 */
import { useState } from 'react'
import { Tabs } from 'antd'
import MarketImpactTab from '../../../indicator/MarketImpactTab'
import {
  LineChart,
  Line,
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
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'
import type { NFIBCompensationData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabel,
  useHiddenSeries,
} from '../common/useChartData'
import {
  NoDataMessage,
  ValueTooltip,
  LatestValueBox,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface NFIBCompensationChartProps {
  data: NFIBCompensationData | null
}

// カラー設定
const COLORS = {
  compensation_plans: '#ff4d4f',     // 人件費計画 - 赤
  hiring_plans: '#1890ff',           // 雇用計画 - 青
}

// 系列名（日本語）
const SERIES_NAMES = {
  compensation_plans: '人件費計画',
  hiring_plans: '雇用計画',
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function NFIBCompensationChart({ data }: NFIBCompensationChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データを日付順にソート
  const sortedData = useSortedData(data?.data || [])

  // 期間でフィルタリング
  const filteredData = usePeriodFiltering(sortedData, { selectedPeriod: currentPeriod })

  // 最新値と次回発表日
  const latest = data?.latest || null
  const nextRelease = data?.next_release || null

  // ローディング
  if (!data) {
    return <LoadingChart title="NFIB中小企業人件費・雇用計画" message="データを読み込み中..." />
  }

  // データなし
  if (!filteredData || filteredData.length === 0) {
    return (
      <ChartContainer
        title="NFIB中小企業人件費・雇用計画"
        showPeriodSelector={false}
        dataSource="NFIB"
      >
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="nfib-compensation">
      <ChartContainer
        title="NFIB中小企業人件費 / 雇用計画"
        showPeriodSelector={false}
        dataSource="NFIB"
        sourceUrl="https://www.nfib.com/news/monthly_report/sbet/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            ...(latest?.compensation_plans != null ? [{
              label: SERIES_NAMES.compensation_plans,
              value: `${latest.compensation_plans >= 0 ? '+' : ''}${latest.compensation_plans.toFixed(1)}%`,
              color: COLORS.compensation_plans
            }] : []),
            ...(latest?.hiring_plans != null ? [{
              label: SERIES_NAMES.hiring_plans,
              value: `${latest.hiring_plans >= 0 ? '+' : ''}${latest.hiring_plans.toFixed(1)}%`,
              color: COLORS.hiring_plans
            }] : [])
          ]}
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
                  {/* 期間セレクター */}
                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                  {/* 原数値グラフ */}
                  <ResponsiveContainer width="100%" height={450}>
                    <LineChart data={filteredData} margin={CHART_MARGIN}>
                      <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                      <XAxis
                        dataKey="date"
                        tickFormatter={formatDateLabel}
                        tick={AXIS_STYLE.tick}
                        interval={AXIS_STYLE.interval}
                      />
                      <YAxis
                        tick={AXIS_STYLE.tick}
                        tickFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(0)}`}
                        domain={['dataMin - 1', 'dataMax + 1']}
                        label={{
                          angle: -90,
                          position: 'insideLeft',
                          dy: 30,
                          style: { fontSize: 11, fill: '#666' }
                        }}
                      />
                      <Tooltip content={<ValueTooltip unit="%" decimals={1} />} />
                      <Legend onClick={(e) => handleLegendClick(e.dataKey as string)} />
                      <ReferenceLine y={0} stroke="#000" strokeWidth={1} />

                      <Line
                        type="monotone"
                        dataKey="compensation_plans"
                        stroke={COLORS.compensation_plans}
                        strokeWidth={2}
                        dot={false}
                        name={SERIES_NAMES.compensation_plans}
                        hide={hiddenSeries.has('compensation_plans')}
                      />
                      <Line
                        type="monotone"
                        dataKey="hiring_plans"
                        stroke={COLORS.hiring_plans}
                        strokeWidth={2}
                        dot={false}
                        name={SERIES_NAMES.hiring_plans}
                        hide={hiddenSeries.has('hiring_plans')}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="nfib" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
