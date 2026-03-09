/**
 * スイス名目賃金上昇率 チャートコンポーネント
 *
 * BFS（スイス連邦統計局）から名目賃金上昇率データを取得し、表示
 *
 * データ:
 * - Nominal Wage Growth（名目賃金上昇率）
 * - 四半期データ（前年同期比）
 *
 * データソース:
 * - BFS (Federal Statistical Office)
 *
 * 発表スケジュール:
 * - FMPマッピングなし（BFSアジェンダ/RSSから週次チェック）
 */
import { useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

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

import type { CHNominalWageGrowthData } from '../../../../hooks/useDashboardData'

interface ChNominalWageGrowthChartProps {
  data: CHNominalWageGrowthData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  wage: '#FF8C00', // オレンジ
}

export default function ChNominalWageGrowthChart({ data }: ChNominalWageGrowthChartProps) {
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

  if (data === null) {
    return <LoadingChart title="スイス名目賃金上昇率" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="スイス名目賃金上昇率" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ch-nominal-wage-growth-chart">
      <ChartContainer
        title="名目賃金上昇率"
        showPeriodSelector={false}
        dataSource="BFS (Federal Statistical Office)"
        sourceUrl="https://www.bfs.admin.ch/bfs/en/home/statistics/work-income/wages-income-employment-labour-costs.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="名目賃金上昇率（前年同期比）"
          value={latestValue?.value}
          date={latestValue?.date}
          format="percent"
          decimals={2}
          valueColor={COLORS.wage}
          nextRelease={data.next_release}
        />

        {/* FMPマッピングがないため、マーケットインパクトタブは追加しない */}

        {/* コントロールバー */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8, marginTop: 16 }}>
          <Tooltip title="比較ページを開く（スイス名目賃金上昇率）">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=ch_nominal_wage_growth', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 期間選択 */}
        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

        {/* グラフ */}
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'value', color: COLORS.wage, name: '名目賃金上昇率' },
          ]}
          yAxisFormatter={(v) => `${v}%`}
          tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
          yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
          showZeroLine={true}
        />
      </ChartContainer>
    </div>
  )
}
