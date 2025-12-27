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
  TOOLTIP_STYLE,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabel,
  formatDateLabelJP,
  useHiddenSeries,
} from '../common/useChartData'
import {
  NoDataMessage,
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
          <span style={{ color: entry.color }}>{entry.name}</span>
          <span style={{ fontWeight: 'bold' }}>
            {entry.value != null ? `${entry.value.toFixed(1)}%` : '-'}
          </span>
        </div>
      ))}
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function NFIBCompensationChart({ data }: NFIBCompensationChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')
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
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 12,
            padding: '12px 16px',
            background: '#f5f5f5',
            borderRadius: 8,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, color: '#666', fontWeight: 'bold' }}>最新値</span>
            {latest?.compensation_plans != null && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 12, color: '#666' }}>{SERIES_NAMES.compensation_plans}:</span>
                <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.compensation_plans }}>
                  {latest.compensation_plans >= 0 ? '+' : ''}{latest.compensation_plans.toFixed(1)}%
                </span>
              </div>
            )}
            {latest?.hiring_plans != null && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 12, color: '#666' }}>{SERIES_NAMES.hiring_plans}:</span>
                <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.hiring_plans }}>
                  {latest.hiring_plans >= 0 ? '+' : ''}{latest.hiring_plans.toFixed(1)}%
                </span>
              </div>
            )}
            {latest?.date && (
              <span style={{ fontSize: 11, color: '#999' }}>
                ({formatDateLabel(latest.date)})
              </span>
            )}
          </div>
          <div style={{ fontSize: 11, color: '#888', textAlign: 'right' }}>
            {nextRelease && (
              <div>次回発表: {nextRelease.date}</div>
            )}
            <div>毎月第2火曜日発表</div>
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
              tickFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(0)}`}
              domain={['dataMin - 1', 'dataMax + 1']}
              label={{
                angle: -90,
                position: 'insideLeft',
                dy: 30,
                style: { fontSize: 11, fill: '#666' }
              }}
            />
            <Tooltip content={<CustomTooltip />} />
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
      </ChartContainer>
    </div>
  )
}
