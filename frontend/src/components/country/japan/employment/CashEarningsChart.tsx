/**
 * 現金給与額チャートコンポーネント（日本）
 *
 * データソース: e-Stat 毎月勤労統計調査
 *
 * 表示:
 * - 現金給与総額 前年比 (%)
 *
 * 発表スケジュール:
 * - 1日〜10日: 速報値(p) 8:30 JST
 * - 17日〜月末: 確報値(r) 8:30 JST
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined, CalendarOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'
import type { JapanCashEarningsData } from '../../../../hooks/useDashboardData'

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

interface CashEarningsChartProps {
  data: JapanCashEarningsData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
}

// グラフの色
const COLORS = {
  positive: '#52c41a',  // 緑：プラス
  negative: '#f5222d',  // 赤：マイナス
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
const formatNextRelease = (nextRelease: JapanCashEarningsData['next_release']): string | null => {
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

export default function CashEarningsChart({ data }: CashEarningsChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)

  // チャートデータに変換（単一系列）
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []
    return data.data.map(d => ({
      date: d.date,
      value: d.value,
    }))
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    return filterByPeriod(chartData, currentPeriod, 2020)
  }, [chartData, currentPeriod])

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = data?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="現金給与額" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="現金給与額" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="cash-earnings-chart">
      <ChartContainer
        title="現金給与額"
        showPeriodSelector={false}
        dataSource="厚生労働省"
        sourceUrl="https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00450071"
      >
        {/* 最新値表示（統合ボックス） */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          {/* 左側: 最新値 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {/* 日付 */}
            {latest?.date && (
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                {formatDate(latest.date)}
              </span>
            )}
            {/* 前年比 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>前年比:</span>
              <span style={{
                fontSize: 20,
                fontWeight: 'bold',
                color: (latest?.value ?? 0) >= 0 ? COLORS.positive : COLORS.negative
              }}>
                {formatValue(latest?.value)}
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
                        onClick={() => window.open('/compare?s=jp_average_cash_earnings_yoy', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* チャート表示（線グラフ） */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: '#1890ff', name: '前年比', hide: false },
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
