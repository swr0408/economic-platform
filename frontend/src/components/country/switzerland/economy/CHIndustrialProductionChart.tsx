/**
 * スイス鉱工業生産チャートコンポーネント
 *
 * BFSから鉱工業生産データを取得し、月次・四半期の各系列を表示
 *
 * データ:
 * - 月次: MoM（前月比）、YoY（前年比）
 * - 四半期: QoQ（前期比）、YoY（前年比）
 *
 * データソース:
 * - BFS (Federal Statistical Office / Bundesamt für Statistik)
 *
 * 発表スケジュール:
 * - 四半期ごと（FMPから次回発表日時取得）
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  usePeriodFiltering,
  useViewModePeriodManagement,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
  StandardBarChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import { DARK_THEME, TEXT_COLORS, QUARTER_NAMES, MONTH_NAMES } from '../../usa/common/chartConstants'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { CHIndustrialProductionData } from '../../../../hooks/useDashboardData'

interface CHIndustrialProductionChartProps {
  data: CHIndustrialProductionData | null
}

// グラフの色
const COLORS = {
  mom: '#DC143C', // スイス赤（前月比）
  yoy: '#1890ff', // 青（前年比）
  qoq: '#52c41a', // 緑（前期比）
  qyoy: '#722ed1', // 紫（四半期前年比）
}

type ViewMode = 'mom' | 'mom_table' | 'yoy' | 'qoq' | 'qoq_table' | 'qyoy'

// 月次日付フォーマッター（2025-01-01 → 2025/01）
const formatMonthLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}/${month}`
}

// 四半期日付フォーマッター（2025-01-01 → 2025/Q1）
const formatQuarterLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  const monthNum = parseInt(month, 10)
  const quarter = Math.ceil(monthNum / 3)
  return `${year}/Q${quarter}`
}

// 日付から年を抽出
const getYearFromDate = (dateStr: string): number => {
  return parseInt(dateStr.split('-')[0], 10)
}

// 日付から月を抽出（0-indexed）
const getMonthFromDate = (dateStr: string): number => {
  return parseInt(dateStr.split('-')[1], 10) - 1
}

// 日付から四半期を抽出（0-indexed）
const getQuarterFromDate = (dateStr: string): number => {
  const month = parseInt(dateStr.split('-')[1], 10)
  return Math.floor((month - 1) / 3)
}

export default function CHIndustrialProductionChart({ data }: CHIndustrialProductionChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    mom: 'default',
    mom_table: 'default',
    yoy: 'default',
    qoq: 'default',
    qoq_table: 'default',
    qyoy: 'default',
  })

  // 月次データ変換
  const monthlyChartData = useMemo(() => {
    if (!data?.monthly_data) return []
    return data.monthly_data.map((item) => ({
      date: item.date,
      mom: item.mom ?? 0,
      yoy: item.yoy ?? 0,
    })).sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // 四半期データ変換
  const quarterlyChartData = useMemo(() => {
    if (!data?.quarterly_data) return []
    return data.quarterly_data.map((item) => ({
      date: item.date,
      qoq: item.qoq ?? 0,
      yoy: item.yoy ?? 0,
    })).sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // 現在のビューモードに応じたデータを選択
  const isQuarterly = viewMode.startsWith('q')

  // 期間フィルタリング（月次用）
  const filteredMonthlyData = usePeriodFiltering(monthlyChartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // 期間フィルタリング（四半期用）
  const filteredQuarterlyData = usePeriodFiltering(quarterlyChartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ（月次：年別×月のマトリックス）
  const monthlyTableData = useMemo(() => {
    if (!monthlyChartData.length) return { years: [] as number[], monthlyData: {} as Record<number, Record<number, number | null>> }

    const years = new Set<number>()
    const monthlyData: Record<number, Record<number, number | null>> = {}
    const dataKey = viewMode === 'mom_table' ? 'mom' : 'yoy'

    monthlyChartData.forEach(item => {
      const year = getYearFromDate(item.date)
      const month = getMonthFromDate(item.date)

      if (year > 0) {
        years.add(year)
        if (!monthlyData[year]) {
          monthlyData[year] = {}
        }
        monthlyData[year][month] = dataKey === 'mom' ? item.mom : item.yoy
      }
    })

    const sortedYears = Array.from(years).sort((a, b) => b - a).slice(0, 10).reverse()
    return { years: sortedYears, monthlyData }
  }, [monthlyChartData, viewMode])

  // テーブル用データ（四半期：年別×四半期のマトリックス）
  const quarterlyTableData = useMemo(() => {
    if (!quarterlyChartData.length) return { years: [] as number[], quarterlyData: {} as Record<number, Record<number, number | null>> }

    const years = new Set<number>()
    const quarterlyData: Record<number, Record<number, number | null>> = {}

    quarterlyChartData.forEach(item => {
      const year = getYearFromDate(item.date)
      const quarter = getQuarterFromDate(item.date)

      if (year > 0) {
        years.add(year)
        if (!quarterlyData[year]) {
          quarterlyData[year] = {}
        }
        quarterlyData[year][quarter] = item.qoq
      }
    })

    const sortedYears = Array.from(years).sort((a, b) => b - a).slice(0, 10).reverse()
    return { years: sortedYears, quarterlyData }
  }, [quarterlyChartData])

  const hasData = monthlyChartData.length > 0 || quarterlyChartData.length > 0

  // 最新値を取得
  const latestMonthly = data?.latest_monthly
  const latestQuarterly = data?.latest_quarterly

  // 現在表示中の値を取得
  const currentValue = useMemo(() => {
    if (viewMode === 'mom' || viewMode === 'mom_table') return latestMonthly?.mom ?? null
    if (viewMode === 'yoy') return latestMonthly?.yoy ?? null
    if (viewMode === 'qoq' || viewMode === 'qoq_table') return latestQuarterly?.qoq ?? null
    if (viewMode === 'qyoy') return latestQuarterly?.yoy ?? null
    return null
  }, [latestMonthly, latestQuarterly, viewMode])

  // 現在の日付を取得
  const currentDate = useMemo(() => {
    if (viewMode === 'mom' || viewMode === 'mom_table' || viewMode === 'yoy') {
      return latestMonthly?.date ?? null
    }
    return latestQuarterly?.date ?? null
  }, [latestMonthly, latestQuarterly, viewMode])

  // 現在の色を取得
  const currentColor = useMemo(() => {
    if (viewMode === 'mom' || viewMode === 'mom_table') return COLORS.mom
    if (viewMode === 'yoy') return COLORS.yoy
    if (viewMode === 'qoq' || viewMode === 'qoq_table') return COLORS.qoq
    if (viewMode === 'qyoy') return COLORS.qyoy
    return COLORS.yoy
  }, [viewMode])

  if (data === null) {
    return <LoadingChart title="鉱工業生産" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="鉱工業生産" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // テーブルセルの背景色を決定
  const getCellColor = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'transparent'
    if (value > 2) return 'rgba(16, 185, 129, 0.55)'
    if (value > 0) return 'rgba(16, 185, 129, 0.25)'
    if (value < -2) return 'rgba(239, 68, 68, 0.55)'
    if (value < 0) return 'rgba(239, 68, 68, 0.25)'
    return 'transparent'
  }

  // 月次テーブルコンポーネント
  const MonthlyTable = () => (
    <div style={{ overflowX: 'auto' }}>
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: 12,
          textAlign: 'center',
          color: DARK_THEME.textPrimary,
        }}
      >
        <thead>
          <tr style={{ backgroundColor: DARK_THEME.bgTertiary }}>
            <th style={{ padding: '8px 4px', borderBottom: `2px solid ${DARK_THEME.borderLight}`, fontWeight: 'bold' }}>
              年
            </th>
            {MONTH_NAMES.map((month, idx) => (
              <th
                key={idx}
                style={{
                  padding: '8px 4px',
                  borderBottom: `2px solid ${DARK_THEME.borderLight}`,
                  fontWeight: 'bold',
                  minWidth: 45,
                }}
              >
                {month}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {monthlyTableData.years.map((year: number) => (
            <tr key={year}>
              <td
                style={{
                  padding: '6px 4px',
                  borderBottom: `1px solid ${DARK_THEME.border}`,
                  fontWeight: 'bold',
                  backgroundColor: DARK_THEME.bgTertiary,
                }}
              >
                {year}
              </td>
              {Array.from({ length: 12 }, (_, month) => {
                const value = monthlyTableData.monthlyData[year]?.[month]
                return (
                  <td
                    key={month}
                    style={{
                      padding: '6px 4px',
                      borderBottom: `1px solid ${DARK_THEME.border}`,
                      backgroundColor: getCellColor(value),
                    }}
                  >
                    {value !== null && value !== undefined ? (
                      <span style={{ color: value >= 0 ? TEXT_COLORS.positive : TEXT_COLORS.negative }}>
                        {value >= 0 ? '+' : ''}{value.toFixed(1)}
                      </span>
                    ) : (
                      <span style={{ color: TEXT_COLORS.quaternary }}>-</span>
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )

  // 四半期テーブルコンポーネント
  const QuarterlyTable = () => (
    <div style={{ overflowX: 'auto' }}>
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: 13,
          textAlign: 'center',
          color: DARK_THEME.textPrimary,
        }}
      >
        <thead>
          <tr style={{ backgroundColor: DARK_THEME.bgTertiary }}>
            <th style={{ padding: '10px 8px', borderBottom: `2px solid ${DARK_THEME.borderLight}`, fontWeight: 'bold' }}>
              年
            </th>
            {QUARTER_NAMES.map((quarter, idx) => (
              <th
                key={idx}
                style={{
                  padding: '10px 8px',
                  borderBottom: `2px solid ${DARK_THEME.borderLight}`,
                  fontWeight: 'bold',
                  minWidth: 80,
                }}
              >
                {quarter}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {quarterlyTableData.years.map((year: number) => (
            <tr key={year}>
              <td
                style={{
                  padding: '8px',
                  borderBottom: `1px solid ${DARK_THEME.border}`,
                  fontWeight: 'bold',
                  backgroundColor: DARK_THEME.bgTertiary,
                }}
              >
                {year}
              </td>
              {Array.from({ length: 4 }, (_, quarter) => {
                const value = quarterlyTableData.quarterlyData[year]?.[quarter]
                return (
                  <td
                    key={quarter}
                    style={{
                      padding: '8px',
                      borderBottom: `1px solid ${DARK_THEME.border}`,
                      backgroundColor: getCellColor(value),
                    }}
                  >
                    {value !== null && value !== undefined ? (
                      <span style={{ color: value >= 0 ? TEXT_COLORS.positive : TEXT_COLORS.negative }}>
                        {value >= 0 ? '+' : ''}{value.toFixed(2)}
                      </span>
                    ) : (
                      <span style={{ color: TEXT_COLORS.quaternary }}>-</span>
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )

  // データ比較用のoverlayConfig ID
  const getCompareId = () => {
    if (viewMode === 'mom' || viewMode === 'mom_table') return 'ch_industrial_production_mom'
    if (viewMode === 'yoy') return 'ch_industrial_production_yoy'
    if (viewMode === 'qoq' || viewMode === 'qoq_table') return 'ch_industrial_production_qoq'
    if (viewMode === 'qyoy') return 'ch_industrial_production_qyoy'
    return 'ch_industrial_production_yoy'
  }

  const getChartTitle = () => {
    if (viewMode === 'mom' || viewMode === 'mom_table') return '鉱工業生産（前月比）'
    if (viewMode === 'yoy') return '鉱工業生産（前年比）'
    if (viewMode === 'qoq' || viewMode === 'qoq_table') return '鉱工業生産（四半期・前期比）'
    if (viewMode === 'qyoy') return '鉱工業生産（四半期・前年比）'
    return '鉱工業生産'
  }

  const dateFormatter = isQuarterly ? formatQuarterLabel : formatMonthLabel
  const isTableMode = viewMode.endsWith('_table')

  return (
    <div id="ch-industrial-production-chart">
      <ChartContainer
        title="鉱工業生産"
        showPeriodSelector={false}
        dataSource="BFS (Federal Statistical Office)"
        sourceUrl="https://www.bfs.admin.ch/bfs/de/home/statistiken/industrie-dienstleistungen/produktion-auftraege-umsatz.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={getChartTitle()}
          value={currentValue}
          date={currentDate ?? undefined}
          format="percent"
          decimals={2}
          valueColor={currentColor}
          nextRelease={data.next_release}
          dateFormatter={dateFormatter}
        />

        {/* タブ切替 */}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* ビューモード切替 */}
                  <ViewModeButtonGroup
                    currentMode={viewMode}
                    onChange={(mode) => setViewMode(mode as ViewMode)}
                    options={[
                      { mode: 'qoq', label: '四半期動向前期比' },
                      { mode: 'qoq_table', label: '四半期動向前期比（テーブル）' },
                      { mode: 'qyoy', label: '四半期動向前年比' },
                      { mode: 'mom', label: '月次動向前月比' },
                      { mode: 'mom_table', label: '月次動向前月比（テーブル）' },
                      { mode: 'yoy', label: '月次動向前年比' },
                    ]}
                  />

                  {/* 期間セレクター（テーブル以外で表示） */}
                  {!isTableMode && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <Tooltip title="比較ページを開く">
                        <Button
                          icon={<AreaChartOutlined />}
                          onClick={() => window.open(`/compare?s=${getCompareId()}`, '_blank')}
                        >
                          データ比較
                        </Button>
                      </Tooltip>
                    </div>
                  )}

                  {/* コンテンツ表示 */}
                  {viewMode === 'mom_table' && <MonthlyTable />}
                  {viewMode === 'qoq_table' && <QuarterlyTable />}

                  {viewMode === 'mom' && (
                    <StandardBarChart
                      data={filteredMonthlyData}
                      bars={[
                        { dataKey: 'mom', color: COLORS.mom, name: '鉱工業生産（月次動向前月比）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      xAxisFormatter={formatMonthLabel}
                    />
                  )}

                  {viewMode === 'yoy' && (
                    <StandardLineChart
                      data={filteredMonthlyData}
                      lines={[
                        { dataKey: 'yoy', color: COLORS.yoy, name: '鉱工業生産（月次動向前年比）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                      yDomain={['dataMin - 2', 'dataMax + 2']}
                      showZeroLine={true}
                      xAxisFormatter={formatMonthLabel}
                    />
                  )}

                  {viewMode === 'qoq' && (
                    <StandardBarChart
                      data={filteredQuarterlyData}
                      bars={[
                        { dataKey: 'qoq', color: COLORS.qoq, name: '鉱工業生産（四半期動向前期比）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      xAxisFormatter={formatQuarterLabel}
                    />
                  )}

                  {viewMode === 'qyoy' && (
                    <StandardLineChart
                      data={filteredQuarterlyData}
                      lines={[
                        { dataKey: 'yoy', color: COLORS.qyoy, name: '鉱工業生産（四半期動向前年比）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                      yDomain={['dataMin - 2', 'dataMax + 2']}
                      showZeroLine={true}
                      xAxisFormatter={formatQuarterLabel}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ch_industrial_production" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
