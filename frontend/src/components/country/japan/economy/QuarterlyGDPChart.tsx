/**
 * 日本四半期GDP成長率チャート
 *
 * データソース: e-Stat（内閣府）
 * 更新: 四半期毎（速報・改定値）
 *
 * タブ構成:
 * 1. 時系列（前期比グラフ / 前期比テーブル）
 * 2. マーケットインパクト
 */
import { useState, useEffect, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// USA共通モジュールを流用
import {
  usePeriodFiltering,
  useQuarterlyTableData,
  useViewModePeriodManagement,
  formatPercent,
} from '../../usa/common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  SimpleLatestValueBox,
} from '../../usa/common/ChartComponents'
import {
  DARK_THEME,
  TEXT_COLORS,
  QUARTER_NAMES,
} from '../../usa/common/chartConstants'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import {
  fetchQuarterlyGDPQoQ,
  type QuarterlyGDPData,
} from '../../../../utils/japan/quarterlyGDPApi'

// チャートデータ型
interface GDPChartData {
  date: string
  value: number
  [key: string]: string | number | null | undefined
}

// ビューモード
type ViewMode = 'qoq_chart' | 'qoq_table'

// グラフの色
const COLORS = {
  qoq: '#10b981',  // 緑
}

const QuarterlyGDPChart: React.FC = () => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [qoqData, setQoqData] = useState<QuarterlyGDPData | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('qoq_chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // ビューモード毎の期間管理（共通フック使用）
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    qoq_chart: 'default',
    qoq_table: 'default',
  })

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      setError(null)

      try {
        const qoq = await fetchQuarterlyGDPQoQ()
        setQoqData(qoq)
      } catch (err) {
        console.error('Error fetching GDP data:', err)
        setError('データの取得に失敗しました')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  // 四半期日付フォーマット（2024-Q1 -> 2024/Q1）
  const formatQuarterLabel = (dateStr: string): string => {
    try {
      const [year, quarter] = dateStr.split('-')
      return `${year}/${quarter}`
    } catch {
      return dateStr
    }
  }

  // 四半期日付をDateオブジェクトに変換
  const parseQuarterToDate = (dateStr: string): Date => {
    const [year, quarter] = dateStr.split('-')
    const quarterNum = parseInt(quarter.replace('Q', ''))
    const month = (quarterNum - 1) * 3
    return new Date(parseInt(year), month, 1)
  }

  // QoQチャートデータを整形
  const qoqChartData = useMemo<GDPChartData[]>(() => {
    if (!qoqData?.data || qoqData.data.length === 0) return []

    return qoqData.data
      .map((item) => ({
        date: parseQuarterToDate(item.date).toISOString(),
        value: item.value,
        originalDate: item.date,
      }))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  }, [qoqData])

  // formatPercent共通関数を使用（小数点2桁）
  const formatPercentage = (value: number) => formatPercent(value, 2)

  // 期間フィルタリング
  const filteredQoQData = usePeriodFiltering(qoqChartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ（年別×四半期のマトリックス）
  const tableData = useQuarterlyTableData(qoqChartData, (item) => item.value, 10)

  const hasData = qoqChartData.length > 0

  if (loading) {
    return <LoadingChart title="GDP成長率（前期比）" />
  }

  if (error) {
    return (
      <ChartContainer title="GDP成長率（前期比）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>
          {error}
        </div>
      </ChartContainer>
    )
  }

  if (!hasData) {
    return (
      <ChartContainer title="GDP成長率（前期比）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestQoQ = qoqData?.latest

  // 次回発表日時
  const nextRelease = qoqData?.next_release
    ? { date: qoqData.next_release }
    : null

  // テーブルセルの背景色を決定（ダークテーマ用）
  const getCellColor = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'transparent'
    if (value > 1) return 'rgba(16, 185, 129, 0.55)'
    if (value > 0) return 'rgba(16, 185, 129, 0.25)'
    if (value < -1) return 'rgba(239, 68, 68, 0.55)'
    if (value < 0) return 'rgba(239, 68, 68, 0.25)'
    return 'transparent'
  }

  // テーブルコンポーネント（ダークテーマ）
  const GDPTable = () => (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, marginBottom: 12 }}>
        ※ 直近10年間のGDP成長率データ（前期比）
      </div>
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
                        {value >= 0 ? '+' : ''}{value.toFixed(2)}%
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
          +1%以上
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(16, 185, 129, 0.25)', marginRight: 4 }} />
          0〜+1%
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(239, 68, 68, 0.25)', marginRight: 4 }} />
          0〜-1%
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(239, 68, 68, 0.55)', marginRight: 4 }} />
          -1%以下
        </span>
      </div>
    </div>
  )

  return (
    <div id="japan-gdp-chart">
      <ChartContainer
        title="GDP成長率（前期比）"
        showPeriodSelector={false}
        dataSource="内閣府"
        sourceUrl="https://www.esri.cao.go.jp/jp/sna/menu.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="前期比"
          value={latestQoQ?.value}
          valueColor={COLORS.qoq}
          date={latestQoQ?.date}
          dateFormatter={formatQuarterLabel}
          nextRelease={nextRelease}
          format="percent"
          decimals={2}
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
                  <ViewModeButtonGroup
                    currentMode={viewMode}
                    onChange={(mode) => setViewMode(mode as ViewMode)}
                    options={[
                      { mode: 'qoq_chart', label: 'グラフ' },
                      { mode: 'qoq_table', label: 'テーブル' },
                    ]}
                  />

                  {/* 期間セレクター（グラフ表示時のみ） */}
                  {viewMode === 'qoq_chart' && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <Tooltip title="比較ページを開く">
                        <Button
                          icon={<AreaChartOutlined />}
                          onClick={() => window.open('/compare?s=japan_gdp_qoq', '_blank')}
                        >
                          データ比較
                        </Button>
                      </Tooltip>
                    </div>
                  )}

                  {/* コンテンツ表示 */}
                  {viewMode === 'qoq_table' && <GDPTable />}

                  {viewMode === 'qoq_chart' && (
                    <ZoomableChart
                      data={filteredQoQData}
                      dataKey="value"
                      color={COLORS.qoq}
                      name="GDP成長率（前期比）"
                      height={450}
                      tickFormatter={formatPercentage}
                      tooltipFormatter={formatPercentage}
                      tooltipLabelFormatter={(dateStr) => {
                        const date = new Date(dateStr)
                        const quarter = Math.floor(date.getMonth() / 3) + 1
                        return `${date.getFullYear()}年Q${quarter}`
                      }}
                      xAxisTickFormatter={(dateStr) => {
                        const date = new Date(dateStr)
                        const quarter = Math.floor(date.getMonth() / 3) + 1
                        return `${date.getFullYear()}/Q${quarter}`
                      }}
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
                <MarketImpactTab indicatorId="japan_gdp_qoq" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}

export default QuarterlyGDPChart
