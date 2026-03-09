/**
 * シカゴ連銀小売物価指数（CARTS Fig6）チャートコンポーネント
 *
 * Retail & Food Services Prices Ex. Auto (SA, y/y % chg.) を表示
 * - BEA（廃止）
 * - 商品CPI（自動車除く）
 * - CARTS Nowcast（シカゴ連銀CPI予想）
 *
 * データソース: Chicago Fed CARTS
 */
import { useState, useMemo } from 'react'
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
import type { RetailFoodServicesPriceData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabel,
  type PeriodType,
} from '../common/useChartData'
import {
  NoDataMessage,
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

interface RetailFoodServicesPriceChartProps {
  retailFoodServicesPriceData: RetailFoodServicesPriceData | null
}

// カラー設定
const COLORS = {
  bea: '#ef4444',         // BEA（赤）- 廃止
  cpi: '#3b82f6',         // 商品CPI（青）
  carts_nowcast: '#10b981', // CARTS Nowcast（緑）
}

// 項目の日本語名
const LABELS: Record<string, string> = {
  bea: 'BEA（廃止）',
  cpi: '商品CPI（自動車除く）',
  carts_nowcast: 'CARTS Nowcast',
}

// =============================================================================
// カスタムツールチップ
// =============================================================================

function RetailFoodServicesPriceTooltip({ active, payload, label }: {
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
        const displayName = LABELS[item.dataKey] || item.name

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
              {item.value != null ? `${item.value.toFixed(2)}%` : '-'}
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

export default function RetailFoodServicesPriceChart({ retailFoodServicesPriceData }: RetailFoodServicesPriceChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(10)

  // データを日付昇順にソート
  const sortedData = useSortedData(retailFoodServicesPriceData?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  // 最新値
  const latestCpi = useMemo(() => {
    if (!retailFoodServicesPriceData?.latest) return null
    return retailFoodServicesPriceData.latest.cpi
  }, [retailFoodServicesPriceData])

  const latestCartsNowcast = useMemo(() => {
    if (!retailFoodServicesPriceData?.latest) return null
    return retailFoodServicesPriceData.latest.carts_nowcast
  }, [retailFoodServicesPriceData])

  const latestDate = useMemo(() => {
    if (!retailFoodServicesPriceData?.latest) return undefined
    return retailFoodServicesPriceData.latest.date
  }, [retailFoodServicesPriceData])

  const hasData = sortedData.length > 0

  // ローディング状態
  if (retailFoodServicesPriceData === null) {
    return <LoadingChart title="シカゴ連銀小売物価指数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="シカゴ連銀小売物価指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="retail-food-services-price">
      <ChartContainer
        title="シカゴ連銀小売物価指数"
        showPeriodSelector={false}
        dataSource="Chicago Fed CARTS"
        sourceUrl="https://www.chicagofed.org/research/data/carts/dashboard"
      >
        {/* 最新値表示 */}
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 16,
          marginBottom: 16,
          padding: '12px 16px',
          background: DARK_THEME.bgSecondary,
          borderRadius: 8,
          border: `1px solid ${DARK_THEME.border}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: DARK_THEME.textSecondary, fontSize: 13 }}>商品CPI（自動車除く）:</span>
            <span style={{ color: COLORS.cpi, fontWeight: 600, fontSize: 16 }}>
              {latestCpi != null ? `${latestCpi.toFixed(2)}%` : '-'}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: DARK_THEME.textSecondary, fontSize: 13 }}>CARTS Nowcast:</span>
            <span style={{ color: COLORS.carts_nowcast, fontWeight: 600, fontSize: 16 }}>
              {latestCartsNowcast != null ? `${latestCartsNowcast.toFixed(2)}%` : '-'}
            </span>
          </div>
          {latestDate && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ color: DARK_THEME.textSecondary, fontSize: 13 }}>最終更新:</span>
              <span style={{ color: DARK_THEME.textPrimary, fontSize: 13 }}>
                {formatDateLabel(latestDate)}
              </span>
            </div>
          )}
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
              domain={[(dataMin: number) => Math.floor(dataMin - 1), (dataMax: number) => Math.ceil(dataMax + 1)]}
              tick={AXIS_STYLE.tick}
              tickFormatter={(v) => `${v}%`}
            />
            <RechartsTooltip content={<RetailFoodServicesPriceTooltip />} />
            <Legend />
            <ReferenceLine {...ZERO_LINE_PROPS} />
            {/* BEA（廃止） - 現在はデータがほぼないが過去データ用に残す */}
            <Line
              type="monotone"
              dataKey="bea"
              stroke={COLORS.bea}
              strokeWidth={2}
              dot={false}
              name={LABELS.bea}
              isAnimationActive={false}
              connectNulls={false}
            />
            {/* 商品CPI（自動車除く） */}
            <Line
              type="monotone"
              dataKey="cpi"
              stroke={COLORS.cpi}
              strokeWidth={2}
              dot={false}
              name={LABELS.cpi}
              isAnimationActive={false}
              connectNulls={false}
            />
            {/* CARTS Nowcast - ドット表示 */}
            <Line
              type="monotone"
              dataKey="carts_nowcast"
              stroke={COLORS.carts_nowcast}
              strokeWidth={0}
              dot={{ fill: COLORS.carts_nowcast, strokeWidth: 1, r: 3 }}
              name={LABELS.carts_nowcast}
              isAnimationActive={false}
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
