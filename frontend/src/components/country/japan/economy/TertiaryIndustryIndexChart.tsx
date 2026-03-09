/**
 * 第三次産業活動指数チャートコンポーネント（日本）
 *
 * データソース: 経済産業省 (METI)
 * - 前月比: https://www.meti.go.jp/statistics/tyo/sanzi/result/excel/b2020_ksmj.xlsx (季節調整済み)
 * - 前年比: https://www.meti.go.jp/statistics/tyo/sanzi/result/excel/b2020_komj.xlsx (原指数)
 * 更新: 月次（中旬頃）
 *
 * 表示:
 * - 前年比グラフ
 * - 前月比テーブル
 * - 前月比グラフ
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined, CalendarOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
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
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// =============================================================================
// 型定義
// =============================================================================

interface TertiaryIndustryDataPoint {
  date: string
  mom?: number | null
  yoy?: number | null
}

interface NextRelease {
  date?: string
  time_jst?: string
  datetime_jst?: string
}

interface ApiResponse {
  data: TertiaryIndustryDataPoint[]
  latest?: TertiaryIndustryDataPoint | null
  next_release?: NextRelease | null
  cached?: boolean
  source?: string
  last_updated?: string
}

interface ChartDataPoint {
  date: string
  yoy: number | null
  mom: number | null
}

type DataKind = 'yoy' | 'mom'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
]
type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// グラフの色
const COLORS = {
  yoy: '#722ed1',
  mom: '#13c2c2',
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

// 日付フォーマット
const formatDate = (dateStr: string): string => {
  const date = new Date(dateStr)
  const year = date.getFullYear()
  const month = date.getMonth() + 1
  return `${year}年${month}月`
}

// =============================================================================
// API関数
// =============================================================================

const fetchTertiaryIndustryData = async (): Promise<ApiResponse> => {
  const response = await fetch('/api/japan/tertiary-industry-index')
  if (!response.ok) {
    throw new Error('Failed to fetch tertiary industry index data')
  }
  return response.json()
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

export default function TertiaryIndustryIndexChart() {
  const [dataKind, setDataKind] = useState<DataKind>('mom')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 10,
    mom: 3,
  })

  // データ取得
  const { data: response, isLoading, error } = useQuery<ApiResponse>({
    queryKey: ['japan-tertiary-industry-index'],
    queryFn: fetchTertiaryIndustryData,
    staleTime: 24 * 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
    refetchOnWindowFocus: false,
  })

  // チャートデータに変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!response?.data) return []

    // 日付昇順でソート
    const sorted = [...response.data].sort((a, b) => a.date.localeCompare(b.date))

    return sorted.map(item => ({
      date: item.date,
      yoy: item.yoy ?? null,
      mom: item.mom ?? null,
    }))
  }, [response?.data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    return filterByPeriod(chartData, currentPeriod, 2010)
  }, [chartData, currentPeriod])

  // テーブル用データ（年別×月別のマトリックス）
  const momTableData = useMonthlyTableData(chartData, (item) => item.mom)

  const hasData = chartData.length > 0

  // 最新値を取得（データは降順でAPIから返ってくる）
  const latestData = response?.latest || (response?.data?.length ? response.data[0] : null)

  if (isLoading) {
    return <LoadingChart title="第三次産業活動指数（Tertiary Industry Index）" />
  }

  if (error) {
    return (
      <ChartContainer title="第三次産業活動指数（Tertiary Industry Index）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>
          データの取得に失敗しました
        </div>
      </ChartContainer>
    )
  }

  if (!hasData) {
    return (
      <ChartContainer title="第三次産業活動指数（Tertiary Industry Index）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="japan-tertiary-industry-index-chart">
      <ChartContainer
        title="第三次産業活動指数"
        showPeriodSelector={false}
        dataSource="経済産業省"
        sourceUrl="https://www.meti.go.jp/statistics/tyo/sanzi/"
      >
        {/* 最新値表示（統合ボックス） */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          {/* 左側: 最新値 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {latestData?.date && (
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                {formatDate(latestData.date)}
              </span>
            )}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                {dataKind === 'yoy' ? '前年比:' : '前月比:'}
              </span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: dataKind === 'yoy' ? COLORS.yoy : COLORS.mom }}>
                {(dataKind === 'yoy' ? latestData?.yoy : latestData?.mom)?.toFixed(1) ?? '-'}%
              </span>
            </div>
          </div>

          {/* 右側: 次回発表 */}
          {response?.next_release && formatNextRelease(response.next_release) && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 12,
              color: TEXT_COLORS.secondary,
            }}>
              <CalendarOutlined />
              <span>次回発表: {formatNextRelease(response.next_release)}</span>
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(`/compare?s=${dataKind === 'yoy' ? 'japan_tertiary_industry_yoy' : 'japan_tertiary_industry_mom'}`, '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {dataKind === 'mom' && (
                    <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                  )}

                  {/* コンテンツ表示 */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && <MonthlyTable data={momTableData} />}

                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'yoy', color: COLORS.yoy, name: '第三次産業活動指数（前年比）', hide: hiddenSeries.has('yoy') },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        onLegendClick={handleLegendClick}
                      />
                    </>
                  )}

                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'mom', color: COLORS.mom, name: '第三次産業活動指数（前月比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                      />
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="japan_tertiary_industry" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
