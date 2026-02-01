/**
 * マネタリーベースチャートコンポーネント
 *
 * スイス国立銀行（SNB）のマネタリーベースの推移を表示
 *
 * データソース:
 * - SNB Data Portal: https://data.snb.ch/
 *
 * 発表スケジュール:
 * - 週次（Weekly）- 週の最初の営業日 10:00（チューリッヒ時間）
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
import type { MonetaryBaseData } from '../../../../hooks/useDashboardData'

interface MonetaryBaseChartProps {
  data: MonetaryBaseData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  main: '#8B4513', // サドルブラウン（金融的な色合い）
}

export default function MonetaryBaseChart({ data }: MonetaryBaseChartProps) {
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
    defaultStartYear: 2000,
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
    return <LoadingChart title="マネタリーベース" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="マネタリーベース" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="monetary-base-chart">
      <ChartContainer
        title="マネタリーベース"
        showPeriodSelector={false}
        dataSource="Swiss National Bank"
        sourceUrl="https://data.snb.ch/en/topics/snb"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="マネタリーベース"
          value={latestValue?.value ? latestValue.value / 1000 : null}
          date={latestValue?.date}
          format="number"
          decimals={1}
          valueColor={COLORS.main}
          unit="B CHF"
          nextRelease={data.next_release ? { date: data.next_release } : null}
        />

        {/* コントロールバー */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, marginTop: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く（マネタリーベース）">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=monetary_base', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* グラフ */}
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'value', color: COLORS.main, name: 'マネタリーベース' },
          ]}
          yAxisFormatter={(v) => `${(v / 1000).toFixed(0)}B`}
          tooltipValueFormatter={(v) => `${(v / 1000).toFixed(1)}B CHF`}
          yDomain={['dataMin - 50000', 'dataMax + 50000']}
          showZeroLine={false}
        />
      </ChartContainer>
    </div>
  )
}
