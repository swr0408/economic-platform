/**
 * FCI-G（金融情勢指数）チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState, useMemo } from 'react'
import { Tooltip as RechartsTooltip } from 'recharts'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { FCIData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS, CUSTOM_TOOLTIP_STYLE } from '../common/chartConstants'
import { usePeriodFiltering, formatDateLabel, type PeriodType } from '../common/useChartData'
import { NoDataMessage } from '../common/ChartComponents'

interface FCIChartProps {
  data: FCIData | null
}

interface ChartDataPoint {
  date: string
  value: number
  baseline: number | null
  oneyear: number | null
  [key: string]: string | number | null | undefined
}

export default function FCIChart({ data }: FCIChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)

  // 両シリーズのデータを統合
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const baselineData = data.baseline?.data || []
    const oneyearData = data.oneyear?.data || []

    // 全ての日付を収集
    const allDates = new Set<string>()
    baselineData.forEach((d) => allDates.add(d.date))
    oneyearData.forEach((d) => allDates.add(d.date))

    // 日付でソート
    const sortedDates = Array.from(allDates).sort(
      (a, b) => new Date(a).getTime() - new Date(b).getTime()
    )

    // データをマージ
    return sortedDates.map((date) => {
      const baselinePoint = baselineData.find((d) => d.date === date)
      const oneyearPoint = oneyearData.find((d) => d.date === date)

      return {
        date,
        value: baselinePoint?.value ?? 0,
        baseline: baselinePoint?.value ?? null,
        oneyear: oneyearPoint?.value ?? null,
      }
    })
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="FCI-G（金融情勢指数）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="FCI-G（金融情勢指数）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestBaseline = data.baseline?.latest
  const latestOneyear = data.oneyear?.latest

  const formatValue = (value: number | null) => {
    if (value === null || value === undefined) return '-'
    return value.toFixed(2)
  }

  const formatMonthLabel = formatDateLabel

  // カスタムツールチップ
  const CustomTooltip = ({
    active,
    payload,
    label,
  }: {
    active?: boolean
    payload?: Array<{
      name: string
      value: number | null
      color: string
      dataKey: string
    }>
    label?: string
  }) => {
    if (!active || !payload || payload.length === 0) return null

    return (
      <div style={CUSTOM_TOOLTIP_STYLE}>
        <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14 }}>
          {formatMonthLabel(label || '')}
        </div>
        {payload.map((item, index) => {
          const seriesName = item.dataKey === 'baseline' ? 'Baseline (3-year)' : 'One-year lookback'
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
                {seriesName}
              </span>
              <span style={{ fontWeight: 500, color: item.color }}>
                {formatValue(item.value)}
              </span>
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div id="fci-chart">
      <ChartContainer
        title="FCI-G（金融情勢指数）"
        showPeriodSelector={false}
        dataSource="Federal Reserve"
        sourceUrl="https://www.federalreserve.gov/econres/notes/feds-notes/a-new-index-to-measure-us-financial-conditions-20230630.html"
      >
        {/* 最新値表示 */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          {/* Baseline (3-year) */}
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, color: TEXT_COLORS.secondary, marginBottom: 2 }}>
              Baseline (3-year)
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <span
                style={{
                  fontSize: 16,
                  fontWeight: 'bold',
                  color: '#1890ff',
                }}
              >
                {latestBaseline ? formatValue(latestBaseline.value) : '-'}
              </span>
              {latestBaseline && (
                <span style={{ fontSize: 11, color: TEXT_COLORS.tertiary }}>
                  ({formatMonthLabel(latestBaseline.date)})
                </span>
              )}
            </div>
          </div>

          {/* One-year lookback */}
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, color: TEXT_COLORS.secondary, marginBottom: 2 }}>
              One-year lookback
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <span
                style={{
                  fontSize: 16,
                  fontWeight: 'bold',
                  color: '#52c41a',
                }}
              >
                {latestOneyear ? formatValue(latestOneyear.value) : '-'}
              </span>
              {latestOneyear && (
                <span style={{ fontSize: 11, color: TEXT_COLORS.tertiary }}>
                  ({formatMonthLabel(latestOneyear.date)})
                </span>
              )}
            </div>
          </div>
        </div>

        {/* 期間セレクタ + 比較ボタン（横並び） */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=fci_baseline', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* チャート */}
        <ZoomableChart
          data={filteredData}
          dataKey="baseline"
          color="#1890ff"
          name="Baseline (3-year)"
          height={450}
          tickFormatter={(v) => v.toFixed(1)}
          xAxisTickFormatter={formatMonthLabel}
          enableDynamicTicks={true}
          showZeroLine={true}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={false}
          showDefaultTooltip={false}
          additionalLines={[
            {
              dataKey: 'oneyear',
              color: '#52c41a',
              name: 'One-year lookback',
              strokeWidth: 2,
            },
          ]}
        >
          <RechartsTooltip content={<CustomTooltip />} />
        </ZoomableChart>
      </ChartContainer>
    </div>
  )
}
