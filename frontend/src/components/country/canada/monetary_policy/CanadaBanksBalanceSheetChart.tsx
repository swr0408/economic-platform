/**
 * カナダ銀行バランスシートチャートコンポーネント（チャータード銀行）
 *
 * カナダのチャータード銀行のカナダドル資産合計の推移を表示
 *
 * データソース:
 * - Statistics Canada Table 10-10-0109-01
 *
 * 発表スケジュール:
 * - 月次
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
import type { CanadaBanksBalanceSheetData } from '../../../../hooks/useDashboardData'

interface CanadaBanksBalanceSheetChartProps {
  data: CanadaBanksBalanceSheetData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  main: '#1E90FF', // ドッジャーブルー（BOCのクリムゾンと区別）
}

export default function CanadaBanksBalanceSheetChart({ data }: CanadaBanksBalanceSheetChartProps) {
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
    return <LoadingChart title="カナダ銀行バランスシート" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="カナダ銀行バランスシート" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="canada-banks-balance-sheet-chart">
      <ChartContainer
        title="カナダ銀行バランスシート（チャータード銀行）"
        showPeriodSelector={false}
        dataSource="Statistics Canada"
        sourceUrl="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1010010901"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="カナダドル資産合計"
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
          <Tooltip title="比較ページを開く（カナダ銀行バランスシート）">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=canada_banks_balance_sheet', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* グラフ */}
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'value', color: COLORS.main, name: 'カナダドル資産合計' },
          ]}
          yAxisFormatter={(v) => `${(v / 1000000).toFixed(1)}T`}
          tooltipValueFormatter={(v) => `${v.toLocaleString()} M CAD`}
          xAxisFormatter={formatDateLabel}
          tooltipLabelFormatter={formatDateLabelFull}
          yDomain={['dataMin - 100000', 'dataMax + 100000']}
          showZeroLine={false}
        />
      </ChartContainer>
    </div>
  )
}
