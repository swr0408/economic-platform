/**
 * ドイツGDP成長率チャートコンポーネント
 *
 * データ:
 * - GDP成長率前期比 (QoQ) - 季節・カレンダー調整済み
 * - GDP成長率前年比 (YoY)
 *
 * データソース:
 * - Destatis GENESIS API (81000-0002)
 * - FMP economic_calendar_events（速報値）
 *
 * 発表スケジュール:
 * - 速報: 四半期終了後約30日
 * - 確定: 四半期終了後約55日
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import { formatPercent, type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, NextReleaseDisplay } from '../../usa/common/ChartComponents'
import { DARK_THEME, TEXT_COLORS, CHART_COLORS, LATEST_VALUE_BOX_STYLE, QUARTER_NAMES } from '../../usa/common/chartConstants'

import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { GermanyGDPGrowthData } from '../../../../hooks/useDashboardData'

interface GermanyGDPGrowthChartProps {
  data: GermanyGDPGrowthData | null
}

type ViewMode = 'chart' | 'table'
type GDPType = 'qoq' | 'yoy'

interface ChartDataPoint {
  date: string
  value: number
  [key: string]: unknown
}

// 四半期形式（2024-Q3）用のフォーマッター
const formatQuarterLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  return dateStr.replace('-Q', '/Q')
}

// 四半期形式から年を抽出
const getYearFromQuarter = (dateStr: string): number => {
  const match = dateStr.match(/^(\d{4})-Q\d$/)
  return match ? parseInt(match[1], 10) : 0
}

// 四半期形式から四半期を抽出（0-indexed）
const getQuarterFromQuarter = (dateStr: string): number => {
  const match = dateStr.match(/^(\d{4})-Q(\d)$/)
  return match ? parseInt(match[2], 10) - 1 : 0
}

export default function GermanyGDPGrowthChart({ data }: GermanyGDPGrowthChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const [viewMode, setViewMode] = useState<ViewMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [gdpType, setGdpType] = useState<GDPType>('qoq')

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const sourceData = gdpType === 'qoq' ? data.gdp_growth_qoq : data.gdp_growth_yoy
    if (!sourceData || !Array.isArray(sourceData)) return []

    const result: ChartDataPoint[] = sourceData
      .filter(point => point.value !== null)
      .map(point => ({
        date: point.date,
        value: point.value || 0,
      }))

    result.sort((a, b) => a.date.localeCompare(b.date))

    return result
  }, [data, gdpType])

  const formatPercentage = (value: number) => formatPercent(value, 2)

  // 期間フィルタリング（四半期形式対応）
  const filteredData = useMemo(() => {
    if (!chartData.length) return []

    const now = new Date()
    const currentYear = now.getFullYear()

    let startYear: number
    if (selectedPeriod === 'all') {
      return chartData
    } else if (selectedPeriod === 'default') {
      startYear = 2015
    } else if (typeof selectedPeriod === 'number') {
      startYear = currentYear - selectedPeriod
    } else {
      startYear = 2015
    }

    return chartData.filter(item => {
      const year = getYearFromQuarter(item.date)
      return year >= startYear
    })
  }, [chartData, selectedPeriod])

  // テーブル用データ（年別×四半期のマトリックス）
  const tableData = useMemo(() => {
    if (!chartData.length) return { years: [], quarterlyData: {} }

    const years = new Set<number>()
    const quarterlyData: Record<number, Record<number, number | null>> = {}

    chartData.forEach(item => {
      const year = getYearFromQuarter(item.date)
      const quarter = getQuarterFromQuarter(item.date)

      if (year > 0) {
        years.add(year)
        if (!quarterlyData[year]) {
          quarterlyData[year] = {}
        }
        quarterlyData[year][quarter] = item.value
      }
    })

    const sortedYears = Array.from(years).sort((a, b) => b - a).slice(0, 10).reverse()

    return { years: sortedYears, quarterlyData }
  }, [chartData])

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="GDP成長率（ドイツ）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="GDP成長率（ドイツ）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latestValue = filteredData.length > 0 ? filteredData[filteredData.length - 1] : null

  // テーブルセルの背景色を決定（ダークテーマ用）
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

  // GDP種類切り替えボタン
  const GDPTypeButtons = () => (
    <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
      <button
        onClick={() => setGdpType('qoq')}
        style={{
          padding: '6px 12px',
          border: gdpType === 'qoq' ? `2px solid ${CHART_COLORS.primary}` : `1px solid ${DARK_THEME.border}`,
          borderRadius: 4,
          background: gdpType === 'qoq' ? 'rgba(59, 130, 246, 0.15)' : DARK_THEME.bgSecondary,
          cursor: 'pointer',
          fontWeight: gdpType === 'qoq' ? 'bold' : 'normal',
          color: gdpType === 'qoq' ? CHART_COLORS.primary : DARK_THEME.textSecondary,
        }}
      >
        前期比 (QoQ)
      </button>
      <button
        onClick={() => setGdpType('yoy')}
        style={{
          padding: '6px 12px',
          border: gdpType === 'yoy' ? `2px solid ${CHART_COLORS.primary}` : `1px solid ${DARK_THEME.border}`,
          borderRadius: 4,
          background: gdpType === 'yoy' ? 'rgba(59, 130, 246, 0.15)' : DARK_THEME.bgSecondary,
          cursor: 'pointer',
          fontWeight: gdpType === 'yoy' ? 'bold' : 'normal',
          color: gdpType === 'yoy' ? CHART_COLORS.primary : DARK_THEME.textSecondary,
        }}
      >
        前年比 (YoY)
      </button>
    </div>
  )

  // 表示モード切り替えボタン（QoQのみテーブル表示可能）
  const ViewModeButtons = () => {
    if (gdpType === 'yoy') return null

    return (
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <button
          onClick={() => setViewMode('chart')}
          style={{
            padding: '6px 12px',
            border: viewMode === 'chart' ? `2px solid ${CHART_COLORS.primary}` : `1px solid ${DARK_THEME.border}`,
            borderRadius: 4,
            background: viewMode === 'chart' ? 'rgba(59, 130, 246, 0.15)' : DARK_THEME.bgSecondary,
            cursor: 'pointer',
            fontWeight: viewMode === 'chart' ? 'bold' : 'normal',
            color: viewMode === 'chart' ? CHART_COLORS.primary : DARK_THEME.textSecondary,
          }}
        >
          グラフ
        </button>
        <button
          onClick={() => setViewMode('table')}
          style={{
            padding: '6px 12px',
            border: viewMode === 'table' ? `2px solid ${CHART_COLORS.primary}` : `1px solid ${DARK_THEME.border}`,
            borderRadius: 4,
            background: viewMode === 'table' ? 'rgba(59, 130, 246, 0.15)' : DARK_THEME.bgSecondary,
            cursor: 'pointer',
            fontWeight: viewMode === 'table' ? 'bold' : 'normal',
            color: viewMode === 'table' ? CHART_COLORS.primary : DARK_THEME.textSecondary,
          }}
        >
          テーブル
        </button>
      </div>
    )
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
  const compareIndicatorId = gdpType === 'qoq' ? 'germany_gdp_growth_qoq' : 'germany_gdp_growth_yoy'
  const marketImpactIndicatorId = 'de_gdp_growth'
  const chartTitle = gdpType === 'qoq' ? 'GDP成長率（前期比）' : 'GDP成長率（前年比）'

  return (
    <div id="germany-gdp-growth-chart">
      <ChartContainer
        title="GDP成長率（ドイツ）"
        showPeriodSelector={false}
        dataSource="Destatis"
        sourceUrl="https://www.destatis.de/SiteGlobals/Forms/Suche/Presse/DE/Pressesuche_Formular_2.html?resourceId=245598&input_=250572&pageLocale=de&templateQueryString=Bruttoinlandsprodukt&submit.x=0&submit.y=0"
      >
        {/* 最新値表示 */}
        {latestValue && (
          <div style={LATEST_VALUE_BOX_STYLE}>
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>最新値: </span>
              <span
                style={{
                  fontSize: 18,
                  fontWeight: 'bold',
                  color: latestValue.value >= 0 ? TEXT_COLORS.positive : TEXT_COLORS.negative,
                }}
              >
                {formatPercentage(latestValue.value)}
              </span>
              <span style={{ fontSize: 12, color: TEXT_COLORS.tertiary, marginLeft: 8 }}>
                ({formatQuarterLabel(latestValue.date)})
              </span>
            </div>
            <NextReleaseDisplay nextRelease={data.next_release} />
          </div>
        )}

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
                  <GDPTypeButtons />
                  <ViewModeButtons />

                  {viewMode === 'chart' && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
                      <Tooltip title="比較ページを開く">
                        <Button
                          icon={<AreaChartOutlined />}
                          onClick={() => window.open(`/compare?s=${compareIndicatorId}&s=eurozone_gdp_qoq`, '_blank')}
                        >
                          データ比較
                        </Button>
                      </Tooltip>
                    </div>
                  )}

                  {viewMode === 'table' && gdpType === 'qoq' && (
                    <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, marginBottom: 12 }}>
                      ※ 直近10年間のGDP成長率データ（単位: %）
                    </div>
                  )}

                  {viewMode === 'table' && gdpType === 'qoq' ? (
                    <GDPTable />
                  ) : (
                    <ZoomableChart
                      data={filteredData}
                      dataKey="value"
                      color={CHART_COLORS.primary}
                      name={chartTitle}
                      height={450}
                      tickFormatter={formatPercentage}
                      tooltipFormatter={formatPercentage}
                      tooltipLabelFormatter={formatQuarterLabel}
                      xAxisTickFormatter={formatQuarterLabel}
                      enableDynamicTicks={true}
                      showZeroLine={true}
                      showFiftyLine={false}
                      connectNulls={true}
                      hideLegend={true}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId={marketImpactIndicatorId} />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
