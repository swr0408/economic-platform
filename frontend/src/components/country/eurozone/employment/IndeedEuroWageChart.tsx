/**
 * Indeed賃金トラッカー（ユーロ圏）チャートコンポーネント
 *
 * Indeed GitHubから賃金成長データを取得し、表示
 *
 * データ:
 * - ドイツ (DE) - Posted Wage Growth YoY
 * - フランス (FR) - Posted Wage Growth YoY
 * - ユーロ圏 (EA) - Posted Wage Growth YoY
 *
 * データソース:
 * - Indeed Hiring Lab GitHub Repository
 *
 * 発表スケジュール:
 * - 不定期（データ更新時）
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import { CHART_COLORS, LATEST_VALUE_BOX_STYLE } from '../../usa/common/chartConstants'
import {
  usePeriodFiltering,
  useHiddenSeries,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import type { IndeedEuroWageData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface IndeedEuroWageChartProps {
  data: IndeedEuroWageData | null
}

// カラー設定
const COLORS = {
  germany: CHART_COLORS.primary,    // 青
  france: CHART_COLORS.positive,    // 緑
  euroArea: CHART_COLORS.orange,   // オレンジ
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function IndeedEuroWageChart({ data }: IndeedEuroWageChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // 3系列のデータをマージして1つのチャートデータに変換
  const chartData = useMemo(() => {
    if (!data) return []

    const germanyData = data.germany || []
    const franceData = data.france || []
    const euroAreaData = data.euro_area || []

    // 全日付を収集
    const allDates = new Set<string>()
    germanyData.forEach((d) => allDates.add(d.date))
    franceData.forEach((d) => allDates.add(d.date))
    euroAreaData.forEach((d) => allDates.add(d.date))

    // 日付順にソート
    const sortedDates = Array.from(allDates).sort(
      (a, b) => new Date(a).getTime() - new Date(b).getTime()
    )

    // 各日付に対してデータをマージ
    const germanyMap = new Map(germanyData.map((d) => [d.date, d.value]))
    const franceMap = new Map(franceData.map((d) => [d.date, d.value]))
    const euroAreaMap = new Map(euroAreaData.map((d) => [d.date, d.value]))

    return sortedDates.map((date) => ({
      date,
      germany: germanyMap.get(date) ?? null,
      france: franceMap.get(date) ?? null,
      euroArea: euroAreaMap.get(date) ?? null,
    }))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="Indeed賃金トラッカー（ユーロ圏）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="Indeed賃金トラッカー（ユーロ圏）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値を取得
  const germanyLatest = data.germany?.length > 0 ? data.germany[data.germany.length - 1] : null
  const franceLatest = data.france?.length > 0 ? data.france[data.france.length - 1] : null
  const euroAreaLatest = data.euro_area?.length > 0 ? data.euro_area[data.euro_area.length - 1] : null

  // 日付フォーマット
  const formatDate = (dateStr: string): string => {
    const date = new Date(dateStr)
    return `${date.getFullYear()}年${date.getMonth() + 1}月`
  }

  return (
    <div id="indeed-euro-wage-chart">
      <ChartContainer
        title="Indeed賃金トラッカー（ユーロ圏・前年比）"
        showPeriodSelector={false}
        dataSource="Indeed Hiring Lab"
        sourceUrl="https://www.hiringlab.org/jp/"
      >
        {/* 最新値表示（3系列） */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          {/* ドイツ */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 12,
                height: 12,
                backgroundColor: COLORS.germany,
                borderRadius: 2,
              }}
            />
            <span style={{ fontSize: 12, color: '#a0a0a0' }}>ドイツ</span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.germany }}>
              {germanyLatest?.value != null
                ? `${germanyLatest.value >= 0 ? '+' : ''}${germanyLatest.value.toFixed(1)}%`
                : '-'}
            </span>
          </div>

          {/* フランス */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 12,
                height: 12,
                backgroundColor: COLORS.france,
                borderRadius: 2,
              }}
            />
            <span style={{ fontSize: 12, color: '#a0a0a0' }}>フランス</span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.france }}>
              {franceLatest?.value != null
                ? `${franceLatest.value >= 0 ? '+' : ''}${franceLatest.value.toFixed(1)}%`
                : '-'}
            </span>
          </div>

          {/* ユーロ圏 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 12,
                height: 12,
                backgroundColor: COLORS.euroArea,
                borderRadius: 2,
              }}
            />
            <span style={{ fontSize: 12, color: '#a0a0a0' }}>ユーロ圏</span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.euroArea }}>
              {euroAreaLatest?.value != null
                ? `${euroAreaLatest.value >= 0 ? '+' : ''}${euroAreaLatest.value.toFixed(1)}%`
                : '-'}
            </span>
          </div>

          {/* 日付（右側に配置） */}
          <div style={{ marginLeft: 'auto', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'flex-end', fontSize: 11, color: '#8c8c8c' }}>
            {euroAreaLatest?.date && <div>{formatDate(euroAreaLatest.date)}</div>}
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
                  {/* 期間セレクタ + 比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=indeed_euro_wage_germany&s=indeed_euro_wage_france&s=indeed_euro_wage_euro_area', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'euroArea', color: COLORS.euroArea, name: 'ユーロ圏', hide: hiddenSeries.has('euroArea') },
                      { dataKey: 'germany', color: COLORS.germany, name: 'ドイツ', hide: hiddenSeries.has('germany') },
                      { dataKey: 'france', color: COLORS.france, name: 'フランス', hide: hiddenSeries.has('france') },
                    ]}
                    yAxisFormatter={(v) => `${v.toFixed(0)}%`}
                    tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                    yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                    showZeroLine={true}
                    onLegendClick={handleLegendClick}
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
