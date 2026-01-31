/**
 * グローバルサプライチェーン圧力指数（GSCPI）チャートコンポーネント
 *
 * NY連銀のGlobal Supply Chain Pressure Indexを表示
 * - 0がサプライチェーン圧力の平均値
 * - 正の値は圧力上昇を示す
 *
 * データソース: NY連銀（Federal Reserve Bank of New York）
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
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { GSCPIData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabel,
  type PeriodType,
} from '../common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  ZERO_LINE_PROPS,
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

interface GSCPIChartProps {
  gscpiData: GSCPIData | null
}

// カラー設定
const GSCPI_COLOR = '#722ed1' // 紫

// =============================================================================
// カスタムツールチップ
// =============================================================================

function GSCPITooltip({ active, payload, label }: {
  active?: boolean
  payload?: TooltipPayloadItem[]
  label?: string
}) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
        {formatDateLabel(label || '')}
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
            GSCPI
          </span>
          <span style={{ fontWeight: 500, color: item.color }}>
            {item.value != null ? item.value.toFixed(3) : '-'}
          </span>
        </div>
      ))}
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function GSCPIChart({ gscpiData }: GSCPIChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>('default')

  // データを日付昇順にソート
  const sortedData = useSortedData(gscpiData?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // 最新値
  const latestValue = useMemo(() => {
    if (!gscpiData?.latest) return null
    return gscpiData.latest.value
  }, [gscpiData])

  const latestDate = useMemo(() => {
    if (!gscpiData?.latest) return undefined
    return gscpiData.latest.date
  }, [gscpiData])

  const hasData = sortedData.length > 0

  // ローディング状態
  if (gscpiData === null) {
    return <LoadingChart title="Global Supply Chain Pressure Index" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="Global Supply Chain Pressure Index" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="gscpi">
      <ChartContainer
        title="グローバルサプライチェーン圧力指数（GSCPI）"
        showPeriodSelector={false}
        dataSource="NY Fed"
        sourceUrl="https://www.newyorkfed.org/research/policy/gscpi#/interactive"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="GSCPI"
          value={latestValue}
          valueColor={GSCPI_COLOR}
          format="number"
          decimals={3}
          date={latestDate}
          nextRelease={gscpiData.next_release}
        />

        {/* 期間セレクタ + 比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く（GSCPI）">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=us_gscpi', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

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
              domain={[(dataMin: number) => Math.floor(dataMin - 0.5), (dataMax: number) => Math.ceil(dataMax + 0.5)]}
              tick={AXIS_STYLE.tick}
              tickFormatter={(v) => v.toFixed(1)}
            />
            <RechartsTooltip content={<GSCPITooltip />} />
            <Legend />
            <ReferenceLine {...ZERO_LINE_PROPS} />
            <Line
              type="monotone"
              dataKey="value"
              stroke={GSCPI_COLOR}
              strokeWidth={2}
              dot={false}
              name="GSCPI"
              isAnimationActive={false}
              connectNulls={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
