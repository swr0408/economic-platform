/**
 * 有効求人倍率チャートコンポーネント（日本）
 *
 * データソース: 厚生労働省 一般職業紹介状況（FMPカレンダー経由）
 *
 * 表示:
 * - 有効求人倍率（倍）- 季節調整値
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined, CalendarOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'
import type { JapanJobOffersRatioData } from '../../../../hooks/useDashboardData'

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

interface JobOffersRatioChartProps {
  data: JapanJobOffersRatioData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
}

// グラフの色
const COLORS = {
  job_offers_ratio: '#52c41a',  // 緑：求人倍率
}

// =============================================================================
// ヘルパー関数
// =============================================================================

// 期間フィルタリング
const filterByPeriod = (
  data: ChartDataPoint[],
  period: PeriodValue,
  defaultStartYear: number = 2015
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
  return `${value.toFixed(2)}倍`
}

// 次回発表日時フォーマット関数
const formatNextRelease = (nextRelease: JapanJobOffersRatioData['next_release']): string | null => {
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

export default function JobOffersRatioChart({ data }: JobOffersRatioChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)

  // チャートデータに変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data || !data.job_offers_ratio) return []

    return data.job_offers_ratio.map(d => ({
      date: d.date,
      value: d.value,
    }))
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    return filterByPeriod(chartData, currentPeriod, 2015)
  }, [chartData, currentPeriod])

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="有効求人倍率（季節調整値）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="有効求人倍率（季節調整値）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="job-offers-ratio-chart">
      <ChartContainer
        title="有効求人倍率（季節調整値）"
        showPeriodSelector={false}
        dataSource="厚生労働省"
        sourceUrl="https://www.mhlw.go.jp/stf/houdou/0000212893_00001.html"
      >
        {/* 最新値表示（統合ボックス） */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          {/* 左側: 最新値 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {/* 日付 */}
            {latestValue?.date && (
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                {formatDate(latestValue.date)}
              </span>
            )}
            {/* 求人倍率 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>求人倍率:</span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.job_offers_ratio }}>
                {formatValue(latestValue?.value)}
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
                  {/* 期間セレクター */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=jp_job_offers_ratio', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* チャート表示 */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: COLORS.job_offers_ratio, name: '有効求人倍率', hide: false },
                    ]}
                    yAxisFormatter={(v) => `${v}倍`}
                    yDomain={['dataMin - 0.1', 'dataMax + 0.1']}
                    showZeroLine={false}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="jp_job_offers_ratio" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
