/**
 * Affinityカード支出チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState } from 'react'
import { Button, Tooltip as AntTooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { AffinitySpendData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  TOOLTIP_STYLE,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabel,
  formatDateLabelJP,
  type PeriodType,
} from '../common/useChartData'
import { NoDataMessage, SimpleLatestValueBox, ZERO_LINE_PROPS } from '../common/ChartComponents'


// =============================================================================
// 型定義
// =============================================================================

interface AffinitySpendChartProps {
  data: AffinitySpendData | null
}

// カラー設定
const COLOR = '#2f54eb'

// 系列名
const SERIES_NAME = 'クレジット / デビットカード支出'

// =============================================================================
// カスタムTooltip
// =============================================================================

interface TooltipPayload {
  name: string
  value: number
  color: string
  dataKey: string
}

interface CustomTooltipProps {
  active?: boolean
  payload?: TooltipPayload[]
  label?: string
}

function AffinityTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null

  const value = payload[0]?.value

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, padding: '8px 12px' }}>
        {formatDateLabelJP(label || '')}
      </div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 4,
          fontSize: 13,
          padding: '4px 12px',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
          <span
            style={{
              display: 'inline-block',
              width: 10,
              height: 10,
              borderRadius: 2,
              backgroundColor: COLOR,
              marginRight: 6,
            }}
          />
          {SERIES_NAME}
        </span>
        <span style={{ fontWeight: 500, color: COLOR }}>
          {value !== null && value !== undefined ? `${value >= 0 ? '+' : ''}${value.toFixed(1)}%` : 'N/A'}
        </span>
      </div>
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function AffinitySpendChart({ data }: AffinitySpendChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)

  // データを日付昇順にソート
  const chartData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="Affinityカード支出" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="Affinityカード支出" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="affinity-spend">
      <ChartContainer
        title="クレジット / デビットカードカード支出"
        showPeriodSelector={false}
        dataSource="Opportunity Insights Economic Tracker"
        sourceUrl="https://economictracker.org/"
        handbookId="affinity-spend"
      >
        {/* 最新値表示 */}
        {latest && (
          <SimpleLatestValueBox
            label="2020年1月比"
            value={latest.value}
            valueColor={COLOR}
            date={latest.date}
            format="percent"
            decimals={1}
          />
        )}

        {/* 時系列チャート */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, marginTop: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <AntTooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=affinity_spending', '_blank')}
            >
              データ比較
            </Button>
          </AntTooltip>
        </div>
        <ResponsiveContainer width="100%" height={450}>
          <LineChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid {...CARTESIAN_GRID_PROPS} />
            <XAxis dataKey="date" tickFormatter={formatDateLabel} tick={AXIS_STYLE.tick} interval={AXIS_STYLE.interval} />
            <YAxis domain={['dataMin - 5', 'dataMax + 5']} tick={AXIS_STYLE.tick} tickFormatter={(v) => `${v}%`} />
            <Tooltip content={<AffinityTooltip />} />
            <ReferenceLine {...ZERO_LINE_PROPS} />
            <Line type="monotone" dataKey="value" name="クレジット / デビットカードカード支出" stroke={COLOR} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls={true} />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
