/**
 * 潜在成長率チャート（内閣府）
 *
 * データソース: 内閣府（Cabinet Office）
 * 更新: 不定期
 *
 * 表示内容:
 * - 潜在成長率 - 折れ線グラフ
 */
import { useState, useEffect, useMemo } from 'react'
import { Spin, Alert, Button } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  fetchPotentialGrowthData,
  type PotentialGrowthData,
} from '../../../../utils/japan/potentialGrowthApi'

// 共通モジュールのインポート
import { type PeriodType } from '../../usa/common/useChartData'
import {
  SimpleLatestValueBox,
  ZERO_LINE_PROPS,
  type TooltipPayloadItem,
} from '../../usa/common/ChartComponents'
import {
  TOOLTIP_STYLE,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  DARK_THEME,
} from '../../usa/common/chartConstants'

// =============================================================================
// 四半期フォーマット
// =============================================================================

function formatQuarterLabel(dateStr: string): string {
  // YYYY-Q1 -> 2024年Q1
  const match = dateStr.match(/^(\d{4})-Q([1-4])$/)
  if (match) {
    return `${match[1]}年Q${match[2]}`
  }
  return dateStr
}

// =============================================================================
// カスタムツールチップ
// =============================================================================

function PotentialGrowthTooltip({ active, payload, label }: {
  active?: boolean
  payload?: TooltipPayloadItem[]
  label?: string
}) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
        {formatQuarterLabel(label || '')}
      </div>
      {payload.map((item, index) => {
        const value = item.value
        const sign = value >= 0 ? '+' : ''
        return (
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
            <span style={{ fontWeight: 500, color: value >= 0 ? '#10b981' : '#ef4444' }}>
              {value != null ? `${sign}${value.toFixed(2)}%` : '-'}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

const PotentialGrowthChart: React.FC = () => {
  const [data, setData] = useState<PotentialGrowthData | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>('default')

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await fetchPotentialGrowthData()
      setData(response)
    } catch (err) {
      console.error('Error fetching Potential Growth data:', err)
      setError('データの取得に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    if (!data?.data) return []

    const sorted = [...data.data].sort((a, b) => {
      const aYear = parseInt(a.date.slice(0, 4))
      const bYear = parseInt(b.date.slice(0, 4))
      if (aYear !== bYear) return aYear - bYear
      return a.date.localeCompare(b.date)
    })

    if (currentPeriod === 'default' || currentPeriod === 'all') {
      return sorted
    }

    const years = typeof currentPeriod === 'number' ? currentPeriod : 10
    const now = new Date()
    const cutoffYear = now.getFullYear() - years

    return sorted.filter(item => {
      const match = item.date.match(/^(\d{4})/)
      if (match) {
        return parseInt(match[1], 10) >= cutoffYear
      }
      return true
    })
  }, [data, currentPeriod])

  if (loading) {
    return (
      <ChartContainer title="潜在成長率" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16, color: DARK_THEME.textSecondary }}>
            データ読み込み中...
          </div>
        </div>
      </ChartContainer>
    )
  }

  if (error) {
    return (
      <ChartContainer title="潜在成長率" showPeriodSelector={false} showDataSource={false}>
        <Alert message="エラー" description={error} type="error" showIcon />
      </ChartContainer>
    )
  }

  // 最新値の色を決定
  const latestValue = data?.latest?.value
  const latestColor = latestValue !== undefined && latestValue !== null
    ? (latestValue >= 0 ? '#10b981' : '#ef4444')
    : '#36A2EB'

  return (
    <div id="japan-potential-growth">
      <ChartContainer
        title="潜在成長率（内閣府）"
        showPeriodSelector={false}
        dataSource="内閣府"
        sourceUrl="https://www5.cao.go.jp/keizai3/getsurei/getsurei-index.html#sonota"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="潜在成長率"
          value={data?.latest?.value}
          valueColor={latestColor}
          date={data?.latest?.date}
          format="percent"
          dateFormatter={formatQuarterLabel}
        />

        {/* コントロール行 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Button
            icon={<AreaChartOutlined />}
            onClick={() => {
              window.open('/compare?s=japan_potential_growth', '_blank')
            }}
          >
            データ比較
          </Button>
        </div>

        {/* チャート */}
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid {...CARTESIAN_GRID_PROPS} />
            <XAxis
              dataKey="date"
              tickFormatter={formatQuarterLabel}
              tick={AXIS_STYLE.tick}
              interval={Math.floor(filteredData.length / 8)}
            />
            <YAxis
              domain={[(dataMin: number) => Math.floor(dataMin * 10 - 1) / 10, (dataMax: number) => Math.ceil(dataMax * 10 + 1) / 10]}
              tick={AXIS_STYLE.tick}
              tickFormatter={(v: number) => `${v.toFixed(1)}%`}
            />
            <RechartsTooltip content={<PotentialGrowthTooltip />} />
            <ReferenceLine {...ZERO_LINE_PROPS} />
            <Line
              type="monotone"
              dataKey="value"
              stroke="#36A2EB"
              strokeWidth={2}
              dot={false}
              name="潜在成長率"
              isAnimationActive={false}
              connectNulls={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}

export default PotentialGrowthChart
