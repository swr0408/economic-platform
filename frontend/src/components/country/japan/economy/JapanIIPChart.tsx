/**
 * 鉱工業生産チャートコンポーネント（日本）
 *
 * データソース: 経済産業省 (METI)
 * - 前月比: https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_gsm1j.xlsx (季節調整済み)
 * - 前年比: https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_gom1j.xlsx (原指数)
 * 更新: 月次（中旬頃）
 *
 * 表示:
 * - 前年比グラフ
 * - 前月比テーブル
 * - 前月比グラフ
 */
import { useState, useEffect, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined, CalendarOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import {
  useViewModePeriodManagement,
  useMonthlyTableData,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { TEXT_COLORS, LATEST_VALUE_BOX_STYLE } from '../../usa/common/chartConstants'
import { MonthlyTable } from '../../usa/common/MonthlyTable'

import {
  fetchJapanIIPData,
  fetchJapanIIPYoYData,
  formatIIPDate,
  type JapanIIPDataPoint,
  type JapanIIPYoYDataPoint,
  type NextRelease,
} from '../../../../api/japanIIPApi'

// =============================================================================
// 型定義
// =============================================================================

interface ChartDataPoint {
  date: string
  yoy: number | null
  mom: number | null
}

type ViewMode = 'yoy' | 'mom_table' | 'mom_chart'

// グラフの色
const COLORS = {
  yoy: '#1890ff',
  mom: '#52c41a',
}

// 次回発表日時のフォーマット
const formatNextRelease = (nextRelease: NextRelease | null | undefined): string | null => {
  if (!nextRelease) return null
  if (nextRelease.datetime_jst) {
    const dt = new Date(nextRelease.datetime_jst)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    const hours = dt.getHours().toString().padStart(2, '0')
    const minutes = dt.getMinutes().toString().padStart(2, '0')
    return `${month}/${day} ${hours}:${minutes}`
  }
  if (nextRelease.time_jst && nextRelease.date) {
    const dt = new Date(nextRelease.date)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    return `${month}/${day} ${nextRelease.time_jst}`
  }
  if (nextRelease.date) {
    const dt = new Date(nextRelease.date)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    return `${month}/${day}`
  }
  return null
}

// =============================================================================
// ヘルパー関数
// =============================================================================

// 期間フィルタリング
const filterByPeriod = (
  data: ChartDataPoint[],
  period: PeriodValue,
  defaultStartYear: number = 2018
): ChartDataPoint[] => {
  if (period === 'all') {
    return data
  }

  let cutoffDate: Date
  if (period === 'default') {
    cutoffDate = new Date(defaultStartYear, 0, 1)
  } else if (typeof period === 'number') {
    cutoffDate = new Date()
    cutoffDate.setFullYear(cutoffDate.getFullYear() - period)
  } else {
    cutoffDate = new Date(defaultStartYear, 0, 1)
  }

  return data.filter(item => {
    const itemDate = new Date(item.date)
    return itemDate >= cutoffDate
  })
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function JapanIIPChart() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [momData, setMomData] = useState<JapanIIPDataPoint[]>([])
  const [yoyData, setYoyData] = useState<JapanIIPYoYDataPoint[]>([])
  const [nextRelease, setNextRelease] = useState<NextRelease | null>(null)

  const [viewMode, setViewMode] = useState<ViewMode>('yoy')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom_table: 'default',
    mom_chart: 3,
  })

  // データ取得
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      setError(null)

      try {
        const [momResponse, yoyResponse] = await Promise.all([
          fetchJapanIIPData(),
          fetchJapanIIPYoYData(),
        ])

        if (momResponse.error) {
          setError(momResponse.error)
        } else {
          setMomData(momResponse.data)
          if (momResponse.next_release) {
            setNextRelease(momResponse.next_release)
          }
        }

        if (yoyResponse.error) {
          setError(yoyResponse.error)
        } else {
          setYoyData(yoyResponse.data)
        }
      } catch (err) {
        console.error('Error fetching IIP data:', err)
        setError('データの取得に失敗しました')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  // チャートデータに変換（YoYとMoMを結合）
  const chartData = useMemo<ChartDataPoint[]>(() => {
    // MoMデータをマップに変換
    const momMap = new Map<string, number | null>()
    for (const item of momData) {
      momMap.set(item.date, item.mom_change)
    }

    // YoYデータをマップに変換
    const yoyMap = new Map<string, number | null>()
    for (const item of yoyData) {
      // 2018年以前のデータを除外（YoY計算の基準年）
      const date = new Date(item.date)
      if (date.getFullYear() > 2018) {
        yoyMap.set(item.date, item.yoy_change)
      }
    }

    // 全ての日付を収集
    const allDates = new Set([...momMap.keys(), ...yoyMap.keys()])

    // 結合データを作成
    const combined: ChartDataPoint[] = []
    for (const date of allDates) {
      combined.push({
        date,
        yoy: yoyMap.get(date) ?? null,
        mom: momMap.get(date) ?? null,
      })
    }

    // 日付昇順でソート
    return combined.sort((a, b) => a.date.localeCompare(b.date))
  }, [momData, yoyData])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    return filterByPeriod(chartData, currentPeriod, 2010)
  }, [chartData, currentPeriod])

  // テーブル用データ（年別×月別のマトリックス）
  const momTableData = useMonthlyTableData(chartData, (item) => item.mom)

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestMom = momData.length > 0 ? momData[0] : null
  const latestYoy = yoyData.length > 0 ? yoyData[0] : null

  if (loading) {
    return <LoadingChart title="鉱工業生産（Industrial Production）" />
  }

  if (error) {
    return (
      <ChartContainer title="鉱工業生産（Industrial Production）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>
          {error}
        </div>
      </ChartContainer>
    )
  }

  if (!hasData) {
    return (
      <ChartContainer title="鉱工業生産（Industrial Production）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="japan-iip-chart">
      <ChartContainer
        title="鉱工業生産"
        showPeriodSelector={false}
        dataSource="経済産業省"
        sourceUrl="https://www.meti.go.jp/statistics/tyo/iip/"
      >
        {/* 最新値表示（統合ボックス） */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          {/* 左側: 最新値 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {(viewMode === 'yoy' ? latestYoy?.date : latestMom?.date) && (
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                {formatIIPDate(viewMode === 'yoy' ? latestYoy!.date : latestMom!.date)}
              </span>
            )}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                {viewMode === 'yoy' ? '前年比:' : '前月比:'}
              </span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: viewMode === 'yoy' ? COLORS.yoy : COLORS.mom }}>
                {(viewMode === 'yoy' ? latestYoy?.yoy_change : latestMom?.mom_change)?.toFixed(1) ?? '-'}%
              </span>
            </div>
          </div>

          {/* 右側: 次回発表 */}
          {nextRelease && formatNextRelease(nextRelease) && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 12,
              color: TEXT_COLORS.secondary,
            }}>
              <CalendarOutlined />
              <span>次回発表: {formatNextRelease(nextRelease)}</span>
            </div>
          )}
        </div>

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
                      { mode: 'yoy', label: '前年比' },
                      { mode: 'mom_table', label: '前月比テーブル' },
                      { mode: 'mom_chart', label: '前月比グラフ' },
                    ]}
                  />

                  {/* 期間セレクター */}
                  {(viewMode === 'yoy' || viewMode === 'mom_chart') && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <Tooltip title="比較ページを開く">
                        <Button
                          icon={<AreaChartOutlined />}
                          onClick={() => window.open(`/compare?s=${viewMode === 'yoy' ? 'japan_iip_yoy' : 'japan_iip_mom'}`, '_blank')}
                        >
                          データ比較
                        </Button>
                      </Tooltip>
                    </div>
                  )}

                  {/* コンテンツ表示 */}
                  {viewMode === 'mom_table' && <MonthlyTable data={momTableData} />}

                  {viewMode === 'yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'yoy', color: COLORS.yoy, name: '鉱工業生産（前年比）', hide: hiddenSeries.has('yoy') },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                      onLegendClick={handleLegendClick}
                    />
                  )}

                  {viewMode === 'mom_chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'mom', color: COLORS.mom, name: '鉱工業生産（前月比）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
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
