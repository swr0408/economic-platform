/**
 * 平均残業時間チャートコンポーネント
 *
 * FRED AWOTMAN（製造業の平均週間残業時間）を表示
 *
 * 表示モード:
 * - 原数値グラフのみ
 *
 * 毎月第1金曜日 8:30 ET発表（BLS Employment Situation）
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
  ResponsiveContainer,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'
import type { OvertimeHoursData } from '../../../../hooks/useDashboardData'

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
} from '../common/useChartData'
import {
  NoDataMessage,
  ValueTooltip,
  LatestValueBox,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface OvertimeHoursChartProps {
  data: OvertimeHoursData | null
}

// カラー設定
const LINE_COLOR = '#1890ff'  // 青

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function OvertimeHoursChart({ data }: OvertimeHoursChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // データを日付順にソート
  const sortedData = useSortedData(data?.data || [])

  // 期間でフィルタリング
  const filteredData = usePeriodFiltering(sortedData, { selectedPeriod: currentPeriod })

  // 最新値と次回発表日
  const latest = data?.latest || null
  const nextRelease = data?.next_release || null

  // ローディング
  if (!data) {
    return <LoadingChart title="平均残業時間" message="データを読み込み中..." />
  }

  // データなし
  if (!filteredData || filteredData.length === 0) {
    return (
      <ChartContainer
        title="平均残業時間"
        showPeriodSelector={false}
        dataSource="FRED"
      >
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="overtime-hours">
      <ChartContainer
        title="平均残業時間（製造業）"
        showPeriodSelector={false}
        dataSource="FRED - BLS"
        sourceUrl="https://www.bls.gov/ces/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={latest?.value != null ? [
            { label: '平均残業時間', value: `${latest.value.toFixed(1)}時間/週`, color: LINE_COLOR }
          ] : []}
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
                        tickFormatter={(v: number) => `${v.toFixed(1)}`}
                        domain={['dataMin - 0.1', 'dataMax + 0.1']}
                        label={{
                          angle: -90,
                          position: 'insideLeft',
                          dy: 50,
                          style: { fontSize: 11, fill: '#666' }
                        }}
                      />
                      <Tooltip content={<ValueTooltip unit="時間" decimals={1} />} />

                      <Line
                        type="monotone"
                        dataKey="value"
                        stroke={LINE_COLOR}
                        strokeWidth={2}
                        dot={false}
                        name="平均残業時間"
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
                <MarketImpactTab indicatorId="nonfarm_payrolls" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
