/**
 * 雇用形態別労働者過不足判断D.I.チャートコンポーネント（日本）
 *
 * データソース: 厚生労働省 労働経済動向調査
 * https://www.mhlw.go.jp/toukei/itiran/roudou/koyou/keizai/
 *
 * 表示:
 * - 正社員等 D.I.
 * - パートタイム D.I.
 *
 * 発表スケジュール: 四半期ごと（3月、6月、9月、12月）
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'
import type { JapanEmploymentTypeData } from '../../../../hooks/useDashboardData'

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

interface EmploymentTypeChartProps {
  data: JapanEmploymentTypeData | null
}

interface ChartDataPoint {
  date: string
  regular_employee: number | null
  part_time: number | null
}

// グラフの色
const COLORS = {
  regular_employee: '#1890ff',  // 青：正社員等
  part_time: '#722ed1',         // 紫：パートタイム
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

// 値フォーマット関数（D.I.は整数で符号付き表示）
const formatValue = (value: number | null | undefined): string => {
  if (value === null || value === undefined) return '-'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value}`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function EmploymentTypeChart({ data }: EmploymentTypeChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)

  // チャートデータに変換（2系列をマージ）
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const regularData = data.regular_employee?.data || []
    const partTimeData = data.part_time?.data || []

    // 全ての日付を収集
    const dateSet = new Set<string>()
    regularData.forEach(d => dateSet.add(d.date))
    partTimeData.forEach(d => dateSet.add(d.date))

    const dates = Array.from(dateSet).sort()

    // 日付ごとにデータをマージ
    const regularMap = new Map(regularData.map(d => [d.date, d.value]))
    const partTimeMap = new Map(partTimeData.map(d => [d.date, d.value]))

    return dates.map(date => ({
      date,
      regular_employee: regularMap.get(date) ?? null,
      part_time: partTimeMap.get(date) ?? null,
    }))
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    return filterByPeriod(chartData, currentPeriod, 2015)
  }, [chartData, currentPeriod])

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestRegular = data?.regular_employee?.latest
  const latestPartTime = data?.part_time?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="雇用形態別労働者過不足判断D.I." />
  }

  if (!hasData) {
    return (
      <ChartContainer title="雇用形態別労働者過不足判断D.I." showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="employment-type-chart">
      <ChartContainer
        title="雇用形態別労働者過不足判断D.I."
        showPeriodSelector={false}
        dataSource="厚生労働省"
        sourceUrl="https://www.mhlw.go.jp/toukei/list/43-1.html"
      >
        {/* 最新値表示（統合ボックス） */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          {/* 左側: 最新値 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {/* 日付 */}
            {latestRegular?.date && (
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                {formatDate(latestRegular.date)}
              </span>
            )}
            {/* 正社員等 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>正社員等:</span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.regular_employee }}>
                {formatValue(latestRegular?.value)}
              </span>
            </div>
            {/* パートタイム */}
            {latestPartTime && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>パートタイム:</span>
                <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.part_time }}>
                  {formatValue(latestPartTime?.value)}
                </span>
              </div>
            )}
          </div>
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
                        onClick={() => window.open('/compare?s=jp_employment_type_di_regular', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* チャート表示 */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'regular_employee', color: COLORS.regular_employee, name: '正社員等', hide: false },
                      { dataKey: 'part_time', color: COLORS.part_time, name: 'パートタイム', hide: false },
                    ]}
                    yAxisFormatter={(v) => `${v}`}
                    yDomain={['dataMin - 5', 'dataMax + 5']}
                    showZeroLine={true}
                  />
                </>
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
