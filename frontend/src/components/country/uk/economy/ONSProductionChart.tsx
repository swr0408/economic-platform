/**
 * ONS Production Industries（鉱工業生産）チャートコンポーネント
 *
 * Office for National Statisticsからイギリス鉱工業生産データを取得し表示
 *
 * 表示モード:
 * 1. 前年比 (YoY): 線グラフ (ED2T data)
 * 2. 前月比 (MoM): 棒グラフ＆テーブル (ECYZ data)
 *
 * データソース:
 * - Office for National Statistics (ONS) - Production Industries
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import { formatPercent, type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, NextReleaseDisplay, ViewModeButtonGroup } from '../../usa/common/ChartComponents'
import { DARK_THEME, TEXT_COLORS, LATEST_VALUE_BOX_STYLE } from '../../usa/common/chartConstants'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { ONSProductionData } from '../../../../hooks/useDashboardData'

interface ONSProductionChartProps {
  data: ONSProductionData | null
}

// 統一されたビューモード（データタイプ + 表示形式）
type ViewMode = 'yoy' | 'mom_chart' | 'mom_table'

interface ChartDataPoint {
  date: string
  value: number
  period?: string
  [key: string]: unknown
}

// 月次期間表記のフォーマット（"2024 Sep" -> "2024/09"）
const formatMonthLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  // "2024-09-01" -> "2024/09"
  const match = dateStr.match(/^(\d{4})-(\d{2})-01$/)
  if (match) {
    return `${match[1]}/${match[2]}`
  }
  return dateStr
}

// 日付から年を抽出
const getYearFromDate = (dateStr: string): number => {
  const match = dateStr.match(/^(\d{4})/)
  return match ? parseInt(match[1], 10) : 0
}

// 日付から月を抽出（1-12）
const getMonthFromDate = (dateStr: string): number => {
  const match = dateStr.match(/^\d{4}-(\d{2})-01$/)
  return match ? parseInt(match[1], 10) : 0
}

// 月名配列（テーブル用）
const MONTH_NAMES = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom_chart', label: '前月比' },
  { mode: 'mom_table', label: '前月比（テーブル）' },
]

// ビューモードの設定情報
const VIEW_MODE_CONFIG: Record<ViewMode, {
  chartType: 'bar' | 'line'
  compareId: string
  chartTitle: string
  tableDescription: string
  dataType: 'yoy' | 'mom'
}> = {
  'yoy': {
    chartType: 'line',
    compareId: 'uk_production_yoy',
    chartTitle: '鉱工業生産（前年比）',
    tableDescription: '',
    dataType: 'yoy',
  },
  'mom_chart': {
    chartType: 'bar',
    compareId: 'uk_production_mom',
    chartTitle: '鉱工業生産（前月比）',
    tableDescription: '',
    dataType: 'mom',
  },
  'mom_table': {
    chartType: 'bar',
    compareId: 'uk_production_mom',
    chartTitle: '鉱工業生産（前月比）',
    tableDescription: '※ 鉱工業生産 前月比データ（単位: %）',
    dataType: 'mom',
  },
}

export default function ONSProductionChart({ data }: ONSProductionChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  const config = VIEW_MODE_CONFIG[viewMode]
  // viewModeからデータタイプを導出
  const productionType = config.dataType

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    if (productionType === 'yoy') {
      // ED2T（YoY成長率）データを使用
      const ed2tData = data.ed2t?.data
      if (!ed2tData || !Array.isArray(ed2tData)) return []

      const result: ChartDataPoint[] = ed2tData
        .filter(point => point.value !== null && point.value !== undefined)
        .map(point => ({
          date: point.date,
          value: point.value,
          period: point.period,
        }))

      result.sort((a, b) => a.date.localeCompare(b.date))
      return result
    } else {
      // ECYZ（MoM成長率）データを使用
      const ecyzData = data.ecyz?.data
      if (!ecyzData || !Array.isArray(ecyzData)) return []

      const result: ChartDataPoint[] = ecyzData
        .filter(point => point.value !== null && point.value !== undefined)
        .map(point => ({
          date: point.date,
          value: point.value,
          period: point.period,
        }))

      result.sort((a, b) => a.date.localeCompare(b.date))
      return result
    }
  }, [data, productionType])

  // formatPercent共通関数を使用（小数点1桁）
  const formatPercentage = (value: number) => formatPercent(value, 1)

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    if (!chartData.length) return []

    const now = new Date()
    const currentYear = now.getFullYear()

    let startYear: number
    if (selectedPeriod === 'all') {
      return chartData
    } else if (selectedPeriod === 'default') {
      startYear = 2019
    } else if (typeof selectedPeriod === 'number') {
      startYear = currentYear - selectedPeriod
    } else {
      startYear = 2019
    }

    return chartData.filter(item => {
      const year = getYearFromDate(item.date)
      return year >= startYear
    })
  }, [chartData, selectedPeriod])

  // テーブル用データ（年別×月のマトリックス）
  const tableData = useMemo(() => {
    if (!chartData.length) return { years: [], monthlyData: {} }

    const years = new Set<number>()
    const monthlyData: Record<number, Record<number, number | null>> = {}

    chartData.forEach(item => {
      const year = getYearFromDate(item.date)
      const month = getMonthFromDate(item.date)

      if (year > 0 && month > 0) {
        years.add(year)
        if (!monthlyData[year]) {
          monthlyData[year] = {}
        }
        monthlyData[year][month - 1] = item.value
      }
    })

    // 直近8年間のみ
    const sortedYears = Array.from(years).sort((a, b) => b - a).slice(0, 8).reverse()

    return { years: sortedYears, monthlyData }
  }, [chartData])

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="鉱工業生産（Production Industries）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="鉱工業生産（Production Industries）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestValue = filteredData.length > 0 ? filteredData[filteredData.length - 1] : null

  // テーブルセルの背景色を決定（ダークテーマ用）
  const getCellColor = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'transparent'
    // 閾値を調整（鉱工業生産は変動が大きめ）
    if (value > 1) return 'rgba(16, 185, 129, 0.55)'    // 強いプラス: 緑
    if (value > 0.5) return 'rgba(16, 185, 129, 0.35)'  // プラス: 薄緑
    if (value > 0) return 'rgba(16, 185, 129, 0.15)'    // プラス: 緑
    if (value < -1) return 'rgba(239, 68, 68, 0.55)'    // マイナス: 赤
    if (value < -0.5) return 'rgba(239, 68, 68, 0.35)'  // マイナス: 薄赤
    if (value < 0) return 'rgba(239, 68, 68, 0.15)'     // マイナス: 薄赤
    return 'transparent'
  }


  // テーブルコンポーネント（ダークテーマ・月次版）
  const ProductionTable = () => (
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
                  minWidth: 50,
                }}
              >
                {month}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tableData.years.map((year: number) => (
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
              {Array.from({ length: 12 }, (_, monthIdx) => {
                const value = tableData.monthlyData[year]?.[monthIdx]
                return (
                  <td
                    key={monthIdx}
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
      <div style={{ marginTop: 8, fontSize: 11, color: TEXT_COLORS.tertiary, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(16, 185, 129, 0.55)', marginRight: 4 }} />
          プラス（+1%以上）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(16, 185, 129, 0.35)', marginRight: 4 }} />
          プラス（0〜+1%）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(239, 68, 68, 0.35)', marginRight: 4 }} />
          マイナス（0〜-1%）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(239, 68, 68, 0.55)', marginRight: 4 }} />
          マイナス（-1%以下）
        </span>
      </div>
    </div>
  )

  // データ比較用のoverlayConfig ID
  const compareIndicatorId = config.compareId
  const marketImpactIndicatorId = 'ons_production'
  const chartTitle = config.chartTitle

  return (
    <div id="ons-production-chart">
      <ChartContainer
        title="鉱工業生産"
        showPeriodSelector={false}
        dataSource="Office for National Statistics (ONS)"
        sourceUrl="https://www.ons.gov.uk/economy/economicoutputandproductivity/output"
      >
        {/* 最新値表示（ダークテーマ） */}
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
                ({formatMonthLabel(latestValue.date)})
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
                  <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />

                  {viewMode !== 'mom_table' && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
                      <Tooltip title="比較ページを開く">
                        <Button
                          icon={<AreaChartOutlined />}
                          onClick={() => window.open(`/compare?s=${compareIndicatorId}`, '_blank')}
                        >
                          データ比較
                        </Button>
                      </Tooltip>
                    </div>
                  )}
                  {/* テーブル説明 */}
                  {viewMode === 'mom_table' && (
                    <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, marginBottom: 12 }}>
                      {config.tableDescription}
                    </div>
                  )}

                  {viewMode === 'mom_table' ? (
                    <ProductionTable />
                  ) : (
                    <ZoomableChart
                      data={filteredData}
                      dataKey="value"
                      color="#8b5cf6"
                      name={chartTitle}
                      height={450}
                      tickFormatter={formatPercentage}
                      tooltipFormatter={formatPercentage}
                      tooltipLabelFormatter={formatMonthLabel}
                      xAxisTickFormatter={formatMonthLabel}
                      enableDynamicTicks={true}
                      showZeroLine={true}
                      showFiftyLine={false}
                      connectNulls={true}
                      hideLegend={true}
                      chartType={config.chartType}
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
