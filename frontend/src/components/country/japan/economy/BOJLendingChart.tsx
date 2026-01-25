/**
 * 日銀貸出動向チャート
 *
 * データソース: 日本銀行 統計検索サイト
 * データコード: FAAPOBAL1（貸出動向・銀行計）
 * 更新: 毎月（月末から翌月初に公表）
 *
 * 表示: 前年比（%）
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
} from '../../usa/common/chartConstants'

import {
  fetchBOJLendingYoYData,
  type BOJLendingDataPoint,
} from '../../../../api/bojLendingApi'

// チャートデータ型
interface LendingChartData {
  date: string
  value: number
  originalDate: string
  [key: string]: string | number | null | undefined
}

// ビューモード
type ViewMode = 'yoy_chart' | 'yoy_table'

// グラフの色
const COLORS = {
  yoy: '#3b82f6',  // 青
}

// 月名（テーブル用）
const MONTH_NAMES = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

/**
 * APIから取得した前年比データをチャート用に変換
 */
function transformToChartData(data: BOJLendingDataPoint[]): LendingChartData[] {
  return data.map((item) => {
    const [year, month] = item.date.split('-')
    const dateObj = new Date(parseInt(year), parseInt(month) - 1, 1)
    return {
      date: dateObj.toISOString(),
      value: item.value,
      originalDate: item.date,
    }
  })
}

const BOJLendingChart: React.FC = () => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [yoyData, setYoyData] = useState<BOJLendingDataPoint[]>([])
  const [viewMode, setViewMode] = useState<ViewMode>('yoy_chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy_chart: 'default',
    yoy_table: 'default',
  })

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      setError(null)

      try {
        const response = await fetchBOJLendingYoYData()
        if (response.error) {
          setError(response.error)
        } else {
          setYoyData(response.data)
        }
      } catch (err) {
        console.error('Error fetching BOJ Lending data:', err)
        setError('データの取得に失敗しました')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  // 月日付フォーマット（YYYY-MM -> YYYY/MM）
  const formatMonthLabel = (dateStr: string): string => {
    try {
      return dateStr.replace('-', '/')
    } catch {
      return dateStr
    }
  }

  // チャートデータに変換
  const yoyChartData = useMemo<LendingChartData[]>(() => {
    if (!yoyData || yoyData.length === 0) return []
    return transformToChartData(yoyData)
  }, [yoyData])

  // formatPercent共通関数を使用（小数点1桁）
  const formatPercentage = (value: number) => formatPercent(value, 1)

  // 期間フィルタリング
  const filteredYoYData = usePeriodFiltering(yoyChartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ（年別×月のマトリックス）
  const tableData = useMemo(() => {
    if (yoyChartData.length === 0) return { years: [], monthlyData: {} }

    // 年でグループ化
    const monthlyData: Record<number, Record<number, number | null>> = {}
    const years = new Set<number>()

    yoyChartData.forEach((item) => {
      const [year, month] = item.originalDate.split('-')
      const yearNum = parseInt(year)
      const monthNum = parseInt(month) - 1

      years.add(yearNum)
      if (!monthlyData[yearNum]) {
        monthlyData[yearNum] = {}
      }
      monthlyData[yearNum][monthNum] = item.value
    })

    // 直近10年のみ
    const sortedYears = Array.from(years).sort((a, b) => b - a).slice(0, 10).reverse()

    return {
      years: sortedYears,
      monthlyData,
    }
  }, [yoyChartData])

  const hasData = yoyChartData.length > 0

  if (loading) {
    return <LoadingChart title="貸出動向（前年比）" />
  }

  if (error) {
    return (
      <ChartContainer title="貸出動向（前年比）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>
          {error}
        </div>
      </ChartContainer>
    )
  }

  if (!hasData) {
    return (
      <ChartContainer title="貸出動向（前年比）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestYoY = yoyChartData.length > 0 ? yoyChartData[yoyChartData.length - 1] : null

  // テーブルセルの背景色を決定
  const getCellColor = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'transparent'
    if (value > 5) return 'rgba(16, 185, 129, 0.55)'
    if (value > 0) return 'rgba(16, 185, 129, 0.25)'
    if (value < -5) return 'rgba(239, 68, 68, 0.55)'
    if (value < 0) return 'rgba(239, 68, 68, 0.25)'
    return 'transparent'
  }

  // テーブルコンポーネント
  const LendingTable = () => (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, marginBottom: 12 }}>
        ※ 直近10年間の貸出動向データ（前年比）
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
            {MONTH_NAMES.map((month, idx) => (
              <th
                key={idx}
                style={{
                  padding: '10px 8px',
                  borderBottom: `2px solid ${DARK_THEME.borderLight}`,
                  fontWeight: 'bold',
                  minWidth: 60,
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
                  padding: '8px',
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
                      padding: '8px',
                      borderBottom: `1px solid ${DARK_THEME.border}`,
                      backgroundColor: getCellColor(value),
                    }}
                  >
                    {value !== null && value !== undefined ? (
                      <span style={{ color: value >= 0 ? TEXT_COLORS.positive : TEXT_COLORS.negative }}>
                        {value >= 0 ? '+' : ''}{value.toFixed(1)}%
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
          +5%以上
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(16, 185, 129, 0.25)', marginRight: 4 }} />
          0〜+5%
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(239, 68, 68, 0.25)', marginRight: 4 }} />
          0〜-5%
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(239, 68, 68, 0.55)', marginRight: 4 }} />
          -5%以下
        </span>
      </div>
    </div>
  )

  return (
    <div id="japan-boj-lending-chart">
      <ChartContainer
        title="貸出動向（前年比）"
        showPeriodSelector={false}
        dataSource="日本銀行"
        sourceUrl="https://www.stat-search.boj.or.jp/"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="前年比"
          value={latestYoY?.value}
          valueColor={COLORS.yoy}
          date={latestYoY?.originalDate}
          dateFormatter={formatMonthLabel}
          format="percent"
          decimals={1}
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
                      { mode: 'yoy_chart', label: '前年比' },
                      { mode: 'yoy_table', label: '前年比（テーブル）' },
                    ]}
                  />

                  {/* 期間セレクター（グラフ表示時のみ） */}
                  {viewMode === 'yoy_chart' && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <Tooltip title="比較ページを開く">
                        <Button
                          icon={<AreaChartOutlined />}
                          onClick={() => window.open('/compare?s=japan_boj_lending', '_blank')}
                        >
                          データ比較
                        </Button>
                      </Tooltip>
                    </div>
                  )}

                  {/* コンテンツ表示 */}
                  {viewMode === 'yoy_table' && <LendingTable />}

                  {viewMode === 'yoy_chart' && (
                    <ZoomableChart
                      data={filteredYoYData}
                      dataKey="value"
                      color={COLORS.yoy}
                      name="貸出動向（前年比）"
                      height={450}
                      tickFormatter={formatPercentage}
                      tooltipFormatter={formatPercentage}
                      tooltipLabelFormatter={(dateStr) => {
                        const date = new Date(dateStr)
                        return `${date.getFullYear()}年${date.getMonth() + 1}月`
                      }}
                      xAxisTickFormatter={(dateStr) => {
                        const date = new Date(dateStr)
                        return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
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
          ]}
        />
      </ChartContainer>
    </div>
  )
}

export default BOJLendingChart
