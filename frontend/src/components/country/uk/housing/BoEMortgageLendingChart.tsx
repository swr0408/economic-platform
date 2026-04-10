/**
 * 住宅ローン承認件数チャートコンポーネント
 *
 * データ:
 * - 住宅ローン承認件数（Total gross mortgage lending）
 *
 * 表示モード:
 * - 折れ線グラフ: 時系列データ
 *
 * データソース:
 * - CSV: Bank of England統計データベース（Series: LPMVTVX）
 *
 * 発表スケジュール:
 * - 月次（毎月28日～翌月4日頃）
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip as AntTooltip, Tabs } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabel,
  formatDateLabelJP,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import type { BoEMortgageLendingData } from '../../../../hooks/useDashboardData'
import type { PeriodValue } from '../../../common/PeriodSelector'

interface BoEMortgageLendingChartProps {
  data: BoEMortgageLendingData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  value: '#1890ff', // 青
}

// 系列名
const SERIES_NAMES = {
  value: '住宅ローン承認件数',
}

export default function BoEMortgageLendingChart({ data }: BoEMortgageLendingChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map(point => ({
      date: point.date,
      value: point.value,
    }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = data?.latest
  const nextRelease = data?.next_release ? { date: data.next_release } : null

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="住宅ローン承認件数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="住宅ローン承認件数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latest || latest.value === null || latest.value === undefined) return []

    // 値をk単位でフォーマット（例: 25000 → 25.0k）
    const formattedValue = (latest.value / 1000).toFixed(1)

    return [
      {
        label: '承認件数',
        value: `${formattedValue}k`,
        color: '#1890ff',
      },
    ]
  }

  // データ比較ページを開く
  const handleCompare = () => {
    window.open('/compare?s=uk_boe_mortgage_lending', '_blank')
  }

  return (
    <div id="uk-boe-mortgage-lending-chart">
      <ChartContainer
        title="住宅ローン承認件数"
        showPeriodSelector={false}
        dataSource="Bank of England"
        sourceUrl="https://www.bankofengland.co.uk/statistics"
        handbookId="boe-mortgage-lending"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latest?.date}
          nextRelease={nextRelease}
        />

        <Tabs
          defaultActiveKey="chart"
          items={[
            {
              key: 'chart',
              label: '時系列',
              children: (
                <>
                  {/* 期間選択とデータ比較ボタン */}
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

                  {/* 折れ線グラフ */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      {
                        dataKey: 'value',
                        color: COLORS.value,
                        name: SERIES_NAMES.value,
                      },
                    ]}
                    xAxisFormatter={formatDateLabel}
                    yAxisFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                    tooltipValueFormatter={(v) => `${v.toLocaleString()} (${(v / 1000).toFixed(1)}k)`}
                    tooltipLabelFormatter={formatDateLabelJP}
                    yDomain={['dataMin - 5000', 'dataMax + 5000']}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="boe_mortgage_lending" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
