import { useState, useMemo } from 'react'
import { Line } from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { NFIBCapexData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { usePeriodFiltering, formatDateLabel, type PeriodType } from '../common/useChartData'
import { NoDataMessage } from '../common/ChartComponents'

interface NFIBCapexChartProps {
  data: NFIBCapexData | null
}

interface ChartDataPoint {
  date: string
  value: number
  capex3MA: number | null
  [key: string]: string | number | null | undefined
}

// 3期移動平均を計算する関数（後方MA）
const calculate3MA = (data: ChartDataPoint[]): ChartDataPoint[] => {
  return data.map((point, index) => {
    // 最初の2ポイントはnull
    if (index < 2) {
      return {
        ...point,
        capex3MA: null,
      }
    }

    // 前2期 + 前1期 + 当期 の平均
    const capex3MA = (data[index - 2].value + data[index - 1].value + point.value) / 3

    return {
      ...point,
      capex3MA,
    }
  })
}

export default function NFIBCapexChart({ data }: NFIBCapexChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')

  // データを日付昇順にソートして3MA計算
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    const sorted = [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        value: item.value,
        capex3MA: null as number | null,
      }))

    return calculate3MA(sorted)
  }, [data])

  // 期間フィルタリング（デフォルト5年前から）
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: new Date().getFullYear() - 5,
  })

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="NFIB中小企業設備投資計画" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="NFIB中小企業設備投資計画" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const formatValue = (value: number) => {
    return value.toFixed(1)
  }

  // グラフの色
  const RAW_COLOR = '#fca5a5' // 薄い赤
  const MA_COLOR = '#dc2626' // 濃い赤

  return (
    <div id="nfib-capex-chart">
      <ChartContainer
        title="NFIB中小企業設備投資計画"
        showPeriodSelector={false}
        dataSource="NFIB"
        sourceUrl="https://www.nfib.com/surveys/small-business-economic-trends/"
      >
        {/* 最新値表示 */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 12,
            padding: '12px 16px',
            background: '#f5f5f5',
            borderRadius: 8,
          }}
        >
          <div>
            <span style={{ fontSize: 12, color: '#666' }}>最新値: </span>
            {data.latest && (
              <>
                <span
                  style={{
                    fontSize: 20,
                    fontWeight: 'bold',
                    color: MA_COLOR,
                  }}
                >
                  {formatValue(data.latest.value)}%
                </span>
                <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>
                  ({formatDateLabel(data.latest.date)})
                </span>
              </>
            )}
          </div>
          <div style={{ fontSize: 11, color: '#888', textAlign: 'right' }}>
            {data.next_release && <div>次回発表: {data.next_release.date}</div>}
            <div>毎月第2火曜日発表</div>
          </div>
        </div>

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color={RAW_COLOR}
          name="設備投資計画"
          height={450}
          tickFormatter={formatValue}
          tooltipFormatter={formatValue}
          tooltipLabelFormatter={formatDateLabel}
          xAxisTickFormatter={formatDateLabel}
          enableDynamicTicks={true}
          showZeroLine={false}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={false}
          strokeWidth={1.5}
        >
          <Line
            type="monotone"
            dataKey="capex3MA"
            stroke={MA_COLOR}
            name="設備投資計画(3か月平均)"
            dot={false}
            strokeWidth={2}
            yAxisId="left"
            isAnimationActive={false}
          />
        </ZoomableChart>
      </ChartContainer>
    </div>
  )
}
