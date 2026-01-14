/**
 * ユーロ圏GDP成長率チャートコンポーネント
 *
 * ECB APIからGDP成長率データを取得し、前期比・前年比を表示
 *
 * データソース:
 * - European Central Bank (ECB) - Main National Accounts
 *
 * 発表スケジュール:
 * - 毎日18:00 CET更新
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
import { DARK_THEME, TEXT_COLORS, CHART_COLORS, LATEST_VALUE_BOX_STYLE, QUARTER_NAMES } from '../../usa/common/chartConstants'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { ECBGDPData } from '../../../../hooks/useDashboardData'

interface EuroGDPChartProps {
  data: ECBGDPData | null
}

type ViewMode = 'chart' | 'table'
type GDPType = 'qoq' | 'yoy'

interface ChartDataPoint {
  date: string
  value: number
  [key: string]: unknown
}

// ECB四半期形式（2024-Q3）用のフォーマッター
const formatECBQuarterLabel = (dateStr: string): string => {
  // "2024-Q3" -> "2024/Q3"
  if (!dateStr) return ''
  return dateStr.replace('-Q', '/Q')
}

// ECB四半期形式から年を抽出
const getYearFromECBQuarter = (dateStr: string): number => {
  // "2024-Q3" -> 2024
  const match = dateStr.match(/^(\d{4})-Q\d$/)
  return match ? parseInt(match[1], 10) : 0
}

// ECB四半期形式から四半期を抽出（0-indexed）
const getQuarterFromECBQuarter = (dateStr: string): number => {
  // "2024-Q3" -> 2 (0-indexed)
  const match = dateStr.match(/^(\d{4})-Q(\d)$/)
  return match ? parseInt(match[2], 10) - 1 : 0
}

export default function EuroGDPChart({ data }: EuroGDPChartProps) {
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

    // 日付でソート（古い順）
    result.sort((a, b) => a.date.localeCompare(b.date))

    return result
  }, [data, gdpType])

  // formatPercent共通関数を使用（小数点2桁）
  const formatPercentage = (value: number) => formatPercent(value, 2)

  // 期間フィルタリング（ECB四半期形式対応）
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
      const year = getYearFromECBQuarter(item.date)
      return year >= startYear
    })
  }, [chartData, selectedPeriod])

  // テーブル用データ（年別×四半期のマトリックス）- ECB形式対応
  const tableData = useMemo(() => {
    if (!chartData.length) return { years: [], quarterlyData: {} }

    const years = new Set<number>()
    const quarterlyData: Record<number, Record<number, number | null>> = {}

    chartData.forEach(item => {
      const year = getYearFromECBQuarter(item.date)
      const quarter = getQuarterFromECBQuarter(item.date)

      if (year > 0) {
        years.add(year)
        if (!quarterlyData[year]) {
          quarterlyData[year] = {}
        }
        quarterlyData[year][quarter] = item.value
      }
    })

    // 直近10年間のみ
    const sortedYears = Array.from(years).sort((a, b) => b - a).slice(0, 10).reverse()

    return { years: sortedYears, quarterlyData }
  }, [chartData])

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="GDP成長率（ユーロ圏）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="GDP成長率（ユーロ圏）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestValue = filteredData.length > 0 ? filteredData[filteredData.length - 1] : null

  // テーブルセルの背景色を決定（ダークテーマ用）- QoQ専用
  const getCellColor = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'transparent'
    // QoQは値が小さいので閾値を調整
    if (value > 0.5) return 'rgba(16, 185, 129, 0.55)'   // 強いプラス: 緑
    if (value > 0.25) return 'rgba(16, 185, 129, 0.35)' // プラス: 薄緑
    if (value > 0) return 'rgba(16, 185, 129, 0.15)'   // プラス: 緑
    if (value < -0.5) return 'rgba(239, 68, 68, 0.55)'   // マイナス: 赤
    if (value < -0.25) return 'rgba(239, 68, 68, 0.35)' // マイナス: 薄赤
    if (value < 0) return 'rgba(239, 68, 68, 0.15)'   // マイナス: 薄赤
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

  // 表示モード切り替えボタン（ダークテーマ）- QoQのみテーブル表示可能
  const ViewModeButtons = () => {
    // YoYの場合はテーブルボタンを表示しない
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

  // テーブルコンポーネント（ダークテーマ）
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
  // マーケットインパクトタブでは euro_gdp を使用（DBマッピングと統一）
  const compareIndicatorId = gdpType === 'qoq' ? 'eurozone_gdp_qoq' : 'eurozone_gdp_yoy'
  const marketImpactIndicatorId = 'euro_gdp'
  const chartTitle = gdpType === 'qoq' ? 'GDP成長率（前期比）' : 'GDP成長率（前年比）'

  return (
    <div id="euro-gdp-chart">
      <ChartContainer
        title="GDP成長率（ユーロ圏）"
        showPeriodSelector={false}
        dataSource="European Central Bank (ECB)"
        sourceUrl="https://ec.europa.eu/eurostat/web/main/news/euro-indicators?p_p_id=estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageNumber=1&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_action=search&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageSize=11&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_collection=CAT_PREREL&p_auth=CCS941kV&text=GDP"
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
                ({formatECBQuarterLabel(latestValue.date)})
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
                          onClick={() => window.open(`/compare?s=${compareIndicatorId}`, '_blank')}
                        >
                          データ比較
                        </Button>
                      </Tooltip>
                    </div>
                  )}
                  {/* テーブルはQoQのみ表示 */}
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
                      tooltipLabelFormatter={formatECBQuarterLabel}
                      xAxisTickFormatter={formatECBQuarterLabel}
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
