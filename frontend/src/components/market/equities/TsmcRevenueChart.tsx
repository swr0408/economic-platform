/**
 * TSMC月次売上高チャートコンポーネント
 *
 * データ項目:
 * - revenue: 月次売上高（百万台湾ドル）
 * - yoy: 前年同月比(%)
 * - mom: 前月比(%)
 * - quarterly: 四半期合計（Q1=1-3月, Q2=4-6月, Q3=7-9月, Q4=10-12月）
 *
 * ビューモード:
 * - raw: 原数値（棒グラフ + TSMC ADR折れ線オーバーレイ）
 * - quarterly: 四半期合計（棒グラフ + TSMC ADR折れ線オーバーレイ）
 * - yoy: 前年同月比（折れ線グラフ + TSMC ADR折れ線オーバーレイ）
 * - mom: 前月比（棒グラフ / ヒートマップ）
 *
 * データソース: TSMC / TWSE MOPS
 *
 * FMPマッピング: なし
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../common/ChartContainer'
import LoadingChart from '../../common/LoadingChart'
import PeriodSelector from '../../common/PeriodSelector'

import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../../country/usa/common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMonthlyTableData,
  useHiddenSeries,
} from '../../country/usa/common/useChartData'
import {
  NoDataMessage,
  ViewModeButtonGroup,
  StandardLineChart,
  StandardBarChart,
} from '../../country/usa/common/ChartComponents'
import { MonthlyTable } from '../../country/usa/common/MonthlyTable'

import { useTsmcRevenueData, useMarketSymbolData } from '../../../hooks/useMarketData'

// =============================================================================
// 型定義・定数
// =============================================================================

type ViewMode = 'raw' | 'quarterly' | 'yoy' | 'mom'
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'raw', label: '月次' },
  { mode: 'mom', label: '前月比' },
  { mode: 'yoy', label: '前年比' },
  { mode: 'quarterly', label: '四半期' },
]

type DisplayMode = 'chart' | 'heatmap_revenue' | 'heatmap_adr'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap_revenue', label: '売上高ヒートマップ' },
  { mode: 'heatmap_adr', label: 'TSMC株価ヒートマップ' },
]

const COLOR_REVENUE = '#10b981'  // Emerald
const COLOR_YOY = '#3b82f6'     // Blue
const COLOR_MOM = '#f59e0b'     // Amber
const COLOR_TSMC_ADR = '#ef4444' // Red

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

interface MergedMonthlyItem {
  date: string
  revenue: number
  yoy: number | null
  mom: number | null
  tsmc_adr: number | null
  [key: string]: unknown
}

interface MergedQuarterlyItem {
  date: string
  quarter_label: string
  revenue: number
  yoy: number | null
  qoq: number | null
  tsmc_adr: number | null
  [key: string]: unknown
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function TsmcRevenueChart() {
  const { data: apiData, isLoading } = useTsmcRevenueData()
  const { data: tsmcAdrData } = useMarketSymbolData('tsmc')
  const [viewMode, setViewMode] = useState<ViewMode>('raw')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<string>()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    raw: 10,
    quarterly: 10,
    yoy: 10,
    mom: 3,
  })

  // TSMC ADR日足を月末終値に変換（月次/四半期マージ用）
  const adrMonthlyMap = useMemo(() => {
    const map = new Map<string, number>()
    if (!tsmcAdrData?.data) return map
    for (const d of tsmcAdrData.data) {
      // 各日付から YYYY-MM を抽出し、月末日の値で上書き（最後の値が残る）
      const [y, m] = d.date.split('-')
      const key = `${y}-${m}-01`
      map.set(key, d.close)
    }
    return map
  }, [tsmcAdrData])

  // 四半期末のTSMC ADR価格マップ
  const adrQuarterlyMap = useMemo(() => {
    const map = new Map<string, number>()
    if (!tsmcAdrData?.data) return map
    // 四半期末月: 03, 06, 09, 12
    const quarterEndMonths = new Set(['03', '06', '09', '12'])
    for (const d of tsmcAdrData.data) {
      const [y, m] = d.date.split('-')
      if (quarterEndMonths.has(m)) {
        const key = `${y}-${m}-01`
        map.set(key, d.close)
      }
    }
    return map
  }, [tsmcAdrData])

  // 月次データ（TSMC ADRマージ）
  const monthlyData = useMemo<MergedMonthlyItem[]>(() => {
    if (!apiData?.data) return []
    return apiData.data.map(item => ({
      ...item,
      tsmc_adr: adrMonthlyMap.get(item.date) ?? null,
    }))
  }, [apiData, adrMonthlyMap])

  // 四半期データ（TSMC ADRマージ）
  const quarterlyData = useMemo<MergedQuarterlyItem[]>(() => {
    if (!apiData?.quarterly) return []
    return apiData.quarterly.map(item => ({
      ...item,
      tsmc_adr: adrQuarterlyMap.get(item.date) ?? null,
    }))
  }, [apiData, adrQuarterlyMap])

  const sortedMonthly = useSortedData(monthlyData)
  const sortedQuarterly = useSortedData(quarterlyData)

  const filteredMonthly = usePeriodFiltering(sortedMonthly, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })
  const filteredQuarterly = usePeriodFiltering(sortedQuarterly, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // 売上高前月比ヒートマップ用データ
  const momTableData = useMonthlyTableData(
    sortedMonthly,
    (item: MergedMonthlyItem) => item.mom,
    10
  )

  // TSMC ADR株価の月次前月比を計算
  const adrMomData = useMemo(() => {
    // adrMonthlyMap を日付順のリストに変換し前月比を計算
    const entries = Array.from(adrMonthlyMap.entries()).sort(([a], [b]) => a.localeCompare(b))
    const result: { date: string; mom: number | null }[] = []
    for (let i = 0; i < entries.length; i++) {
      const [date, close] = entries[i]
      let mom: number | null = null
      if (i > 0) {
        const prevClose = entries[i - 1][1]
        if (prevClose > 0) {
          mom = Math.round(((close - prevClose) / prevClose) * 1000) / 10
        }
      }
      result.push({ date, mom })
    }
    return result
  }, [adrMonthlyMap])

  // TSMC ADR株価ヒートマップ用データ
  const adrMomTableData = useMonthlyTableData(
    adrMomData,
    (item: { date: string; mom: number | null }) => item.mom,
    10
  )

  const hasData = sortedMonthly.length > 0

  // ローディング
  if (isLoading) {
    return (
      <div id="tsmc-revenue">
        <LoadingChart title="TSMC売上高" />
      </div>
    )
  }

  if (!hasData) {
    return (
      <div id="tsmc-revenue">
        <ChartContainer title="TSMC売上高" showPeriodSelector={false} showDataSource={false}>
          <NoDataMessage />
        </ChartContainer>
      </div>
    )
  }

  const latest = apiData?.latest
  const latestQ = apiData?.latest_quarterly
  const nextRelease = apiData?.next_release

  return (
    <div id="tsmc-revenue">
      <ChartContainer
        title="TSMC売上高"
        showPeriodSelector={false}
        dataSource="TSMC / TWSE MOPS"
        sourceUrl="https://investor.tsmc.com/english/monthly-revenue"
      >
        {/* 最新値ボックス */}
        <div style={{ ...LATEST_VALUE_BOX_STYLE, justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {viewMode === 'quarterly' ? (
              <>
                {latestQ?.quarter_label && (
                  <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                    {latestQ.quarter_label}
                  </span>
                )}
                <_LatestItem
                  label="四半期"
                  value={latestQ?.revenue != null ? `${latestQ.revenue.toLocaleString()} 百万TWD` : '—'}
                  color={COLOR_REVENUE}
                />
                <_LatestItem
                  label="YoY"
                  value={latestQ?.yoy != null ? `${latestQ.yoy >= 0 ? '+' : ''}${latestQ.yoy.toFixed(1)}%` : '—'}
                  color={COLOR_YOY}
                />
                <_LatestItem
                  label="QoQ"
                  value={latestQ?.qoq != null ? `${latestQ.qoq >= 0 ? '+' : ''}${latestQ.qoq.toFixed(1)}%` : '—'}
                  color={COLOR_MOM}
                />
              </>
            ) : (
              <>
                {latest?.date && (
                  <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                    {formatDateFull(latest.date)}
                  </span>
                )}
                <_LatestItem
                  label="売上高"
                  value={latest?.revenue != null ? `${latest.revenue.toLocaleString()} 百万TWD` : '—'}
                  color={COLOR_REVENUE}
                />
                <_LatestItem
                  label="YoY"
                  value={latest?.yoy != null ? `${latest.yoy >= 0 ? '+' : ''}${latest.yoy.toFixed(1)}%` : '—'}
                  color={COLOR_YOY}
                />
                <_LatestItem
                  label="MoM"
                  value={latest?.mom != null ? `${latest.mom >= 0 ? '+' : ''}${latest.mom.toFixed(1)}%` : '—'}
                  color={COLOR_MOM}
                />
              </>
            )}
          </div>
          {nextRelease && (
            <span style={{ fontSize: 11, color: TEXT_COLORS.secondary }}>
              次回: {nextRelease.date}
            </span>
          )}
        </div>

        {/* ViewMode + データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=tsmc_revenue', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* ===== 月次原数値（棒グラフ + TSMC ADR折れ線） ===== */}
        {viewMode === 'raw' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardLineChart
              data={filteredMonthly}
              lines={[
                { dataKey: 'revenue', color: COLOR_REVENUE, name: 'TSMC売上高(L)', hide: hiddenSeries.has('revenue'), strokeWidth: 2 },
                { dataKey: 'tsmc_adr', color: COLOR_TSMC_ADR, name: 'TSMC ADR(R)', yAxisId: 'right', hide: hiddenSeries.has('tsmc_adr'), strokeDasharray: '6 3' },
              ]}
              xAxisFormatter={formatDateLabel}
              yAxisFormatter={(v: number) => `${(v / 1000).toFixed(0)}B`}
              rightYAxisFormatter={(v: number) => `$${v.toFixed(0)}`}
              tooltipLabelFormatter={formatDateFull}
              tooltipValueFormatter={(v: number, dataKey: string) => {
                if (v == null) return 'N/A'
                if (dataKey === 'tsmc_adr') return `$${v.toFixed(2)}`
                return `${v.toLocaleString()} 百万TWD`
              }}
              yDomain={['dataMin * 0.9', 'dataMax * 1.05']}
              rightYDomain={['dataMin * 0.8', 'dataMax * 1.1']}
              showZeroLine={false}
              onLegendClick={handleLegendClick}
            />
          </>
        )}

        {/* ===== 四半期合計（棒グラフ + TSMC ADR折れ線） ===== */}
        {viewMode === 'quarterly' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardLineChart
              data={filteredQuarterly}
              lines={[
                { dataKey: 'revenue', color: COLOR_REVENUE, name: 'TSMC四半期売上高(L)', hide: hiddenSeries.has('revenue'), strokeWidth: 2 },
                { dataKey: 'tsmc_adr', color: COLOR_TSMC_ADR, name: 'TSMC ADR(R)', yAxisId: 'right', hide: hiddenSeries.has('tsmc_adr'), strokeDasharray: '6 3' },
              ]}
              xAxisFormatter={(dateStr: string) => {
                // date (YYYY-MM-01) → quarter label
                if (!dateStr) return ''
                const [y, m] = dateStr.split('-')
                const q = Math.ceil(parseInt(m) / 3)
                return `${y} Q${q}`
              }}
              yAxisFormatter={(v: number) => `${(v / 1000).toFixed(0)}B`}
              rightYAxisFormatter={(v: number) => `$${v.toFixed(0)}`}
              tooltipLabelFormatter={(dateStr: string) => {
                if (!dateStr) return ''
                const [y, m] = dateStr.split('-')
                const q = Math.ceil(parseInt(m) / 3)
                return `${y}年 Q${q}`
              }}
              tooltipValueFormatter={(v: number, dataKey: string) => {
                if (v == null) return 'N/A'
                if (dataKey === 'tsmc_adr') return `$${v.toFixed(2)}`
                return `${v.toLocaleString()} 百万TWD`
              }}
              yDomain={['dataMin * 0.9', 'dataMax * 1.05']}
              rightYDomain={['dataMin * 0.8', 'dataMax * 1.1']}
              showZeroLine={false}
              onLegendClick={handleLegendClick}
            />
          </>
        )}

        {/* ===== 前年比（折れ線 + TSMC ADR折れ線） ===== */}
        {viewMode === 'yoy' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardLineChart
              data={filteredMonthly}
              lines={[
                { dataKey: 'yoy', color: COLOR_YOY, name: 'TSMC売上高 YoY(L)', hide: hiddenSeries.has('yoy') },
                { dataKey: 'tsmc_adr', color: COLOR_TSMC_ADR, name: 'TSMC ADR(R)', yAxisId: 'right', hide: hiddenSeries.has('tsmc_adr'), strokeDasharray: '6 3' },
              ]}
              xAxisFormatter={formatDateLabel}
              yAxisFormatter={(v: number) => `${v.toFixed(0)}%`}
              rightYAxisFormatter={(v: number) => `$${v.toFixed(0)}`}
              tooltipLabelFormatter={formatDateFull}
              tooltipValueFormatter={(v: number, dataKey: string) => {
                if (v == null) return 'N/A'
                if (dataKey === 'tsmc_adr') return `$${v.toFixed(2)}`
                return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
              }}
              yDomain={['dataMin - 5', 'dataMax + 5']}
              rightYDomain={['dataMin * 0.8', 'dataMax * 1.1']}
              showZeroLine={true}
              onLegendClick={handleLegendClick}
            />
          </>
        )}

        {/* ===== 前月比 ===== */}
        {viewMode === 'mom' && (
          <>
            {/* 売上高前月比: チャート/ヒートマップ切替 */}
            <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />

            {displayMode === 'chart' && (
              <>
                <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                <StandardBarChart
                  data={filteredMonthly}
                  bars={[
                    { dataKey: 'mom', color: COLOR_MOM, name: 'TSMC売上高（前月比）' },
                  ]}
                  xAxisFormatter={formatDateLabel}
                  yAxisFormatter={(v: number) => `${v.toFixed(0)}%`}
                  tooltipLabelFormatter={formatDateFull}
                  tooltipValueFormatter={(v: number) => v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(1)}%` : 'N/A'}
                  yDomain={['dataMin - 5', 'dataMax + 5']}
                />
              </>
            )}

            {displayMode === 'heatmap_revenue' && (
              <MonthlyTable
                data={momTableData}
                decimals={1}
              />
            )}

            {displayMode === 'heatmap_adr' && (
              <MonthlyTable
                data={adrMomTableData}
                decimals={1}
              />
            )}
          </>
        )}
      </ChartContainer>
    </div>
  )
}

// =============================================================================
// サブコンポーネント
// =============================================================================

function _LatestItem({
  label,
  value,
  color,
}: {
  label: string
  value: string
  color: string
}) {
  return (
    <span
      style={{
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
        {value}
      </span>
    </span>
  )
}
