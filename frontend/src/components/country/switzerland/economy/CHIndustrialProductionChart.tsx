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

// データ種別
type DataKind = 'mom' | 'yoy' | 'qoq' | 'qyoy'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'qoq', label: '四半期動向前期比' },
  { mode: 'qyoy', label: '四半期動向前年比' },
  { mode: 'mom', label: '月次動向前月比' },
  { mode: 'yoy', label: '月次動向前年比' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS_IP: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

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
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    mom: 10,
    yoy: 10,
    qoq: 10,
    qyoy: 10,
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

  // 現在のデータ種別に応じたデータを選択
  const isQuarterly = dataKind === 'qoq' || dataKind === 'qyoy'

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
    const dataKey = 'mom'

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
  }, [monthlyChartData])

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
    if (dataKind === 'mom') return latestMonthly?.mom ?? null
    if (dataKind === 'yoy') return latestMonthly?.yoy ?? null
    if (dataKind === 'qoq') return latestQuarterly?.qoq ?? null
    if (dataKind === 'qyoy') return latestQuarterly?.yoy ?? null
    return null
  }, [latestMonthly, latestQuarterly, dataKind])

  // 現在の日付を取得
  const currentDate = useMemo(() => {
    if (dataKind === 'mom' || dataKind === 'yoy') {
      return latestMonthly?.date ?? null
    }
    return latestQuarterly?.date ?? null
  }, [latestMonthly, latestQuarterly, dataKind])

  // 現在の色を取得
  const currentColor = useMemo(() => {
    if (dataKind === 'mom') return COLORS.mom
    if (dataKind === 'yoy') return COLORS.yoy
    if (dataKind === 'qoq') return COLORS.qoq
    if (dataKind === 'qyoy') return COLORS.qyoy
    return COLORS.yoy
  }, [dataKind])

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
    if (dataKind === 'mom') return 'ch_industrial_production_mom'
    if (dataKind === 'yoy') return 'ch_industrial_production_yoy'
    if (dataKind === 'qoq') return 'ch_industrial_production_qoq'
    if (dataKind === 'qyoy') return 'ch_industrial_production_qyoy'
    return 'ch_industrial_production_yoy'
  }

  const getChartTitle = () => {
    if (dataKind === 'mom') return '鉱工業生産（前月比）'
    if (dataKind === 'yoy') return '鉱工業生産（前年比）'
    if (dataKind === 'qoq') return '鉱工業生産（四半期・前期比）'
    if (dataKind === 'qyoy') return '鉱工業生産（四半期・前年比）'
    return '鉱工業生産'
  }

  const dateFormatter = isQuarterly ? formatQuarterLabel : formatMonthLabel
  // momまたはqoqで表示形式切替が有効
  const showDisplayModeToggle = dataKind === 'mom' || dataKind === 'qoq'

  return (
    <div id="ch-industrial-production-chart">
      <ChartContainer
        title="鉱工業生産"
        showPeriodSelector={false}
        dataSource="BFS (Federal Statistical Office)"
        sourceUrl="https://www.bfs.admin.ch/bfs/de/home/statistiken/industrie-dienstleistungen/produktion-auftraege-umsatz.html"
        handbookId="industrial-production"
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
                  {/* 上段: データ種別 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      currentMode={dataKind}
                      onChange={setDataKind}
                      options={DATA_KIND_OPTIONS}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(`/compare?s=${getCompareId()}`, '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 下段: 表示形式（momまたはqoqのときのみ） */}
                  {showDisplayModeToggle && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS_IP} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 期間セレクター（ヒートマップ以外で表示） */}
                  {!(showDisplayModeToggle && displayMode === 'heatmap') && (
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                  )}

                  {/* 月次前月比ヒートマップ */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && <MonthlyTable />}

                  {/* 四半期前期比ヒートマップ */}
                  {dataKind === 'qoq' && displayMode === 'heatmap' && <QuarterlyTable />}

                  {/* 月次前月比チャート */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <StandardBarChart
                      data={filteredMonthlyData}
                      bars={[
                        { dataKey: 'mom', color: COLORS.mom, name: '鉱工業生産（月次動向前月比）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      xAxisFormatter={formatMonthLabel}
                    />
                  )}

                  {/* 月次前年比チャート */}
                  {dataKind === 'yoy' && (
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

                  {/* 四半期前期比チャート */}
                  {dataKind === 'qoq' && displayMode === 'chart' && (
                    <StandardBarChart
                      data={filteredQuarterlyData}
                      bars={[
                        { dataKey: 'qoq', color: COLORS.qoq, name: '鉱工業生産（四半期動向前期比）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      xAxisFormatter={formatQuarterLabel}
                    />
                  )}

                  {/* 四半期前年比チャート */}
                  {dataKind === 'qyoy' && (
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
