/**
 * 経済政策不確実性指数（EPU）チャートコンポーネント
 *
 * データ:
 * - Global EPU Index (月次) - FRED GEPUCURRENT
 * - US EPU Index (月次) - policyuncertainty.com Excel
 * - US EPU Index (日次) - policyuncertainty.com CSV（米国モード時に背景表示）
 *
 * データソース:
 * - Economic Policy Uncertainty (policyuncertainty.com)
 *
 * FMPマッピング: なし
 */
import { useState, useEffect, useCallback, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabel,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import {
  CHART_MARGIN,
  CARTESIAN_GRID_PROPS,
  AXIS_STYLE,
  TOOLTIP_STYLE,
  DARK_THEME,
} from '../../usa/common/chartConstants'

import type { GlobalEpuData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface EpuChartProps {
  data: GlobalEpuData | null
}

type EpuViewMode = 'global' | 'us_monthly'

const VIEW_MODE_OPTIONS: { mode: EpuViewMode; label: string }[] = [
  { mode: 'global', label: 'グローバル（月次）' },
  { mode: 'us_monthly', label: '米国（月次）' },
]

interface EpuItem {
  date: string
  value: number | null
}

// カラー設定
const COLOR_GLOBAL = '#722ed1'
const COLOR_US_MONTHLY = '#1890ff'
const COLOR_US_DAILY = '#1890ff'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

// =============================================================================
// 日次データを月次データにマージするユーティリティ
// =============================================================================

interface MergedEpuItem {
  date: string
  value: number | null
  daily_value: number | null
}

function mergeMonthlyAndDaily(
  monthly: EpuItem[],
  daily: EpuItem[],
): MergedEpuItem[] {
  // 月次データの日付範囲を取得
  if (monthly.length === 0) return []

  const firstMonthlyDate = monthly[0].date
  const lastMonthlyDate = monthly[monthly.length - 1].date

  // 日次データを日付キーにしたマップ
  const dailyMap = new Map<string, number>()
  for (const d of daily) {
    if (d.value != null && d.date >= firstMonthlyDate) {
      dailyMap.set(d.date, d.value)
    }
  }

  // 全日付を収集（月次 + 日次）
  const allDates = new Set<string>()
  for (const m of monthly) allDates.add(m.date)
  for (const date of dailyMap.keys()) {
    if (date <= lastMonthlyDate || date > lastMonthlyDate) {
      allDates.add(date)
    }
  }

  // 月次データをマップに
  const monthlyMap = new Map<string, number>()
  for (const m of monthly) {
    if (m.value != null) monthlyMap.set(m.date, m.value)
  }

  // ソートされた全日付で結果を構築
  const sortedDates = Array.from(allDates).sort()
  const result: MergedEpuItem[] = []

  for (const date of sortedDates) {
    result.push({
      date,
      value: monthlyMap.get(date) ?? null,
      daily_value: dailyMap.get(date) ?? null,
    })
  }

  return result
}

// =============================================================================
// カスタムTooltip
// =============================================================================

interface TooltipPayloadItem {
  color: string
  name: string
  value: number
  dataKey: string
}

function EpuTooltip({ active, payload, label }: {
  active?: boolean
  payload?: TooltipPayloadItem[]
  label?: string
}) {
  if (!active || !payload || payload.length === 0) return null

  // daily_value がnullのエントリは除外
  const validPayload = payload.filter(item => item.value != null)
  if (validPayload.length === 0) return null

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
        {formatDateLabel(label || '')}
      </div>
      {validPayload.map((item, index) => (
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
                opacity: item.dataKey === 'daily_value' ? 0.4 : 1,
              }}
            />
            {item.name}
          </span>
          <span style={{ fontWeight: 500, color: item.color, opacity: item.dataKey === 'daily_value' ? 0.7 : 1 }}>
            {item.value.toFixed(1)}
          </span>
        </div>
      ))}
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function EpuChart({ data }: EpuChartProps) {
  const [viewMode, setViewMode] = useState<EpuViewMode>('global')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)

  // US Monthly データ（個別API）
  const [usMonthlyData, setUsMonthlyData] = useState<EpuItem[] | null>(null)
  const [usMonthlyLatest, setUsMonthlyLatest] = useState<EpuItem | null>(null)
  const [usMonthlyLoading, setUsMonthlyLoading] = useState(false)

  // US Daily データ（個別API, 背景用）
  const [usDailyData, setUsDailyData] = useState<EpuItem[] | null>(null)
  const [usDailyLoading, setUsDailyLoading] = useState(false)

  const fetchUsMonthlyData = useCallback(async () => {
    setUsMonthlyLoading(true)
    try {
      const resp = await fetch(`${API_BASE_URL}/api/global/epu?series=us_monthly`)
      if (!resp.ok) throw new Error('Failed to fetch US monthly EPU')
      const json = await resp.json()
      setUsMonthlyData(json.data ?? [])
      setUsMonthlyLatest(json.latest ?? null)
    } catch (err) {
      console.error('Failed to fetch US monthly EPU:', err)
      setUsMonthlyData([])
    } finally {
      setUsMonthlyLoading(false)
    }
  }, [])

  const fetchUsDailyData = useCallback(async () => {
    setUsDailyLoading(true)
    try {
      const resp = await fetch(`${API_BASE_URL}/api/global/epu?series=us_daily`)
      if (!resp.ok) throw new Error('Failed to fetch US daily EPU')
      const json = await resp.json()
      setUsDailyData(json.data ?? [])
    } catch (err) {
      console.error('Failed to fetch US daily EPU:', err)
      setUsDailyData([])
    } finally {
      setUsDailyLoading(false)
    }
  }, [])

  // 米国モードに切り替わったらデータ取得
  useEffect(() => {
    if (viewMode === 'us_monthly') {
      if (usMonthlyData === null) fetchUsMonthlyData()
      if (usDailyData === null) fetchUsDailyData()
    }
  }, [viewMode, usMonthlyData, usDailyData, fetchUsMonthlyData, fetchUsDailyData])

  // Global データ（ダッシュボードから）
  const globalSorted = useSortedData(data?.data ?? [])
  const globalFiltered = usePeriodFiltering(globalSorted, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  // US Monthly データのソート
  const usMonthSorted = useSortedData(usMonthlyData ?? [])

  // US Daily データのソート
  const usDailySorted = useSortedData(usDailyData ?? [])

  // US Monthly + Daily マージデータ（期間フィルタリングはマージ後に適用）
  const usMergedData = useMemo(() => {
    if (usMonthSorted.length === 0 && usDailySorted.length === 0) return []
    return mergeMonthlyAndDaily(usMonthSorted, usDailySorted)
  }, [usMonthSorted, usDailySorted])

  const usMergedFiltered = usePeriodFiltering(usMergedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  // 表示中のデータ
  const isGlobal = viewMode === 'global'

  const activeLatest = useMemo(() => {
    if (isGlobal) {
      return globalSorted.length > 0 ? globalSorted[globalSorted.length - 1] : null
    }
    return usMonthlyLatest
  }, [isGlobal, globalSorted, usMonthlyLatest])

  const hasData = isGlobal
    ? globalSorted.length > 0
    : (usMonthlyData !== null && usMonthSorted.length > 0)
  const isLoading = isGlobal
    ? data === null
    : (usMonthlyLoading || usDailyLoading)

  // ローディング
  if (isLoading && !hasData) {
    return <LoadingChart title="経済政策不確実性指数（EPU）" />
  }

  return (
    <div id="epu">
      <ChartContainer
        title="経済政策不確実性指数（EPU）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="Economic Policy Uncertainty"
        sourceUrl="https://www.policyuncertainty.com/index.html"
      >
        {/* 最新値 */}
        {activeLatest && (
          <SimpleLatestValueBox
            label={isGlobal ? 'Global EPU' : 'US EPU'}
            value={activeLatest.value}
            valueColor={isGlobal ? COLOR_GLOBAL : COLOR_US_MONTHLY}
            date={activeLatest.date}
            decimals={1}
          />
        )}

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
              onClick={() => window.open('/compare?s=global_epu', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 期間選択 */}
        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

        {/* チャート */}
        {!hasData ? (
          <NoDataMessage />
        ) : isGlobal ? (
          <StandardLineChart
            data={globalFiltered}
            lines={[
              { dataKey: 'value', color: COLOR_GLOBAL, name: 'Global EPU' },
            ]}
            yAxisFormatter={(v) => `${v.toFixed(0)}`}
            tooltipValueFormatter={(v) => v != null ? `${v.toFixed(1)}` : 'N/A'}
            yDomain={['dataMin - 10', 'dataMax + 10']}
            showZeroLine={false}
          />
        ) : (
          /* US Monthly + Daily 背景 */
          <ResponsiveContainer width="100%" height={450}>
            <ComposedChart data={usMergedFiltered} margin={CHART_MARGIN}>
              <CartesianGrid {...CARTESIAN_GRID_PROPS} />
              <XAxis
                dataKey="date"
                tickFormatter={formatDateLabel}
                tick={AXIS_STYLE.tick}
                interval={AXIS_STYLE.interval}
              />
              <YAxis
                domain={['dataMin - 10', 'dataMax + 10']}
                tick={AXIS_STYLE.tick}
                tickFormatter={(v: number) => `${v.toFixed(0)}`}
              />
              <RechartsTooltip content={<EpuTooltip />} />
              <Legend />
              {/* 日次データを薄く背景に表示 */}
              <Area
                type="monotone"
                dataKey="daily_value"
                fill={COLOR_US_DAILY}
                fillOpacity={0.1}
                stroke={COLOR_US_DAILY}
                strokeWidth={0.5}
                strokeOpacity={0.25}
                name="US Daily EPU"
                dot={false}
                isAnimationActive={false}
                connectNulls={false}
              />
              {/* 月次データをメインラインで表示 */}
              <Line
                type="monotone"
                dataKey="value"
                stroke={COLOR_US_MONTHLY}
                strokeWidth={2}
                name="US Monthly EPU"
                dot={false}
                isAnimationActive={false}
                connectNulls={true}
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </ChartContainer>
    </div>
  )
}
