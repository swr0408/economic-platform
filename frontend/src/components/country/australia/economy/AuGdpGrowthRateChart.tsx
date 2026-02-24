/**
 * オーストラリアGDP成長率チャートコンポーネント
 *
 * ABSから四半期GDP成長率データを取得し、前期比・前年比を表示
 *
 * データ:
 * - GDP Growth Rate QoQ（前期比）
 * - GDP Growth Rate YoY（前年比）
 *
 * データソース:
 * - ABS (Australian Bureau of Statistics) 5206.0 Key Aggregates
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
import { DARK_THEME, TEXT_COLORS, QUARTER_NAMES } from '../../usa/common/chartConstants'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { AuGdpGrowthRateData } from '../../../../hooks/useDashboardData'

interface AuGdpGrowthRateChartProps {
  data: AuGdpGrowthRateData | null
}

interface ChartDataPoint {
  date: string
  qoq: number
  yoy: number
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  qoq: '#00843D', // オーストラリア緑
  yoy: '#FFCD00', // オーストラリア金
}

type ViewMode = 'qoq_chart' | 'qoq_table' | 'yoy'

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

// 日付から四半期を抽出（0-indexed）
const getQuarterFromDate = (dateStr: string): number => {
  const month = parseInt(dateStr.split('-')[1], 10)
  return Math.floor((month - 1) / 3)
}

export default function AuGdpGrowthRateChart({ data }: AuGdpGrowthRateChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('qoq_chart')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    qoq_chart: 'default',
    qoq_table: 'default',
    yoy: 'default',
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((item) => ({
      date: item.date,
      qoq: item.qoq ?? 0,
      yoy: item.yoy ?? 0,
    }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    return [...rawChartData].sort((a, b) => a.date.localeCompare(b.date))
  }, [rawChartData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ（年別×四半期のマトリックス）
  const tableData = useMemo(() => {
    if (!chartData.length) return { years: [] as number[], quarterlyData: {} as Record<number, Record<number, number | null>> }

    const years = new Set<number>()
    const quarterlyData: Record<number, Record<number, number | null>> = {}

    chartData.forEach(item => {
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

    // 直近10年間のみ
    const sortedYears = Array.from(years).sort((a, b) => b - a).slice(0, 10).reverse()

    return { years: sortedYears, quarterlyData }
  }, [chartData])

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  // 現在表示中の値を取得
  const currentValue = useMemo(() => {
    if (!latest) return null
    if (viewMode === 'yoy') return latest.yoy
    return latest.qoq
  }, [latest, viewMode])

  // 現在の色を取得
  const currentColor = useMemo(() => {
    if (viewMode === 'yoy') return COLORS.yoy
    return COLORS.qoq
  }, [viewMode])

  if (data === null) {
    return <LoadingChart title="GDP成長率" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="GDP成長率" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // テーブルセルの背景色を決定
  const getCellColor = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'transparent'
    if (value > 0.5) return 'rgba(16, 185, 129, 0.55)'
    if (value > 0.25) return 'rgba(16, 185, 129, 0.35)'
    if (value > 0) return 'rgba(16, 185, 129, 0.15)'
    if (value < -0.5) return 'rgba(239, 68, 68, 0.55)'
    if (value < -0.25) return 'rgba(239, 68, 68, 0.35)'
    if (value < 0) return 'rgba(239, 68, 68, 0.15)'
    return 'transparent'
  }

  // テーブルコンポーネント
  const GDPTable = () => (
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
          {tableData.years.map((year: number) => (
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
                const value = tableData.quarterlyData[year]?.[quarter]
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
      <div style={{ marginTop: 8, fontSize: 11, color: TEXT_COLORS.tertiary, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(16, 185, 129, 0.55)', marginRight: 4 }} />
          プラス（+0.5%以上）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(16, 185, 129, 0.35)', marginRight: 4 }} />
          プラス（0〜+0.5%）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(239, 68, 68, 0.35)', marginRight: 4 }} />
          マイナス（0〜-0.5%）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(239, 68, 68, 0.55)', marginRight: 4 }} />
          マイナス（-0.5%以下）
        </span>
      </div>
    </div>
  )

  // データ比較用のoverlayConfig ID
  const getCompareId = () => {
    if (viewMode === 'yoy') return 'au_gdp_growth_rate_yoy'
    return 'au_gdp_growth_rate_qoq'
  }

  const getChartTitle = () => {
    if (viewMode === 'yoy') return 'GDP成長率（前年比）'
    return 'GDP成長率（前期比）'
  }

  return (
    <div id="au-gdp-growth-rate-chart">
      <ChartContainer
        title="GDP成長率"
        showPeriodSelector={false}
        dataSource="ABS (Australian Bureau of Statistics)"
        sourceUrl="https://www.abs.gov.au/statistics/economy/national-accounts/australian-national-accounts-national-income-expenditure-and-product"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={getChartTitle()}
          value={currentValue}
          date={latest?.date}
          format="percent"
          decimals={2}
          valueColor={currentColor}
          nextRelease={data.next_release}
          dateFormatter={formatQuarterLabel}
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
                  {/* ビューモード切替（3種類） */}
                  <ViewModeButtonGroup
                    currentMode={viewMode}
                    onChange={(mode) => setViewMode(mode as ViewMode)}
                    options={[
                      { mode: 'qoq_chart', label: '前期比' },
                      { mode: 'qoq_table', label: '前期比（テーブル）' },
                      { mode: 'yoy', label: '前年比' },
                    ]}
                  />

                  {/* 期間セレクター（テーブル以外で表示） */}
                  {viewMode !== 'qoq_table' && (
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
                  {viewMode === 'qoq_table' && <GDPTable />}

                  {viewMode === 'qoq_chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'qoq', color: COLORS.qoq, name: 'GDP成長率（前期比）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      xAxisFormatter={formatQuarterLabel}
                    />
                  )}

                  {viewMode === 'yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'yoy', color: COLORS.yoy, name: 'GDP成長率（前年比）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                      yDomain={['dataMin - 1', 'dataMax + 1']}
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
                <MarketImpactTab indicatorId="au_gdp" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
