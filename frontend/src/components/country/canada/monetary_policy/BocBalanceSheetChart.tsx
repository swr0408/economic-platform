/**
 * BOCバランスシートチャートコンポーネント
 *
 * カナダ中央銀行（BOC）のバランスシート（総資産）の推移を表示
 *
 * データソース:
 * - Statistics Canada Table 10-10-0136-01
 *
 * 発表スケジュール:
 * - 週次（水曜日時点のデータ）
 * - 発表時刻: 金曜 14:30 ET（土曜 04:30 JST 冬 / 03:30 JST 夏）
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
  formatDateLabel,
  formatDateLabelFull,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

// 型定義
import type { BocBalanceSheetData } from '../../../../hooks/useDashboardData'

interface BocBalanceSheetChartProps {
  data: BocBalanceSheetData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  main: '#DC143C', // カナダカラー（クリムゾン）
}

export default function BocBalanceSheetChart({ data }: BocBalanceSheetChartProps) {
  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement('default', {
    default: 10,
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
    defaultStartYear: 2015,
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
    return <LoadingChart title="BOCバランスシート" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="BOCバランスシート" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="boc-balance-sheet-chart">
      <ChartContainer
        title="BOCバランスシート"
        showPeriodSelector={false}
        dataSource="Statistics Canada"
        sourceUrl="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1010013601"
        handbookId="central-bank-balance-sheet"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="総資産"
          value={latestValue?.value}
          date={latestValue?.date}
          format="number"
          decimals={0}
          valueColor={COLORS.main}
          unit="M CAD"
        />

        {/* コントロールバー */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, marginTop: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く（BOCバランスシート）">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=boc_balance_sheet', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* グラフ */}
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'value', color: COLORS.main, name: '総資産' },
          ]}
          yAxisFormatter={(v) => `${(v / 1000).toFixed(0)}B`}
          tooltipValueFormatter={(v) => `${v.toLocaleString()} M CAD`}
          xAxisFormatter={formatDateLabel}
          tooltipLabelFormatter={formatDateLabelFull}
          yDomain={['dataMin - 20000', 'dataMax + 20000']}
          showZeroLine={false}
        />
      </ChartContainer>
    </div>
  )
}
