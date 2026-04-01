/**
 * CPI項目別チャートコンポーネント
 *
 * 食品、エネルギー、コア財、コアサービス、住居費の前年比を表示
 * エネルギーは変動が大きいため右Y軸に表示
 */
import { useState } from 'react'
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
import type { CPICategoriesData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
  formatDateLabel,
  type PeriodType,
} from '../common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
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

interface CPICategoriesChartProps {
  categoriesData: CPICategoriesData | null
}

// カラー設定
const COLORS = {
  food: '#ef4444',          // 食品（赤）
  energy: '#f97316',        // エネルギー（オレンジ）
  core_goods: '#3b82f6',    // コア財（青）
  core_services: '#a855f7', // コアサービス（紫）
  shelter: '#10b981',       // 住居費（緑）
}

// 項目の日本語名
const CATEGORY_LABELS: Record<string, string> = {
  food: '食品',
  energy: 'エネルギー',
  core_goods: 'コア財',
  core_services: 'コアサービス',
  shelter: '住居費',
}

// =============================================================================
// カスタムツールチップ
// =============================================================================

function CategoryTooltip({ active, payload, label }: {
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
      {payload.map((item, index) => {
        // エネルギーは「（右軸）」を表示名に含むので、dataKeyで判定
        const isEnergy = item.dataKey === 'energy'
        const displayName = isEnergy ? `${CATEGORY_LABELS.energy}（右軸）` : (CATEGORY_LABELS[item.dataKey] || item.name)
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
              {displayName}
            </span>
            <span style={{ fontWeight: 500, color: item.color }}>
              {item.value.toFixed(2)}%
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

export default function CPICategoriesChart({ categoriesData }: CPICategoriesChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(10)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データを日付昇順にソート
  const sortedData = useSortedData(categoriesData?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = sortedData.length > 0

  // ローディング状態
  if (categoriesData === null) {
    return <LoadingChart title="CPI 項目別" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="CPI 項目別" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = categoriesData?.latest

  return (
    <div id="cpi-categories">
      <ChartContainer
        title="CPI 項目別（前年比）"
        showPeriodSelector={false}
        dataSource="FRED (BLS)"
        sourceUrl="https://www.bls.gov/cpi/"
        handbookId="cpi-categories"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: CATEGORY_LABELS.food,
              value: latest?.food,
              color: COLORS.food,
              format: 'percent',
            },
            {
              label: CATEGORY_LABELS.energy,
              value: latest?.energy,
              color: COLORS.energy,
              format: 'percent',
            },
            {
              label: CATEGORY_LABELS.core_goods,
              value: latest?.core_goods,
              color: COLORS.core_goods,
              format: 'percent',
            },
            {
              label: CATEGORY_LABELS.core_services,
              value: latest?.core_services,
              color: COLORS.core_services,
              format: 'percent',
            },
            {
              label: CATEGORY_LABELS.shelter,
              value: latest?.shelter,
              color: COLORS.shelter,
              format: 'percent',
            },
          ]}
          date={latest?.date}
        />

        {/* 期間選択 */}
        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

        {/* 折れ線グラフ（エネルギーは右Y軸） */}
        <ResponsiveContainer width="100%" height={450}>
          <LineChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid {...CARTESIAN_GRID_PROPS} />
            <XAxis
              dataKey="date"
              tickFormatter={formatDateLabel}
              tick={AXIS_STYLE.tick}
              interval={AXIS_STYLE.interval}
            />
            {/* 左Y軸（食品、コア財、コアサービス、住居費） */}
            <YAxis
              yAxisId="left"
              domain={[(dataMin: number) => Math.floor(dataMin - 1), (dataMax: number) => Math.ceil(dataMax + 1)]}
              tick={AXIS_STYLE.tick}
              tickFormatter={(v) => `${v}%`}
            />
            {/* 右Y軸（エネルギー） */}
            <YAxis
              yAxisId="right"
              orientation="right"
              domain={[(dataMin: number) => Math.floor(dataMin - 5), (dataMax: number) => Math.ceil(dataMax + 5)]}
              tick={{ ...AXIS_STYLE.tick, fill: COLORS.energy }}
              tickFormatter={(v) => `${v}%`}
            />
            <RechartsTooltip content={<CategoryTooltip />} />
            <Legend
              onClick={(e) => handleLegendClick(e.dataKey as string)}
              wrapperStyle={{ cursor: 'pointer' }}
            />
            <ReferenceLine yAxisId="left" {...ZERO_LINE_PROPS} />
            {/* 左Y軸の線 */}
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="food"
              stroke={COLORS.food}
              strokeWidth={2}
              dot={false}
              name={CATEGORY_LABELS.food}
              hide={hiddenSeries.has('food')}
              isAnimationActive={false}
              connectNulls={true}
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="core_goods"
              stroke={COLORS.core_goods}
              strokeWidth={2}
              dot={false}
              name={CATEGORY_LABELS.core_goods}
              hide={hiddenSeries.has('core_goods')}
              isAnimationActive={false}
              connectNulls={true}
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="core_services"
              stroke={COLORS.core_services}
              strokeWidth={2}
              dot={false}
              name={CATEGORY_LABELS.core_services}
              hide={hiddenSeries.has('core_services')}
              isAnimationActive={false}
              connectNulls={true}
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="shelter"
              stroke={COLORS.shelter}
              strokeWidth={2}
              dot={false}
              name={CATEGORY_LABELS.shelter}
              hide={hiddenSeries.has('shelter')}
              isAnimationActive={false}
              connectNulls={true}
            />
            {/* 右Y軸の線（エネルギー） */}
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="energy"
              stroke={COLORS.energy}
              strokeWidth={2}
              dot={false}
              name={`${CATEGORY_LABELS.energy}（右軸）`}
              hide={hiddenSeries.has('energy')}
              isAnimationActive={false}
              connectNulls={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
