/**
 * NFIB労働報酬・失業率チャートコンポーネント
 *
 * NFIB PDF レポートからのデータを使用:
 * - Actual Compensation Changes: 実際の人件費変更（%）
 * - FRED UNRATE: 失業率（%）
 *
 * 表示モード:
 * - 原数値グラフのみ（2軸）
 *
 * 毎月第2火曜日 6:00 ET発表（NFIB）
 * 毎月第1金曜日 8:30 ET発表（雇用統計）
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
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'
import type { NFIBCompensationUnemploymentData } from '../../../../hooks/useDashboardData'

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

interface NFIBCompensationUnemploymentChartProps {
  data: NFIBCompensationUnemploymentData | null
}

// カラー設定
const COLORS = {
  actual_compensation: '#dc2626',     // 実際の人件費変更 - 赤
  unemployment_rate: '#1890ff',       // 失業率 - 青
}

// 系列名（日本語）
const SERIES_NAMES = {
  actual_compensation: 'NFIB労働報酬',
  unemployment_rate: '失業率',
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

export default function NFIBCompensationUnemploymentChart({ data }: NFIBCompensationUnemploymentChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(5)
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
    return <LoadingChart title="NFIB労働報酬・失業率" message="データを読み込み中..." />
  }

  // データなし
  if (!filteredData || filteredData.length === 0) {
    return (
      <ChartContainer
        title="NFIB労働報酬・失業率"
        showPeriodSelector={false}
        dataSource="NFIB / BLS"
      >
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="nfib-compensation-unemployment">
      <ChartContainer
        title="NFIB労働報酬 / 失業率"
        showPeriodSelector={false}
        dataSource="NFIB / BLS"
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
            {latest?.actual_compensation != null && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 12, color: '#666' }}>{SERIES_NAMES.actual_compensation}:</span>
                <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.actual_compensation }}>
                  {latest.actual_compensation >= 0 ? '+' : ''}{latest.actual_compensation.toFixed(1)}%
                </span>
              </div>
            )}
            {latest?.unemployment_rate != null && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 12, color: '#666' }}>{SERIES_NAMES.unemployment_rate}:</span>
                <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.unemployment_rate }}>
                  {latest.unemployment_rate.toFixed(1)}%
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

        {/* 2軸グラフ */}
        <ResponsiveContainer width="100%" height={450}>
          <LineChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid {...CARTESIAN_GRID_PROPS} />
            <XAxis
              dataKey="date"
              tickFormatter={formatDateLabel}
              tick={AXIS_STYLE.tick}
              interval={AXIS_STYLE.interval}
            />
            {/* 左Y軸: NFIB労働報酬 */}
            <YAxis
              yAxisId="left"
              tick={AXIS_STYLE.tick}
              tickFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(0)}`}
              domain={['dataMin - 1', 'dataMax + 1']}
              label={{
                value: 'NFIB労働報酬（%）',
                angle: -90,
                position: 'insideLeft',
                dy: 40,
                style: { fontSize: 11, fill: COLORS.actual_compensation }
              }}
            />
            {/* 右Y軸: 失業率（逆順） */}
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={AXIS_STYLE.tick}
              tickFormatter={(v: number) => `${v.toFixed(1)}`}
              domain={['dataMin - 0.1', 'dataMax + 0.1']}
              reversed
              label={{
                value: '失業率（%）',
                angle: 90,
                position: 'insideRight',
                dy: 30,
                style: { fontSize: 11, fill: COLORS.unemployment_rate }
              }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend onClick={(e) => handleLegendClick(e.dataKey as string)} />

            <Line
              type="monotone"
              dataKey="actual_compensation"
              stroke={COLORS.actual_compensation}
              strokeWidth={2}
              dot={false}
              name={SERIES_NAMES.actual_compensation}
              yAxisId="left"
              hide={hiddenSeries.has('actual_compensation')}
            />
            <Line
              type="monotone"
              dataKey="unemployment_rate"
              stroke={COLORS.unemployment_rate}
              strokeWidth={2}
              dot={false}
              name={SERIES_NAMES.unemployment_rate}
              yAxisId="right"
              hide={hiddenSeries.has('unemployment_rate')}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
