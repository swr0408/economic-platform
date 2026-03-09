/**
 * 実質消費支出チャートコンポーネント（日本）
 *
 * データソース: 総務省統計局（家計調査）
 * - e-Stat API + FMP経由でDBに蓄積
 *
 * 表示:
 * - 前年比グラフ
 * - 前月比テーブル
 * - 前月比グラフ
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined, CalendarOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'
import type { ConsumptionExpenditureData, ConsumptionExpenditureNextRelease } from '../../../../hooks/useDashboardData'

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
import {
  LATEST_VALUE_BOX_STYLE,
  TEXT_COLORS,
} from '../../usa/common/chartConstants'
import { MonthlyTable } from '../../usa/common/MonthlyTable'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// =============================================================================
// 型定義
// =============================================================================

interface ConsumptionExpenditureChartProps {
  data: ConsumptionExpenditureData | null
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
  yoy: '#1890ff',
  mom: '#52c41a',
}

// =============================================================================
// ヘルパー関数
// =============================================================================

// 期間フィルタリング
const filterByPeriod = (
  data: ChartDataPoint[],
  period: PeriodValue,
  defaultStartYear: number = 2020
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

// 日付フォーマット関数
const formatDate = (dateStr: string) => {
  const date = new Date(dateStr)
  return `${date.getFullYear()}年${(date.getMonth() + 1).toString().padStart(2, '0')}月`
}

// 次回発表日時フォーマット関数
const formatNextRelease = (nextRelease: ConsumptionExpenditureNextRelease | null | undefined): string | null => {
  if (!nextRelease) return null

  // datetime_jstがある場合はそれを使用
  if (nextRelease.datetime_jst) {
    const dt = new Date(nextRelease.datetime_jst)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    const hours = dt.getHours().toString().padStart(2, '0')
    const minutes = dt.getMinutes().toString().padStart(2, '0')
    return `${month}/${day} ${hours}:${minutes}`
  }

  // time_jstがある場合
  if (nextRelease.date && nextRelease.time_jst) {
    const dt = new Date(nextRelease.date)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    return `${month}/${day} ${nextRelease.time_jst}`
  }

  // dateのみの場合
  if (nextRelease.date) {
    const dt = new Date(nextRelease.date)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    return `${month}/${day}`
  }

  return null
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function ConsumptionExpenditureChart({ data }: ConsumptionExpenditureChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 20,
    mom: 3,
  })

  // YoYとMoMデータをマージしてチャートデータに変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const yoyData = data.yoy?.data || []
    const momData = data.mom?.data || []

    // 全日付を収集
    const allDates = new Set<string>()
    yoyData.forEach((d) => allDates.add(d.date))
    momData.forEach((d) => allDates.add(d.date))

    // 日付順にソート
    const sortedDates = Array.from(allDates).sort(
      (a, b) => new Date(a).getTime() - new Date(b).getTime()
    )

    // 各日付に対してデータをマージ
    const yoyMap = new Map(yoyData.map((d) => [d.date, d.value]))
    const momMap = new Map(momData.map((d) => [d.date, d.value]))

    return sortedDates.map((date) => ({
      date,
      yoy: yoyMap.get(date) ?? null,
      mom: momMap.get(date) ?? null,
    }))
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    return filterByPeriod(chartData, currentPeriod, 2020)
  }, [chartData, currentPeriod])

  // テーブル用データ（年別×月別のマトリックス）
  const momTableData = useMonthlyTableData(chartData, (item) => item.mom)

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestYoy = data?.yoy?.latest
  const latestMom = data?.mom?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="実質消費支出（家計調査）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="実質消費支出（家計調査）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="consumption-expenditure-chart">
      <ChartContainer
        title="実質消費支出（家計調査）"
        showPeriodSelector={false}
        dataSource="総務省統計局"
        sourceUrl="https://www.stat.go.jp/data/kakei/"
      >
        {/* 最新値表示（統合ボックス） */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          {/* 左側: 最新値 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {/* 日付 */}
            {(dataKind === 'yoy' ? latestYoy?.date : latestMom?.date) && (
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                {formatDate(dataKind === 'yoy' ? latestYoy!.date : latestMom!.date)}
              </span>
            )}
            {/* 値 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                {dataKind === 'yoy' ? '前年比:' : '前月比:'}
              </span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: dataKind === 'yoy' ? COLORS.yoy : COLORS.mom }}>
                {(dataKind === 'yoy' ? latestYoy?.value : latestMom?.value)?.toFixed(1) ?? '-'}%
              </span>
            </div>
          </div>

          {/* 右側: 次回発表 */}
          {data?.next_release && formatNextRelease(data.next_release) && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 12,
              color: TEXT_COLORS.secondary,
            }}>
              <CalendarOutlined />
              <span>次回発表: {formatNextRelease(data.next_release)}</span>
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
                        onClick={() => window.open(`/compare?s=${dataKind === 'yoy' ? 'jp_household_spending_yoy' : 'jp_household_spending_mom'}`, '_blank')}
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
                          { dataKey: 'yoy', color: COLORS.yoy, name: '実質消費支出（前年比）', hide: hiddenSeries.has('yoy') },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        onLegendClick={handleLegendClick}
                        showZeroLine={true}
                      />
                    </>
                  )}

                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'mom', color: COLORS.mom, name: '実質消費支出（前月比）' },
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
                <MarketImpactTab indicatorId="jp_household_spending_yoy" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
