/**
 * ONS GVA（月間GDP）チャートコンポーネント
 *
 * Office for National StatisticsからイギリスGVA（Gross Value Added）データを取得し表示
 *
 * 表示モード:
 * 1. 3か月（対前3か月）: 棒グラフ＆テーブル (ED3H data)
 * 2. 単月の前月比: 棒グラフ＆テーブル (ECY2 mom)
 * 3. 3か月前年比: 線グラフ (ED3H yoy)
 * 4. 前年同月比: 線グラフ (ECY2 yoy)
 *
 * データソース:
 * - Office for National Statistics (ONS) - Monthly GDP
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
import { NoDataMessage, NextReleaseDisplay } from '../../usa/common/ChartComponents'
import { DARK_THEME, TEXT_COLORS, CHART_COLORS, LATEST_VALUE_BOX_STYLE } from '../../usa/common/chartConstants'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { ONSGVAData } from '../../../../hooks/useDashboardData'

interface ONSGVAChartProps {
  data: ONSGVAData | null
}

type ViewMode = 'chart' | 'table'
// 4つの表示モード
type GVAType = '3m3m' | 'mom' | '3m_yoy' | 'yoy'

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

// GVAタイプの設定
const GVA_TYPE_CONFIG: Record<GVAType, {
  label: string
  chartType: 'bar' | 'line'
  hasTable: boolean
  compareId: string
  chartTitle: string
  tableDescription: string
}> = {
  '3m3m': {
    label: '3か月成長率',
    chartType: 'bar',
    hasTable: true,
    compareId: 'uk_gva_3m3m',
    chartTitle: '月間GDP（3か月成長率）',
    tableDescription: '※ 月間GDP（GVA）3か月間成長率データ（単位: %）',
  },
  'mom': {
    label: '単月前月比',
    chartType: 'bar',
    hasTable: true,
    compareId: 'uk_gva_mom',
    chartTitle: '月間GDP（前月比）',
    tableDescription: '※ 月間GDP（GVA）前月比データ（単位: %）',
  },
  '3m_yoy': {
    label: '3か月前年比',
    chartType: 'line',
    hasTable: false,
    compareId: 'uk_gva_3m_yoy',
    chartTitle: '月間GDP（3か月前年比）',
    tableDescription: '',
  },
  'yoy': {
    label: '前年同月比',
    chartType: 'line',
    hasTable: false,
    compareId: 'uk_gva_yoy',
    chartTitle: '月間GDP（前年同月比）',
    tableDescription: '',
  },
}

export default function ONSGVAChart({ data }: ONSGVAChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const [viewMode, setViewMode] = useState<ViewMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [gvaType, setGvaType] = useState<GVAType>('3m3m')

  const config = GVA_TYPE_CONFIG[gvaType]

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    if (gvaType === '3m3m') {
      // ED3H（3か月間成長率）データを使用 - ONS公式発表値
      const ed3hData = data.ed3h?.data
      if (!ed3hData || !Array.isArray(ed3hData)) return []

      const result: ChartDataPoint[] = ed3hData
        .filter(point => point.value !== null && point.value !== undefined)
        .map(point => ({
          date: point.date,
          value: point.value,
          period: point.period,
        }))

      result.sort((a, b) => a.date.localeCompare(b.date))
      return result
    } else if (gvaType === 'mom') {
      // ECY2のMoMデータを使用
      const momData = data.ecy2?.mom
      if (!momData || !Array.isArray(momData)) return []

      const result: ChartDataPoint[] = momData
        .filter(point => point.mom_change !== null && point.mom_change !== undefined)
        .map(point => ({
          date: point.date,
          value: point.mom_change || 0,
          period: point.period,
        }))

      result.sort((a, b) => a.date.localeCompare(b.date))
      return result
    } else if (gvaType === '3m_yoy') {
      // ECY2の3か月移動平均YoYデータを使用（3か月前年比）
      const ecy2_3mYoyData = data.ecy2?.['3m_yoy']
      if (!ecy2_3mYoyData || !Array.isArray(ecy2_3mYoyData)) return []

      const result: ChartDataPoint[] = ecy2_3mYoyData
        .filter(point => point.yoy_change !== null && point.yoy_change !== undefined)
        .map(point => ({
          date: point.date,
          value: point.yoy_change || 0,
          period: point.period,
        }))

      result.sort((a, b) => a.date.localeCompare(b.date))
      return result
    } else {
      // ECY2のYoYデータを使用（前年同月比）
      const yoyData = data.ecy2?.yoy
      if (!yoyData || !Array.isArray(yoyData)) return []

      const result: ChartDataPoint[] = yoyData
        .filter(point => point.yoy_change !== null && point.yoy_change !== undefined)
        .map(point => ({
          date: point.date,
          value: point.yoy_change || 0,
          period: point.period,
        }))

      result.sort((a, b) => a.date.localeCompare(b.date))
      return result
    }
  }, [data, gvaType])

  // formatPercent共通関数を使用（小数点2桁）
  const formatPercentage = (value: number) => formatPercent(value, 2)

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
    return <LoadingChart title="月間GDP（GVA）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="月間GDP（GVA）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestValue = filteredData.length > 0 ? filteredData[filteredData.length - 1] : null

  // テーブルセルの背景色を決定（ダークテーマ用）
  const getCellColor = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'transparent'
    // 閾値を調整
    if (value > 0.5) return 'rgba(16, 185, 129, 0.55)'   // 強いプラス: 緑
    if (value > 0.2) return 'rgba(16, 185, 129, 0.35)'   // プラス: 薄緑
    if (value > 0) return 'rgba(16, 185, 129, 0.15)'     // プラス: 緑
    if (value < -0.5) return 'rgba(239, 68, 68, 0.55)'   // マイナス: 赤
    if (value < -0.2) return 'rgba(239, 68, 68, 0.35)'   // マイナス: 薄赤
    if (value < 0) return 'rgba(239, 68, 68, 0.15)'      // マイナス: 薄赤
    return 'transparent'
  }

  // GVA種類切り替えボタン（4つのモード）
  const GVATypeButtons = () => (
    <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
      {(Object.keys(GVA_TYPE_CONFIG) as GVAType[]).map((type) => (
        <button
          key={type}
          onClick={() => {
            setGvaType(type)
            // テーブル非対応のモードに切り替えた場合はチャート表示に戻す
            if (!GVA_TYPE_CONFIG[type].hasTable) {
              setViewMode('chart')
            }
          }}
          style={{
            padding: '6px 12px',
            border: gvaType === type ? `2px solid ${CHART_COLORS.primary}` : `1px solid ${DARK_THEME.border}`,
            borderRadius: 4,
            background: gvaType === type ? 'rgba(59, 130, 246, 0.15)' : DARK_THEME.bgSecondary,
            cursor: 'pointer',
            fontWeight: gvaType === type ? 'bold' : 'normal',
            color: gvaType === type ? CHART_COLORS.primary : DARK_THEME.textSecondary,
          }}
        >
          {GVA_TYPE_CONFIG[type].label}
        </button>
      ))}
    </div>
  )

  // 表示モード切り替えボタン（テーブル対応のモードのみ）
  const ViewModeButtons = () => {
    if (!config.hasTable) return null

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

  // テーブルコンポーネント（ダークテーマ・月次版）
  const GVATable = () => (
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
  const compareIndicatorId = config.compareId
  const marketImpactIndicatorId = 'ons_gva'
  const chartTitle = config.chartTitle

  return (
    <div id="ons-gva-chart">
      <ChartContainer
        title="月間GDP（GVA）"
        showPeriodSelector={false}
        dataSource="Office for National Statistics (ONS)"
        sourceUrl="https://www.ons.gov.uk/economy/grossdomesticproductgdp"
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
                  <GVATypeButtons />
                  <ViewModeButtons />

                  {viewMode === 'chart' && (
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
                  {viewMode === 'table' && config.hasTable && (
                    <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, marginBottom: 12 }}>
                      {config.tableDescription}
                    </div>
                  )}

                  {viewMode === 'table' && config.hasTable ? (
                    <GVATable />
                  ) : (
                    <ZoomableChart
                      data={filteredData}
                      dataKey="value"
                      color={CHART_COLORS.primary}
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
