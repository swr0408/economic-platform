/**
 * SNB当座預金チャートコンポーネント
 *
 * スイス国立銀行（SNB）への当座預金の推移を表示
 *
 * データソース:
 * - SNB Data Portal: https://data.snb.ch/
 *
 * 発表スケジュール:
 * - 不定期（週次程度で更新）
 */
import { useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

// 型定義
import type { SNBSightDepositsData } from '../../../../hooks/useDashboardData'

interface SNBSightDepositsChartProps {
  data: SNBSightDepositsData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  main: '#1E90FF', // ドジャーブルー
}

export default function SNBSightDepositsChart({ data }: SNBSightDepositsChartProps) {
  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement('default', {
    default: 'default',
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((item) => ({
      date: item.date,
      value: item.value,
    }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = useMemo(() => {
    if (!chartData.length) return null
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].value !== null) {
        return chartData[i]
      }
    }
    return null
  }, [chartData])

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="SNB当座預金" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="SNB当座預金" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="snb-sight-deposits-chart">
      <ChartContainer
        title="SNB当座預金"
        showPeriodSelector={false}
        dataSource="Swiss National Bank"
        sourceUrl="https://data.snb.ch/en/topics/snb"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="当座預金"
          value={latestValue?.value ? latestValue.value / 1000000 : null}
          date={latestValue?.date}
          format="number"
          decimals={0}
          valueColor={COLORS.main}
          unit="CHF"
          nextRelease={data.next_release ? { date: data.next_release } : null}
        />

        {/* コントロールバー */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, marginTop: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く（SNB当座預金）">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=snb_sight_deposits', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* グラフ */}
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'value', color: COLORS.main, name: '当座預金' },
          ]}
          yAxisFormatter={(v) => `${(v / 1000000).toFixed(0)}M`}
          tooltipValueFormatter={(v) => `${(v / 1000).toLocaleString()} CHF`}
          yDomain={['dataMin - 10000000', 'dataMax + 10000000']}
          showZeroLine={false}
        />
      </ChartContainer>
    </div>
  )
}
