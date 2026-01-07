/**
 * 30年固定住宅ローン金利チャートコンポーネント
 *
 * Freddie Mac Primary Mortgage Market Survey から取得した
 * 30年固定住宅ローン金利を表示
 * データソース: FRED (MORTGAGE30US)
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { MortgageRatesData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  usePeriodFiltering,
  formatDateLabel,
  type PeriodType,
} from '../common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  type TooltipPayloadItem,
} from '../common/ChartComponents'
import {
  TOOLTIP_STYLE,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  DARK_THEME,
} from '../common/chartConstants'

// =============================================================================
// 型定義
// =============================================================================

interface MortgageRatesChartProps {
  mortgageRatesData: MortgageRatesData | null
}

// カラー設定
const CHART_COLOR = '#8b5cf6'

// =============================================================================
// カスタムツールチップ
// =============================================================================

function MortgageRatesTooltip({ active, payload, label }: {
  active?: boolean
  payload?: TooltipPayloadItem[]
  label?: string
}) {
  if (!active || !payload || payload.length === 0) return null

  const item = payload[0]

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
        {formatDateLabel(label || '')}
      </div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
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
          30年固定金利
        </span>
        <span style={{ fontWeight: 500, color: item.color }}>
          {item.value != null ? `${item.value.toFixed(2)}%` : '-'}
        </span>
      </div>
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function MortgageRatesChart({ mortgageRatesData }: MortgageRatesChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>('default')

  // データを準備
  const chartData = useMemo(() => {
    if (!mortgageRatesData?.data) return []
    return mortgageRatesData.data
  }, [mortgageRatesData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  // 最新値
  const latestValue = useMemo(() => {
    return mortgageRatesData?.latest?.value ?? null
  }, [mortgageRatesData])

  const latestDate = useMemo(() => {
    return mortgageRatesData?.latest?.date
  }, [mortgageRatesData])

  const hasData = chartData.length > 0

  // ローディング状態
  if (mortgageRatesData === null) {
    return <LoadingChart title="30年固定住宅ローン金利" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="30年固定住宅ローン金利" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="mortgage-rates">
      <ChartContainer
        title="30年固定住宅ローン金利"
        showPeriodSelector={false}
        dataSource="FreddieMac"
        sourceUrl="https://www.freddiemac.com/pmms"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="30年固定金利"
          value={latestValue}
          unit="%"
          valueColor={CHART_COLOR}
          date={latestDate}
          nextRelease={mortgageRatesData?.next_release}
        />

        {/* データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
          <Tooltip title="比較ページを開く（住宅ローン金利）">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=us_mortgage_rate_30y', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 期間選択 */}
        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

        {/* 折れ線グラフ */}
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid {...CARTESIAN_GRID_PROPS} />
            <XAxis
              dataKey="date"
              tickFormatter={formatDateLabel}
              tick={AXIS_STYLE.tick}
              interval={AXIS_STYLE.interval}
            />
            <YAxis
              domain={['dataMin - 0.2', 'dataMax + 0.2']}
              tick={AXIS_STYLE.tick}
              tickFormatter={(v) => `${v}%`}
            />
            <RechartsTooltip content={<MortgageRatesTooltip />} />
            <Line
              type="monotone"
              dataKey="value"
              stroke={CHART_COLOR}
              strokeWidth={2}
              dot={false}
              name="30年固定金利"
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
