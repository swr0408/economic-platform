/**
 * WSTS 半導体売上高チャートコンポーネント
 *
 * 2ビューモード:
 *   - 原数値: Monthly bar (Worldwide) + 3MMA line (Worldwide)
 *   - 前年比: Monthly line (5系列, 地域4つは初期非表示) + 3MMA line (Worldwide)
 *
 * データソース: WSTS (World Semiconductor Trade Statistics)
 *
 * FMPマッピング: なし
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'

import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../../usa/common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
  StandardBarChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'

import type { SemiconductorSalesData, SemiconductorSalesItem } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface Props {
  data: SemiconductorSalesData | null
}

type ViewMode = 'raw' | 'yoy'

const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'raw', label: '原数値' },
]

// カラー設定
const COLOR_WORLDWIDE = '#3b82f6'
const COLOR_WORLDWIDE_3MMA = '#e1c00b' // 3MMA: Worldwideより濃い青
const COLOR_AMERICAS = '#10b981'
const COLOR_EUROPE = '#f97316'
const COLOR_JAPAN = '#ef4444'
const COLOR_ASIA_PACIFIC = '#a855f7'

// 前年比モード: Monthly 5系列 + 3MMA Worldwide
const YOY_MONTHLY_SERIES = [
  { key: 'worldwide', label: 'Worldwide', color: COLOR_WORLDWIDE },
  { key: 'americas', label: 'Americas', color: COLOR_AMERICAS },
  { key: 'europe', label: 'Europe', color: COLOR_EUROPE },
  { key: 'japan', label: 'Japan', color: COLOR_JAPAN },
  { key: 'asia_pacific', label: 'Asia Pacific', color: COLOR_ASIA_PACIFIC },
] as const

const formatDateLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}/${month}`
}

const formatDateFull = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}年${parseInt(month)}月`
}

/** Monthly + 3MMAデータをdateでマージ */
function mergeWithMma(
  monthlyData: SemiconductorSalesItem[],
  mmaData: SemiconductorSalesItem[],
  mmaKey: string,
): Record<string, unknown>[] {
  const mmaMap = new Map<string, number | null>()
  for (const item of mmaData) {
    mmaMap.set(item.date, item.worldwide)
  }

  return monthlyData.map(item => ({
    ...item,
    [mmaKey]: mmaMap.get(item.date) ?? null,
  }))
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function SemiconductorSalesChart({ data }: Props) {
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<string>(
    ['americas', 'europe', 'japan', 'asia_pacific']
  )

  // ViewModeに応じたマージデータ
  const chartData = useMemo(() => {
    if (!data) return []
    if (viewMode === 'raw') {
      return mergeWithMma(data.data ?? [], data.mma_data ?? [], 'worldwide_3mma')
    } else {
      return mergeWithMma(data.yoy_data ?? [], data.mma_yoy_data ?? [], 'worldwide_3mma')
    }
  }, [data, viewMode])

  const sortedData = useSortedData(chartData as (Record<string, unknown> & { date: string })[])
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2016,
  })

  // ローディング
  if (data === null) {
    return (
      <div id="semiconductor-sales">
        <LoadingChart title="半導体売上高" />
      </div>
    )
  }

  if (chartData.length === 0) {
    return (
      <div id="semiconductor-sales">
        <ChartContainer title="半導体売上高">
          <NoDataMessage />
        </ChartContainer>
      </div>
    )
  }

  // 最新値
  const latestMonthly = viewMode === 'raw'
    ? (data.data?.length > 0 ? data.data[data.data.length - 1] : null)
    : (data.yoy_data?.length > 0 ? data.yoy_data[data.yoy_data.length - 1] : null)
  const latestMma = viewMode === 'raw'
    ? (data.mma_data?.length > 0 ? data.mma_data[data.mma_data.length - 1] : null)
    : (data.mma_yoy_data?.length > 0 ? data.mma_yoy_data[data.mma_yoy_data.length - 1] : null)

  const isYoy = viewMode === 'yoy'
  const unit = isYoy ? '%' : 'B'

  return (
    <div id="semiconductor-sales">
      <ChartContainer
        title="半導体売上高"
        showDataSource={true}
        dataSource="WSTS"
        sourceUrl="https://www.wsts.org/"
      >
        {/* 最新値ボックス */}
        <div style={{ ...LATEST_VALUE_BOX_STYLE, justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {latestMonthly?.date && (
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                {formatDateFull(latestMonthly.date)}
              </span>
            )}
            {viewMode === 'raw' ? (
              // 原数値: Worldwide (Monthly bar) + Worldwide 3MMA (line)
              <>
                <_LatestBox
                  label="Worldwide"
                  value={latestMonthly?.worldwide}
                  color={COLOR_WORLDWIDE}
                  hidden={false}
                  onClick={() => {}}
                  unit={unit}
                  decimals={1}
                  showSign={false}
                />
                <_LatestBox
                  label="3MMA"
                  value={latestMma?.worldwide}
                  color={COLOR_WORLDWIDE_3MMA}
                  hidden={hiddenSeries.has('worldwide_3mma')}
                  onClick={() => handleLegendClick('worldwide_3mma')}
                  unit={unit}
                  decimals={1}
                  showSign={false}
                />
              </>
            ) : (
              // 前年比: 5 Monthly系列 + 3MMA Worldwide
              <>
                {YOY_MONTHLY_SERIES.map(s => (
                  <_LatestBox
                    key={s.key}
                    label={s.label}
                    value={latestMonthly?.[s.key as keyof SemiconductorSalesItem] as number | null | undefined}
                    color={s.color}
                    hidden={hiddenSeries.has(s.key)}
                    onClick={() => handleLegendClick(s.key)}
                    unit={unit}
                    decimals={1}
                    showSign={true}
                  />
                ))}
                <_LatestBox
                  label="Worldwide3MMA"
                  value={latestMma?.worldwide}
                  color={COLOR_WORLDWIDE_3MMA}
                  hidden={hiddenSeries.has('worldwide_3mma')}
                  onClick={() => handleLegendClick('worldwide_3mma')}
                  unit={unit}
                  decimals={1}
                  showSign={true}
                />
              </>
            )}
          </div>
        </div>

        {/* ViewModeButtonGroup + データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <ViewModeButtonGroup
            options={VIEW_MODE_OPTIONS}
            currentMode={viewMode}
            onChange={setViewMode}
          />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=semiconductor_sales', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 期間選択 */}
        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

        {/* チャート */}
        {viewMode === 'raw' ? (
          // 原数値: Monthly bar + 3MMA line
          <StandardBarChart
            data={filteredData}
            bars={[
              { dataKey: 'worldwide', color: COLOR_WORLDWIDE, name: 'Worldwide' },
            ]}
            lines={[
              {
                dataKey: 'worldwide_3mma',
                color: COLOR_WORLDWIDE_3MMA,
                name: '3MMA',
                hide: hiddenSeries.has('worldwide_3mma'),
                strokeWidth: 2,
              },
            ]}
            xAxisFormatter={formatDateLabel}
            yAxisFormatter={(v: number) => `${v.toFixed(0)}B`}
            tooltipLabelFormatter={formatDateFull}
            tooltipValueFormatter={(v: number) => v != null ? `${v.toFixed(2)} Billion USD` : 'N/A'}
            yDomain={['dataMin - 1', 'dataMax + 1']}
            showZeroLine={false}
            onLegendClick={handleLegendClick}
          />
        ) : (
          // 前年比: Monthly line (5系列) + 3MMA line
          <StandardLineChart
            data={filteredData}
            lines={[
              ...YOY_MONTHLY_SERIES.map(s => ({
                dataKey: s.key,
                color: s.color,
                name: s.label,
                hide: hiddenSeries.has(s.key),
              })),
              {
                dataKey: 'worldwide_3mma',
                color: COLOR_WORLDWIDE_3MMA,
                name: 'Worldwide3MMA',
                hide: hiddenSeries.has('worldwide_3mma'),
                strokeDasharray: '6 3',
              },
            ]}
            xAxisFormatter={formatDateLabel}
            yAxisFormatter={(v: number) => `${v.toFixed(0)}%`}
            tooltipLabelFormatter={formatDateFull}
            tooltipValueFormatter={(v: number) => v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(1)}%` : 'N/A'}
            yDomain={['dataMin - 5', 'dataMax + 5']}
            showZeroLine={true}
            onLegendClick={handleLegendClick}
          />
        )}
      </ChartContainer>
    </div>
  )
}

// =============================================================================
// サブコンポーネント
// =============================================================================

function _LatestBox({
  label,
  value,
  color,
  hidden,
  onClick,
  unit,
  decimals,
  showSign,
}: {
  label: string
  value: number | null | undefined
  color: string
  hidden: boolean
  onClick: () => void
  unit: string
  decimals: number
  showSign: boolean
}) {
  const formatted = value != null
    ? `${showSign && value >= 0 ? '+' : ''}${value.toFixed(decimals)}${unit}`
    : '—'

  return (
    <span
      onClick={onClick}
      style={{
        cursor: 'pointer',
        opacity: hidden ? 0.3 : 1,
        marginRight: 8,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
      }}
    >
      <span
        style={{
          display: 'inline-block',
          width: 10,
          height: 10,
          borderRadius: '50%',
          backgroundColor: color,
        }}
      />
      <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>{label}</span>
      <span style={{ fontSize: 16, fontWeight: 700, color }}>
        {formatted}
      </span>
    </span>
  )
}
