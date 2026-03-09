/**
 * BOEインフレ期待調査（中央値）チャートコンポーネント
 *
 * データ:
 * - Q2a: 今後12ヶ月（next_12_months）
 * - Q2b: その後12ヶ月（following_12_months）
 * - Q2c: 5年先（five_years）
 *
 * 表示モード:
 * - 折れ線グラフ: 3系列を同時表示
 *
 * データソース:
 * - BOE Inflation Attitudes Survey Excel (Long-run file)
 *
 * 発表スケジュール:
 * - 四半期毎（3月、6月、9月、12月の7日〜17日頃）
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip as AntTooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useHiddenSeries,
  formatDateLabel,
  formatDateLabelJP,
} from '../../usa/common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import type { BOEInflationAttitudesData } from '../../../../hooks/useDashboardData'

interface BOEInflationAttitudesChartProps {
  data: BOEInflationAttitudesData | null
}

interface ChartDataPoint {
  date: string
  next_12_months: number | null
  following_12_months: number | null
  five_years: number | null
  [key: string]: unknown
}

type ViewMode = 'chart'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = []

// グラフの色
const COLORS = {
  next_12_months: '#e74c3c',      // 今後12ヶ月 - 赤
  following_12_months: '#f39c12', // その後12ヶ月 - オレンジ
  five_years: '#3498db',          // 5年先 - 青
}

// 系列名
const SERIES_NAMES = {
  next_12_months: '今後12ヶ月',
  following_12_months: 'その後12ヶ月',
  five_years: '5年先',
}

export default function BOEInflationAttitudesChart({ data }: BOEInflationAttitudesChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('chart')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    chart: 10,
  })

  // propsのデータをチャート用に変換（全系列をマージ）
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.series) return []

    const dateMap = new Map<string, ChartDataPoint>()

    const initPoint = (date: string): ChartDataPoint => ({
      date,
      next_12_months: null,
      following_12_months: null,
      five_years: null,
    })

    // 今後12ヶ月
    if (data.series.next_12_months?.data) {
      data.series.next_12_months.data.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, initPoint(point.date))
        }
        dateMap.get(point.date)!.next_12_months = point.value
      })
    }

    // その後12ヶ月
    if (data.series.following_12_months?.data) {
      data.series.following_12_months.data.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, initPoint(point.date))
        }
        dateMap.get(point.date)!.following_12_months = point.value
      })
    }

    // 5年先
    if (data.series.five_years?.data) {
      data.series.five_years.data.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, initPoint(point.date))
        }
        dateMap.get(point.date)!.five_years = point.value
      })
    }

    return Array.from(dateMap.values()).sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (chartData.length === 0) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  // 次回発表（四半期：日付が特定できないためラベルのみ）
  const nextReleaseInfo = {
    date: '',
    label: '3、6、9、12月 7日〜17日頃',
  }

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="インフレ期待調査（中央値）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="インフレ期待調査（中央値）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latest) return []

    const items = []
    if (latest.next_12_months !== null) {
      items.push({
        label: '今後12ヶ月',
        value: `${latest.next_12_months.toFixed(1)}%`,
        color: COLORS.next_12_months,
      })
    }
    if (latest.following_12_months !== null) {
      items.push({
        label: 'その後12ヶ月',
        value: `${latest.following_12_months.toFixed(1)}%`,
        color: COLORS.following_12_months,
      })
    }
    if (latest.five_years !== null) {
      items.push({
        label: '5年先',
        value: `${latest.five_years.toFixed(1)}%`,
        color: COLORS.five_years,
      })
    }
    return items
  }

  // データ比較ページを開く
  const handleCompare = () => {
    window.open('/compare?s=uk_boe_inflation_attitudes_12m&s=uk_boe_inflation_attitudes_5y', '_blank')
  }

  return (
    <div id="uk-boe-inflation-attitudes-chart">
      <ChartContainer
        title="インフレ期待調査（中央値）"
        showPeriodSelector={false}
        dataSource="BOE"
        sourceUrl="https://www.bankofengland.co.uk/search#?cludoquery=Ipsos%20Inflation%20Attitudes%20Survey&cludopage=1&cludorefurl=https%3A%2F%2Fwww.bankofengland.co.uk%2Finflation-attitudes-survey%2F2025%2Ffebruary-2025&cludorefpt=Bank%20of%20England%2FIpsos%20Inflation%20Attitudes%20Survey%20-%20February%202025%20%7C%20Bank%20of%20England&cludoinputtype=standard"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latest?.date}
          nextRelease={nextReleaseInfo}
        />

        {/* ビューモード切り替え */}
        <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />

        {/* 折れ線グラフ */}
        {viewMode === 'chart' && (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
              <AntTooltip title="比較ページを開く">
                <Button
                  icon={<AreaChartOutlined />}
                  onClick={handleCompare}
                >
                  データ比較
                </Button>
              </AntTooltip>
            </div>
            <StandardLineChart
              data={filteredData}
              lines={[
                {
                  dataKey: 'next_12_months',
                  color: COLORS.next_12_months,
                  name: SERIES_NAMES.next_12_months,
                  hide: hiddenSeries.has('next_12_months'),
                },
                {
                  dataKey: 'following_12_months',
                  color: COLORS.following_12_months,
                  name: SERIES_NAMES.following_12_months,
                  hide: hiddenSeries.has('following_12_months'),
                },
                {
                  dataKey: 'five_years',
                  color: COLORS.five_years,
                  name: SERIES_NAMES.five_years,
                  hide: hiddenSeries.has('five_years'),
                },
              ]}
              xAxisFormatter={formatDateLabel}
              yAxisFormatter={(v) => `${v.toFixed(1)}%`}
              tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
              tooltipLabelFormatter={formatDateLabelJP}
              onLegendClick={handleLegendClick}
              yDomain={['dataMin - 0.2', 'dataMax + 0.2']}
            />
          </>
        )}
      </ChartContainer>
    </div>
  )
}
