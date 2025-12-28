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
  TOOLTIP_STYLE,
  LATEST_VALUE_BOX_STYLE,
  TEXT_COLORS,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabel,
  formatDateLabelJP,
} from '../common/useChartData'
import {
  NoDataMessage,
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
// カスタムツールチップ
// =============================================================================

interface TooltipPayloadItem {
  name: string
  value: number
  color: string
  dataKey: string
}

interface TooltipProps {
  active?: boolean
  payload?: TooltipPayloadItem[]
  label?: string
}

function CustomTooltip({ active, payload, label }: TooltipProps) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8 }}>
        {formatDateLabelJP(label || '')}
      </div>
      {payload.map((entry, index) => (
        <div
          key={index}
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            gap: 16,
            fontSize: 12,
            marginBottom: 4,
          }}
        >
          <span style={{ color: '#f1f5f9' }}>{entry.name}</span>
          <span style={{ fontWeight: 'bold', color: entry.color }}>
            {entry.value != null ? `${entry.value.toFixed(1)}時間` : '-'}
          </span>
        </div>
      ))}
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function OvertimeHoursChart({ data }: OvertimeHoursChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')

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
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary, fontWeight: 'bold' }}>最新値</span>
            {latest?.value != null && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 16, fontWeight: 'bold', color: LINE_COLOR }}>
                  {latest.value.toFixed(1)}時間/週
                </span>
              </div>
            )}
            {latest?.date && (
              <span style={{ fontSize: 11, color: TEXT_COLORS.tertiary }}>
                ({formatDateLabel(latest.date)})
              </span>
            )}
          </div>
          <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, textAlign: 'right' }}>
            {nextRelease && (
              <div>次回発表: {nextRelease.date}</div>
            )}
            <div>毎月第1金曜日発表</div>
          </div>
        </div>

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
            <Tooltip content={<CustomTooltip />} />

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
      </ChartContainer>
    </div>
  )
}
