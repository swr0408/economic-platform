import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import { usePeriodFiltering, formatQuarterLabel, useQuarterlyTableData, formatPercent, type PeriodType } from '../common/useChartData'
import { NoDataMessage, ViewModeButtonGroup } from '../common/ChartComponents'
import { DARK_THEME, TEXT_COLORS, CHART_COLORS, LATEST_VALUE_BOX_STYLE, QUARTER_NAMES } from '../common/chartConstants'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// Props型定義
interface GDPGrowthItem {
  date: string
  value: number
}

interface GDPGrowthChartProps {
  data: GDPGrowthItem[] | null
  nextRelease?: {
    date: string
    title: string
    estimate_type: string
    quarter: number
    year: number
  } | null
}

interface GDPChartData {
  date: string
  value: number
  [key: string]: string | number | null | undefined
}

// 表示形式
type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

export default function GDPGrowthChart({ data, nextRelease }: GDPGrowthChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(20)
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // propsのデータをチャート用に変換
  const gdpData = useMemo<GDPChartData[]>(() => {
    if (!data || data.length === 0) return []

    const chartData: GDPChartData[] = data.map((item) => ({
      date: item.date,
      value: item.value,
    }))

    // 日付でソート（古い順）
    chartData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return chartData
  }, [data])

  // formatPercent共通関数を使用（小数点1桁）
  const formatPercentage = (value: number) => formatPercent(value, 1)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(gdpData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  // テーブル用データ（年別×四半期のマトリックス）
  const tableData = useQuarterlyTableData(gdpData, (item) => item.value, 10)

  const hasData = gdpData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="GDP成長率（前期比年率）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="GDP成長率（前期比年率）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestValue = filteredData.length > 0 ? filteredData[filteredData.length - 1] : null

  // テーブルセルの背景色を決定（ダークテーマ用）
  const getCellColor = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'transparent'
    if (value > 3) return 'rgba(16, 185, 129, 0.55)'   // 強いプラス: 緑
    if (value > 1.5) return 'rgba(16, 185, 129, 0.35)' // プラス: 薄緑
    if (value > 0) return 'rgba(16, 185, 129, 0.15)'   // プラス: 緑
    if (value < -3) return 'rgba(239, 68, 68, 0.55)'   // マイナス: 赤
    if (value < -1.5) return 'rgba(239, 68, 68, 0.35)' // マイナス: 薄赤
    if (value < 0) return 'rgba(239, 68, 68, 0.15)'   // マイナス: 薄赤
    return 'transparent'
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
          プラス（+2%以上）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(16, 185, 129, 0.35)', marginRight: 4 }} />
          プラス（0〜+2%）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(239, 68, 68, 0.35)', marginRight: 4 }} />
          マイナス（0〜-2%）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(239, 68, 68, 0.55)', marginRight: 4 }} />
          マイナス（-2%以下）
        </span>
      </div>
    </div>
  )

  return (
    <div id="gdp-growth-chart">
      <ChartContainer
        title="GDP成長率（前期比年率）"
        showPeriodSelector={false}
        dataSource="BEA / FRED"
        sourceUrl="https://www.bea.gov/data/gdp/gross-domestic-product"
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
                ({formatQuarterLabel(latestValue.date)})
              </span>
            </div>
            {nextRelease && (
              <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, textAlign: 'right' }}>
                <div>次回発表: {nextRelease.date}</div>
                <div style={{ color: DARK_THEME.accent }}>
                  Q{nextRelease.quarter}/{nextRelease.year} ({nextRelease.estimate_type})
                </div>
              </div>
            )}
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
                  {/* 表示形式 */}
                  <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />

                  {displayMode === 'chart' && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
                      <Tooltip title="比較ページを開く">
                        <Button
                          icon={<AreaChartOutlined />}
                          onClick={() => window.open('/compare?s=gdp_growth', '_blank')}
                        >
                          データ比較
                        </Button>
                      </Tooltip>
                    </div>
                  )}

                  {displayMode === 'heatmap' ? (
                    <GDPTable />
                  ) : (
                    <ZoomableChart
                      data={filteredData}
                      dataKey="value"
                      color={CHART_COLORS.primary}
                      name="GDP成長率（前期比）"
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
                <MarketImpactTab indicatorId="gdp_growth" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
