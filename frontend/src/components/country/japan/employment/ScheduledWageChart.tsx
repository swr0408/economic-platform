/**
 * 所定内給与チャートコンポーネント（日本）- e-Stat版
 *
 * データソース: e-Stat 毎月勤労統計調査
 *
 * 表示:
 * - 所定内給与 前年比
 * - 一般 前年比
 * - パート 前年比
 * - パート時間当 前年比（所定内給与÷所定内労働時間）
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined, CalendarOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'
import type { JapanScheduledWageData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  NoDataMessage,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import {
  LATEST_VALUE_BOX_STYLE,
  TEXT_COLORS,
} from '../../usa/common/chartConstants'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// =============================================================================
// 型定義
// =============================================================================

interface ScheduledWageChartProps {
  data: JapanScheduledWageData | null
}

interface ChartDataPoint {
  date: string
  scheduled_wage: number | null
  general: number | null
  part_time_wage: number | null
  part_time_hourly: number | null
}

// グラフの色
const COLORS = {
  scheduled_wage: '#1890ff',  // 青：所定内給与
  general: '#52c41a',         // 緑：一般
  part_time_wage: '#fa8c16',  // オレンジ：パート
  part_time_hourly: '#722ed1', // 紫：パート時間当
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

// 値フォーマット関数
const formatValue = (value: number | null | undefined): string => {
  if (value === null || value === undefined) return '-'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

// 次回発表日時フォーマット関数
const formatNextRelease = (nextRelease: JapanScheduledWageData['next_release']): string | null => {
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

export default function ScheduledWageChart({ data }: ScheduledWageChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')

  // チャートデータに変換（4系列をマージ）
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const scheduledWageData = data.scheduled_wage?.data || []
    const generalData = data.general?.data || []
    const partTimeWageData = data.part_time_wage?.data || []
    const partTimeHourlyData = data.part_time_hourly?.data || []

    // 全ての日付を収集
    const dateSet = new Set<string>()
    scheduledWageData.forEach(d => dateSet.add(d.date))
    generalData.forEach(d => dateSet.add(d.date))
    partTimeWageData.forEach(d => dateSet.add(d.date))
    partTimeHourlyData.forEach(d => dateSet.add(d.date))

    const dates = Array.from(dateSet).sort()

    // 日付ごとにデータをマージ
    const scheduledWageMap = new Map(scheduledWageData.map(d => [d.date, d.value]))
    const generalMap = new Map(generalData.map(d => [d.date, d.value]))
    const partTimeWageMap = new Map(partTimeWageData.map(d => [d.date, d.value]))
    const partTimeHourlyMap = new Map(partTimeHourlyData.map(d => [d.date, d.value]))

    return dates.map(date => ({
      date,
      scheduled_wage: scheduledWageMap.get(date) ?? null,
      general: generalMap.get(date) ?? null,
      part_time_wage: partTimeWageMap.get(date) ?? null,
      part_time_hourly: partTimeHourlyMap.get(date) ?? null,
    }))
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    return filterByPeriod(chartData, currentPeriod, 2020)
  }, [chartData, currentPeriod])

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestScheduledWage = data?.scheduled_wage?.latest
  const latestGeneral = data?.general?.latest
  const latestPartTimeWage = data?.part_time_wage?.latest
  const latestPartTimeHourly = data?.part_time_hourly?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="所定内給与（e-Stat）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="所定内給与（e-Stat）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="scheduled-wage-chart">
      <ChartContainer
        title="所定内給与"
        showPeriodSelector={false}
        dataSource="厚生労働省"
        sourceUrl="https://www.mhlw.go.jp/toukei/list/30-1.html"
      >
        {/* 最新値表示（統合ボックス） */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          {/* 左側: 最新値 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {/* 日付 */}
            {latestScheduledWage?.date && (
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                {formatDate(latestScheduledWage.date)}
              </span>
            )}
            {/* 所定内給与 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>所定内給与:</span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.scheduled_wage }}>
                {formatValue(latestScheduledWage?.value)}
              </span>
            </div>
            {/* 一般 */}
            {latestGeneral && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>一般:</span>
                <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.general }}>
                  {formatValue(latestGeneral?.value)}
                </span>
              </div>
            )}
            {/* パート */}
            {latestPartTimeWage && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>パート:</span>
                <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.part_time_wage }}>
                  {formatValue(latestPartTimeWage?.value)}
                </span>
              </div>
            )}
            {/* パート時間当 */}
            {latestPartTimeHourly && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>パート時間当:</span>
                <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.part_time_hourly }}>
                  {formatValue(latestPartTimeHourly?.value)}
                </span>
              </div>
            )}
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
                  {/* 期間セレクター */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=jp_average_cash_earnings_yoy', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* チャート表示 */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'scheduled_wage', color: COLORS.scheduled_wage, name: '所定内給与', hide: false },
                      { dataKey: 'general', color: COLORS.general, name: '一般', hide: false },
                      { dataKey: 'part_time_wage', color: COLORS.part_time_wage, name: 'パート', hide: false },
                      { dataKey: 'part_time_hourly', color: COLORS.part_time_hourly, name: 'パート時間当', hide: false },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                    showZeroLine={true}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="jp_average_cash_earnings_yoy" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
