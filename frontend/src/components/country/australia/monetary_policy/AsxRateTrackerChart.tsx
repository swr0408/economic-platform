/**
 * ASX RBA Rate Tracker チャートコンポーネント
 *
 * ASX 30日物銀行間キャッシュレート先物から算出された
 * 次回RBA会合での金利変更確率とインプライドイールドカーブを表示
 *
 * データソース:
 * - ASX (Australian Securities Exchange)
 * - https://www.asx.com.au/markets/trade-our-derivatives-market/futures-market/rba-rate-tracker
 *
 * 3セクション:
 * A. サマリ情報（現在金利、次回会合日、変更確率）
 * B. 確率推移チャート（スタック棒グラフ）
 * C. インプライドイールドカーブ（折れ線グラフ）
 */
import { useState, useMemo } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine as RechartsReferenceLine,
} from 'recharts'
import { Tabs } from 'antd'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'

import { NoDataMessage } from '../../usa/common/ChartComponents'
import { DARK_THEME } from '../../usa/common/chartConstants'

import type { AsxRateTrackerData } from '../../../../hooks/useDashboardData'

interface AsxRateTrackerChartProps {
  data: AsxRateTrackerData | null
}

// 確率推移チャート用データ
interface ProbabilityChartData {
  date: string
  prob_no_change: number
  prob_change: number
}

// イールドカーブチャート用データ
interface YieldCurveChartData {
  date: string
  value: number
  month: string
  implied_yield: number
  [key: string]: string | number | null | undefined
}

const TOOLTIP_STYLE: React.CSSProperties = {
  backgroundColor: DARK_THEME.bgTertiary,
  border: `1px solid ${DARK_THEME.borderLight}`,
  borderRadius: 8,
  padding: '12px 16px',
  boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
}

export default function AsxRateTrackerChart({ data }: AsxRateTrackerChartProps) {
  const [activeTab, setActiveTab] = useState<string>('probability')

  // 確率推移データ
  const probabilityData = useMemo<ProbabilityChartData[]>(() => {
    if (!data?.probability_history || data.probability_history.length === 0) return []
    return data.probability_history.map((day) => ({
      date: day.date,
      prob_no_change: day.prob_no_change,
      prob_change: day.prob_change,
    }))
  }, [data])

  // イールドカーブデータ
  const yieldCurveData = useMemo<YieldCurveChartData[]>(() => {
    if (!data?.yield_curve?.data || data.yield_curve.data.length === 0) return []
    return data.yield_curve.data.map((point) => ({
      date: point.month,
      value: point.implied_yield,
      month: point.month,
      implied_yield: point.implied_yield,
    }))
  }, [data])

  const summary = data?.summary
  const yieldCurve = data?.yield_curve

  // ローディング表示
  if (data === null) {
    return <LoadingChart title="ASX RBA Rate Tracker" />
  }

  // データなし
  if (!summary && probabilityData.length === 0 && yieldCurveData.length === 0) {
    return (
      <ChartContainer title="ASX RBA Rate Tracker" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 変更方向のラベル
  const rateChangeLabel = (() => {
    if (!summary?.future_rate_change) return '金利変更'
    return summary.future_rate_change > 0 ? '利上げ' : '利下げ'
  })()

  // 変更幅の表示
  const rateChangeText = summary?.future_rate_change
    ? `${Math.abs(summary.future_rate_change * 100).toFixed(0)}bp ${rateChangeLabel}`
    : ''

  return (
    <div id="asx-rate-tracker-chart">
      <ChartContainer
        title="RBA Rate Tracker"
        showPeriodSelector={false}
        dataSource="Australian Securities Exchange"
        sourceUrl="https://www.asx.com.au/markets/trade-our-derivatives-market/futures-market/rba-rate-tracker"
      >
        {/* セクションA: サマリ */}
        {summary && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
              gap: 12,
              marginBottom: 16,
              padding: 16,
              backgroundColor: DARK_THEME.bgSecondary,
              borderRadius: 8,
              border: `1px solid ${DARK_THEME.borderLight}`,
            }}
          >
            {/* 現在の金利 */}
            <SummaryItem
              label="現在の金利"
              value={summary.current_rate != null ? `${summary.current_rate.toFixed(2)}%` : '-'}
              color="#00BFFF"
            />
            {/* 次回会合日 */}
            <SummaryItem
              label="次回RBA会合"
              value={summary.next_meeting_date ? formatMeetingDate(summary.next_meeting_date) : '-'}
              color={DARK_THEME.textPrimary}
            />
            {/* 変更確率 */}
            <SummaryItem
              label={`${rateChangeText} 確率`}
              value={summary.market_expectation_pct != null ? `${summary.market_expectation_pct}%` : '-'}
              color="#FF6B6B"
            />
            {/* 据え置き確率 */}
            <SummaryItem
              label="据え置き確率"
              value={summary.market_expectation_pct != null ? `${100 - summary.market_expectation_pct}%` : '-'}
              color="#52c41a"
            />
            {/* 先物インプライド金利 */}
            <SummaryItem
              label="先物インプライド金利"
              value={summary.future_cash_rate != null ? `${summary.future_cash_rate.toFixed(2)}%` : '-'}
              color="#faad14"
            />
            {/* 決済価格 */}
            <SummaryItem
              label="決済価格"
              value={summary.settlement_price != null ? `${summary.settlement_price.toFixed(2)}` : '-'}
              subValue={summary.settlement_date ? `(${summary.settlement_date})` : ''}
              color={DARK_THEME.textSecondary}
            />
          </div>
        )}

        {/* セクションB + C: タブ */}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'probability',
              label: '確率推移',
              children: (
                <ProbabilityHistoryChart
                  data={probabilityData}
                  rateChangeLabel={rateChangeLabel}
                />
              ),
            },
            {
              key: 'yield_curve',
              label: 'イールドカーブ',
              children: (
                <ImpliedYieldCurveChart
                  data={yieldCurveData}
                  targetRate={yieldCurve?.target_rate ?? null}
                />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}

// サマリアイテムコンポーネント
function SummaryItem({
  label,
  value,
  subValue,
  color,
}: {
  label: string
  value: string
  subValue?: string
  color: string
}) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 12, color: DARK_THEME.textSecondary, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 600, color }}>{value}</div>
      {subValue && (
        <div style={{ fontSize: 11, color: DARK_THEME.textSecondary, marginTop: 2 }}>{subValue}</div>
      )}
    </div>
  )
}

