/**
 * 実質賃金チャートコンポーネント（日本）- 2系列版
 *
 * データソース: e-Stat 毎月勤労統計調査
 *
 * 表示:
 * - 実質賃金 前年比（%）- 全事業所版
 * - 実質賃金 前年比（%）- 共通事業所版
 *
 * 発表スケジュール:
 * - 1日〜10日: 速報値(p) 8:30 JST
 * - 17日〜月末: 確報値(r) 8:30 JST
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined, CalendarOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'
import type { JapanRealWageData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  NoDataMessage,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import {
  LATEST_VALUE_BOX_STYLE,
  TEXT_COLORS,
} from '../../usa/common/chartConstants'

// =============================================================================
// 型定義
// =============================================================================

interface RealWageChartProps {
  data: JapanRealWageData | null
}

interface ChartDataPoint {
  date: string
  all: number | null
  common: number | null
}

// グラフの色
const COLORS = {
  all: '#1890ff',     // 青：全事業所版
  common: '#52c41a',  // 緑：共通事業所版
  positive: '#52c41a',
  negative: '#f5222d',
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
const formatNextRelease = (nextRelease: JapanRealWageData['next_release']): string | null => {
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

export default function RealWageChart({ data }: RealWageChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')

  // チャートデータに変換（2系列をマージ）
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const allData = data.all?.data || []
    const commonData = data.common?.data || []

    // 全ての日付を収集
    const dateSet = new Set<string>()
    allData.forEach(d => dateSet.add(d.date))
    commonData.forEach(d => dateSet.add(d.date))

    const dates = Array.from(dateSet).sort()

    // 日付ごとにデータをマージ
    const allMap = new Map(allData.map(d => [d.date, d.value]))
    const commonMap = new Map(commonData.map(d => [d.date, d.value]))

    return dates.map(date => ({
      date,
      all: allMap.get(date) ?? null,
      common: commonMap.get(date) ?? null,
    }))
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    return filterByPeriod(chartData, currentPeriod, 2020)
  }, [chartData, currentPeriod])

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestAll = data?.all?.latest
  const latestCommon = data?.common?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="実質賃金" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="実質賃金" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="real-wage-chart">
      <ChartContainer
        title="実質賃金"
        showPeriodSelector={false}
        dataSource="厚生労働省"
        sourceUrl="https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00450071"
      >
        {/* 最新値表示（統合ボックス） */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          {/* 左側: 最新値 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {/* 日付 */}
            {(latestAll?.date || latestCommon?.date) && (
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                {formatDate(latestAll?.date || latestCommon?.date || '')}
              </span>
            )}
            {/* 全事業所版 */}
            {latestAll && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>全事業所:</span>
                <span style={{
                  fontSize: 16,
                  fontWeight: 'bold',
                  color: COLORS.all
                }}>
                  {formatValue(latestAll?.value)}
                </span>
              </div>
            )}
            {/* 共通事業所版 */}
            {latestCommon && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>共通事業所:</span>
                <span style={{
                  fontSize: 16,
                  fontWeight: 'bold',
                  color: COLORS.common
                }}>
                  {formatValue(latestCommon?.value)}
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

        {/* 期間セレクター */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, marginTop: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=jp_real_wage_yoy', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* チャート表示（線グラフ） */}
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'all', color: COLORS.all, name: '全事業所', hide: false },
            { dataKey: 'common', color: COLORS.common, name: '共通事業所', hide: false },
          ]}
          yAxisFormatter={(v) => `${v}%`}
          yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
          showZeroLine={true}
        />
      </ChartContainer>
    </div>
  )
}
