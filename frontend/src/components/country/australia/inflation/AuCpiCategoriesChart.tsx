/**
 * AU CPI Categories Chart Component
 * オーストラリア CPIカテゴリ別チャート
 *
 * 6系列（前年比）:
 * - Goods (財)
 * - Services (サービス)
 * - Electricity (電力) ← 右Y軸（変動大）
 * - Rents (家賃)
 * - New dwellings (新築住宅)
 * - Food & non-alcoholic beverages (食品)
 *
 * データソース: Australian Bureau of Statistics (ABS)
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
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
  formatDateLabel,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
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

import type { AuCpiCategoriesData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface AuCpiCategoriesChartProps {
  data: AuCpiCategoriesData | null
}

// カラー設定
const COLORS: Record<string, string> = {
  goods_yoy: '#3b82f6',        // 財（青）
  services_yoy: '#a855f7',     // サービス（紫）
  electricity_yoy: '#f97316',  // 電力（オレンジ）← 右Y軸
  rents_yoy: '#10b981',        // 家賃（緑）
  new_dwellings_yoy: '#06b6d4', // 新築住宅（シアン）
  food_yoy: '#ef4444',         // 食品（赤）
}

// 項目の日本語名
const CATEGORY_LABELS: Record<string, string> = {
  goods_yoy: '財',
  services_yoy: 'サービス',
  electricity_yoy: '電力',
  rents_yoy: '家賃',
  new_dwellings_yoy: '新築住宅',
  food_yoy: '食品',
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
        const isElectricity = item.dataKey === 'electricity_yoy'
        const displayName = isElectricity
          ? `${CATEGORY_LABELS.electricity_yoy}（右軸）`
          : (CATEGORY_LABELS[item.dataKey] || item.name)
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
              {item.value !== null && item.value !== undefined
                ? `${item.value >= 0 ? '+' : ''}${item.value.toFixed(1)}%`
                : 'N/A'}
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

export default function AuCpiCategoriesChart({ data }: AuCpiCategoriesChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(20)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データを日付昇順にソート
  const sortedData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2019,
  })

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="CPI カテゴリ別" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="CPI カテゴリ別" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  return (
    <div id="au-cpi-categories-chart">
      <ChartContainer
        title="CPI カテゴリ別（前年比）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="Australian Bureau of Statistics"
        sourceUrl="https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/monthly-consumer-price-index-indicator"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            { label: '財', value: latest?.goods_yoy, color: COLORS.goods_yoy, format: 'percent' },
            { label: 'サービス', value: latest?.services_yoy, color: COLORS.services_yoy, format: 'percent' },
            { label: '電力', value: latest?.electricity_yoy, color: COLORS.electricity_yoy, format: 'percent' },
            { label: '家賃', value: latest?.rents_yoy, color: COLORS.rents_yoy, format: 'percent' },
            { label: '新築住宅', value: latest?.new_dwellings_yoy, color: COLORS.new_dwellings_yoy, format: 'percent' },
            { label: '食品', value: latest?.food_yoy, color: COLORS.food_yoy, format: 'percent' },
          ]}
          date={latest?.date}
        />

        {/* 期間選択 + データ比較 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <AntTooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=au_cpi_goods_yoy', '_blank')}
            >
              データ比較
            </Button>
          </AntTooltip>
        </div>

        {/* 折れ線グラフ（電力は右Y軸） */}
        <ResponsiveContainer width="100%" height={450}>
          <LineChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid {...CARTESIAN_GRID_PROPS} />
            <XAxis
              dataKey="date"
              tickFormatter={formatDateLabel}
              tick={AXIS_STYLE.tick}
              interval={AXIS_STYLE.interval}
            />
            {/* 左Y軸 */}
            <YAxis
              yAxisId="left"
              domain={[(dataMin: number) => Math.floor(dataMin - 1), (dataMax: number) => Math.ceil(dataMax + 1)]}
              tick={AXIS_STYLE.tick}
              tickFormatter={(v) => `${v}%`}
            />
            {/* 右Y軸（電力） */}
            <YAxis
              yAxisId="right"
              orientation="right"
              domain={[(dataMin: number) => Math.floor(dataMin - 5), (dataMax: number) => Math.ceil(dataMax + 5)]}
              tick={{ ...AXIS_STYLE.tick, fill: COLORS.electricity_yoy }}
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
              dataKey="goods_yoy"
              stroke={COLORS.goods_yoy}
              strokeWidth={2}
              dot={false}
              name={CATEGORY_LABELS.goods_yoy}
              hide={hiddenSeries.has('goods_yoy')}
              isAnimationActive={false}
              connectNulls={true}
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="services_yoy"
              stroke={COLORS.services_yoy}
              strokeWidth={2}
              dot={false}
              name={CATEGORY_LABELS.services_yoy}
              hide={hiddenSeries.has('services_yoy')}
              isAnimationActive={false}
              connectNulls={true}
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="rents_yoy"
              stroke={COLORS.rents_yoy}
              strokeWidth={2}
              dot={false}
              name={CATEGORY_LABELS.rents_yoy}
              hide={hiddenSeries.has('rents_yoy')}
              isAnimationActive={false}
              connectNulls={true}
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="new_dwellings_yoy"
              stroke={COLORS.new_dwellings_yoy}
              strokeWidth={2}
              dot={false}
              name={CATEGORY_LABELS.new_dwellings_yoy}
              hide={hiddenSeries.has('new_dwellings_yoy')}
              isAnimationActive={false}
              connectNulls={true}
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="food_yoy"
              stroke={COLORS.food_yoy}
              strokeWidth={2}
              dot={false}
              name={CATEGORY_LABELS.food_yoy}
              hide={hiddenSeries.has('food_yoy')}
              isAnimationActive={false}
              connectNulls={true}
            />
            {/* 右Y軸の線（電力） */}
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="electricity_yoy"
              stroke={COLORS.electricity_yoy}
              strokeWidth={2}
              dot={false}
              name={`${CATEGORY_LABELS.electricity_yoy}（右軸）`}
              hide={hiddenSeries.has('electricity_yoy')}
              isAnimationActive={false}
              connectNulls={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