// 会合日フォーマット
function formatMeetingDate(dateStr: string): string {
  try {
    const d = new Date(dateStr)
    return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`
  } catch {
    return dateStr
  }
}

// X軸日付フォーマット
function formatShortDate(dateStr: string): string {
  try {
    const d = new Date(dateStr)
    return `${d.getMonth() + 1}/${d.getDate()}`
  } catch {
    return dateStr
  }
}

// =============================================================================
// セクションB: 確率推移スタック棒グラフ
// =============================================================================

function ProbabilityHistoryChart({
  data,
  rateChangeLabel,
}: {
  data: ProbabilityChartData[]
  rateChangeLabel: string
}) {
  if (data.length === 0) {
    return <NoDataMessage />
  }

  return (
    <ResponsiveContainer width="100%" height={400}>
      <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.borderLight} />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: DARK_THEME.textSecondary }}
          tickFormatter={formatShortDate}
          axisLine={{ stroke: DARK_THEME.borderLight }}
          tickLine={{ stroke: DARK_THEME.borderLight }}
        />
        <YAxis
          domain={[0, 100]}
          tick={{ fontSize: 11, fill: DARK_THEME.textSecondary }}
          tickFormatter={(v) => `${v}%`}
          axisLine={{ stroke: DARK_THEME.borderLight }}
          tickLine={{ stroke: DARK_THEME.borderLight }}
        />
        <RechartsTooltip
          content={({ active, payload, label }) => {
            if (!active || !payload || payload.length === 0) return null
            return (
              <div style={TOOLTIP_STYLE}>
                <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
                  {label}
                </div>
                {payload.map((item, index) => (
                  <div
                    key={index}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: 4,
                      fontSize: 13,
                    }}
                  >
                    <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
                      <span
                        style={{
                          display: 'inline-block',
                          width: 10,
                          height: 10,
                          borderRadius: 2,
                          backgroundColor: item.color,
                          marginRight: 6,
                        }}
                      />
                      {item.name}
                    </span>
                    <span style={{ fontWeight: 500, color: item.color }}>
                      {`${item.value}%`}
                    </span>
                  </div>
                ))}
              </div>
            )
          }}
        />
        <Legend
          wrapperStyle={{ fontSize: 12, color: DARK_THEME.textSecondary }}
        />
        <Bar
          dataKey="prob_no_change"
          stackId="prob"
          fill="#52c41a"
          name="据え置き"
          radius={[0, 0, 0, 0]}
        />
        <Bar
          dataKey="prob_change"
          stackId="prob"
          fill="#00BFFF"
          name={rateChangeLabel}
          radius={[4, 4, 0, 0]}
        />
      </BarChart>
    </ResponsiveContainer>
  )
}

// =============================================================================
// セクションC: インプライドイールドカーブ
// =============================================================================

function ImpliedYieldCurveChart({
  data,
  targetRate,
}: {
  data: YieldCurveChartData[]
  targetRate: number | null
}) {
  if (data.length === 0) {
    return <NoDataMessage />
  }

  return (
    <div>
      {/* ターゲット金利の表示 */}
      {targetRate != null && (
        <div style={{ marginBottom: 8, fontSize: 13, color: DARK_THEME.textSecondary }}>
          <span
            style={{
              display: 'inline-block',
              width: 16,
              height: 2,
              backgroundColor: '#FF6B6B',
              marginRight: 6,
              verticalAlign: 'middle',
            }}
          />
          RBA目標金利: {targetRate.toFixed(2)}%
        </div>
      )}

      <ZoomableChart
        data={data}
        height={400}
        dataKey="implied_yield"
        color="#00BFFF"
        name="インプライドイールド"
        xAxisTickFormatter={(value) => value}
        tickFormatter={(value) => `${value.toFixed(2)}%`}
        tooltipFormatter={(value) => `${value.toFixed(3)}%`}
        tooltipLabelFormatter={(value) => String(value)}
        domain={['dataMin - 0.1', 'dataMax + 0.1']}
        showZeroLine={false}
        showFiftyLine={false}
        enableDynamicTicks={false}
        hideMainLine={false}
      >
        {targetRate != null && (
          <RechartsReferenceLine
            y={targetRate}
            yAxisId="left"
            stroke="#FF6B6B"
            strokeDasharray="5 5"
            strokeWidth={1.5}
          />
        )}
      </ZoomableChart>
    </div>
  )
}
