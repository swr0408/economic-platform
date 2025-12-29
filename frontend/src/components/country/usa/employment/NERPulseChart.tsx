/**
 * NER Pulse（週次雇用変動）チャートコンポーネント
 *
 * ADP Media Centerから取得した週次雇用変動データを表示
 *
 * 表示モード:
 * - 週次増減グラフ（棒グラフ）
 *
 * 共通コンポーネントを使用
 */
import { useMemo } from 'react'
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
import type { NERPulseData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
} from '../common/chartConstants'
import {
  formatWeekEnding,
  formatWeekEndingJP,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  ChangeTooltip,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface NERPulseChartProps {
  data: NERPulseData | null
}

// カラー設定
const CHART_COLOR = CHART_COLORS.primary

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function NERPulseChart({ data }: NERPulseChartProps) {
  // データを日付順にソート（古い順）
  const sortedData = useMemo(() => {
    if (!data?.data) return []
    return [...data.data].sort((a, b) =>
      new Date(a.week_ending).getTime() - new Date(b.week_ending).getTime()
    )
  }, [data?.data])

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="NER Pulse（週次雇用変動）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="NER Pulse（週次雇用変動）" showPeriodSelector={false} showDataSource={false}>
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
        label: 'NER Pulse（週次増減）',
        value: `${latest.change >= 0 ? '+' : ''}${latest.change.toLocaleString()}`,
        color: latest.change >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative,
      },
    ]
  }

  return (
    <div id="ner-pulse">
      <ChartContainer
        title="ADP雇用者数（NER Pulse）"
        showPeriodSelector={false}
        dataSource="ADP Media Center"
        sourceUrl="https://mediacenter.adp.com/labor-market-data"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latest?.week_ending}
          nextRelease={nextRelease}
        />

        {/* 週次増減グラフ */}
        <ResponsiveContainer width="100%" height={450}>
          <ComposedChart data={sortedData} margin={CHART_MARGIN}>
            <CartesianGrid {...CARTESIAN_GRID_PROPS} />
            <XAxis
              dataKey="week_ending"
              tickFormatter={formatWeekEnding}
              tick={AXIS_STYLE.tick}
              interval={0}
            />
            <YAxis
              tick={AXIS_STYLE.tick}
              tickFormatter={(v) => `${v >= 0 ? '+' : ''}${(v / 1000).toFixed(0)}k`}
              label={{
                angle: -90,
                position: 'insideLeft',
                dy: 20,
                style: { fontSize: 11, fill: '#666' }
              }}
            />
            <Tooltip content={<ChangeTooltip unit="" formatValue={(v) => v.toLocaleString()} labelFormatter={formatWeekEndingJP} />} />
            <Legend />
            <ReferenceLine y={0} stroke="#000" strokeWidth={1} />

            <Bar
              dataKey="change"
              fill={CHART_COLOR}
              name="NER Pulse"
            />
          </ComposedChart>
        </ResponsiveContainer>

      </ChartContainer>
    </div>
  )
}
