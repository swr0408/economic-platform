/**
 * BOE OISフォワードカーブチャートコンポーネント
 *
 * Bank of EnglandのOISフォワードカーブ（1M-12M）を表示
 * 当日と前日の比較データを折れ線グラフで表示
 *
 * データソース:
 * - Bank of England Yield Curves ZIP file
 *
 * 更新スケジュール:
 * - 1日2回 16:00、3:00 JST
 */
import { useMemo } from 'react'
import { Line } from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'

// 型定義
import type { BOEOISCurveData } from '../../../../hooks/useDashboardData'

interface BOEOISCurveChartProps {
  data: BOEOISCurveData | null
  height?: number
}

interface ChartDataPoint {
  date: string
  value: number
  tenor: string
  tenorNum: number
  currentRate: number | null
  previousRate: number | null
  [key: string]: unknown
}

export default function BOEOISCurveChart({ data, height = 400 }: BOEOISCurveChartProps) {
  // チャートデータを変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.current?.data) return []

    const result: ChartDataPoint[] = []

    // 1M-12Mのデータを抽出
    for (let month = 1; month <= 12; month++) {
      const monthKey = `Month${month}`
      const currentRate = data.current?.data?.[monthKey] ?? null
      const previousRate = data.previous?.data?.[monthKey] ?? null

      result.push({
        date: `${month}M`,
        tenor: `${month}M`,
        tenorNum: month,
        value: currentRate ?? 0,
        currentRate,
        previousRate,
      })
    }

    return result.sort((a, b) => a.tenorNum - b.tenorNum)
  }, [data])

  const currentDate = data?.current?.date
  const previousDate = data?.previous?.date

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="OISカーブ (1M-12M)" />
  }

  if (chartData.length === 0) {
    return (
      <ChartContainer title="OISカーブ (1M-12M)" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#94a3b8' }}>
          データが見つかりませんでした
        </div>
      </ChartContainer>
    )
  }

  return (
    <div id="boe-ois-curve-chart">
      <ChartContainer
        title="OISカーブ (1M-12M)"
        showPeriodSelector={false}
        dataSource="Bank of England"
        sourceUrl="https://www.bankofengland.co.uk/statistics/yield-curves"
      >
        <ZoomableChart
          data={chartData}
          height={height}
          dataKey="currentRate"
          color="#1890ff"
          name={currentDate ? `${currentDate}` : '当日'}
          xAxisTickFormatter={(value) => value}
          tickFormatter={(value) => `${value.toFixed(3)}%`}
          tooltipFormatter={(value) => `${value.toFixed(3)}%`}
          domain={['dataMin - 0.05', 'dataMax + 0.05']}
          showZeroLine={false}
          showFiftyLine={false}
          enableDynamicTicks={true}
          hideMainLine={false}
          connectNulls={true}
        >
          {previousDate && (
            <Line
              type="monotone"
              dataKey="previousRate"
              stroke="#52c41a"
              strokeWidth={2}
              dot={false}
              name={previousDate}
              yAxisId="left"
              connectNulls={true}
              isAnimationActive={false}
            />
          )}
        </ZoomableChart>
      </ChartContainer>
    </div>
  )
}
