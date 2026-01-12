/**
 * Eurex OISカーブチャートコンポーネント
 *
 * 3ヶ月ユーロSTR先物カーブを表示
 *
 * データソース:
 * - Eurex (Three-Month Euro STR Futures)
 *
 * 発表スケジュール:
 * - 毎営業日 20:00-20:10 JST（夏時間）/ 21:00-21:10 JST（冬時間）
 */
import { useMemo } from 'react'
import { Tooltip as RechartsTooltip } from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import { NoDataMessage } from '../../usa/common/ChartComponents'
import { DARK_THEME } from '../../usa/common/chartConstants'

// 型定義
import type { EurexOISData } from '../../../../hooks/useDashboardData'

interface EurexOISChartProps {
  data: EurexOISData | null
}

interface ChartDataPoint {
  date: string
  value: number
  contract: string
  settle: number
  previousValue?: number | null
  [key: string]: unknown
}

const formatDateLabel = (dateStr: string): string => {
  try {
    // DD/MM/YYYY形式からYYYY/MM形式に変換
    if (dateStr.includes('/')) {
      const parts = dateStr.split('/')
      if (parts.length === 3) {
        return `${parts[2]}/${parts[1]}`
      }
    }
    // YYYY-MM-DD形式からYYYY/MM形式に変換
    const [year, month] = dateStr.split('-')
    return `${year}/${month}`
  } catch {
    return dateStr
  }
}

export default function EurexOISChart({ data }: EurexOISChartProps) {
  // チャート用データに変換
  const chartData = useMemo((): ChartDataPoint[] => {
    if (!data || !data.labels || data.labels.length === 0) return []

    return data.labels.map((date, index) => ({
      date,
      value: data.values[index] ?? 0,
      contract: data.contracts[index] ?? '',
      settle: data.settle_values[index] ?? 0,
      previousValue: data.previous_values?.[index] ?? null
    }))
  }, [data])

  const formatTick = (value: number) => {
    return `${value.toFixed(2)}%`
  }

  // カスタムツールチップ
  interface TooltipProps {
    active?: boolean
    payload?: Array<{
      payload: ChartDataPoint
    }>
  }

  const CustomTooltip = ({ active, payload }: TooltipProps) => {
    if (!active || !payload || !payload[0]) return null

    const point = payload[0].payload
    const hasPrevious = point.previousValue !== null && point.previousValue !== undefined
    const change = hasPrevious ? point.value - (point.previousValue ?? 0) : null

    return (
      <div
        style={{
          backgroundColor: DARK_THEME.bgTertiary,
          border: `1px solid ${DARK_THEME.borderLight}`,
          borderRadius: 8,
          padding: '12px 16px',
          boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
        }}
      >
        <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
          {`限月: ${point.contract}`}
        </div>
        <div style={{ fontSize: 13, color: '#f1f5f9', marginBottom: 4 }}>
          {`清算値: ${point.settle.toFixed(4)}`}
        </div>
        <div style={{ fontSize: 13, color: '#52c41a', marginBottom: 4 }}>
          {`金利織り込み: ${point.value.toFixed(4)}%`}
        </div>
        {hasPrevious && (
          <>
            <div
              style={{
                marginTop: 8,
                borderTop: `1px solid ${DARK_THEME.borderLight}`,
                paddingTop: 8,
                fontSize: 13,
                color: '#999',
              }}
            >
              {`前日: ${(point.previousValue ?? 0).toFixed(4)}%`}
            </div>
            <div
              style={{
                fontSize: 13,
                color: change && change > 0 ? '#cf1322' : change && change < 0 ? '#3f8600' : '#666',
              }}
            >
              {`変化: ${change && change > 0 ? '+' : ''}${(change ?? 0).toFixed(4)}%`}
            </div>
          </>
        )}
      </div>
    )
  }

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="3ヶ月ユーロSTR先物カーブ" />
  }

  const hasData = chartData.length > 0

  if (!hasData) {
    return (
      <ChartContainer title="3ヶ月ユーロSTR先物カーブ" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="eurex-ois-chart">
      <ChartContainer
        title="3ヶ月ユーロSTR先物カーブ (直近12ヶ月)"
        showPeriodSelector={false}
        dataSource="Eurex"
        sourceUrl="https://www.eurex.com/ex-en/markets/int/mon/3m-euro-str-futures/estr/Three-Month-Euro-STR-Futures-3402480"
      >
        {/* 日付表示 */}
        <div style={{ marginBottom: 16, fontSize: 13, color: '#94a3b8' }}>
          {data.current_date && (
            <span>
              最新日: <strong style={{ color: '#52c41a' }}>{data.current_date}</strong>
            </span>
          )}
          {data.previous_date && (
            <span style={{ marginLeft: 16 }}>
              前日: <strong style={{ color: '#999' }}>{data.previous_date}</strong>
            </span>
          )}
        </div>

        <ZoomableChart
          data={chartData}
          dataKey="value"
          height={400}
          color="#52c41a"
          strokeWidth={2}
          name="最新"
          tickFormatter={formatTick}
          xAxisTickFormatter={formatDateLabel}
          showZeroLine={true}
          showFiftyLine={false}
          zeroLineValue={0}
          domain={['dataMin - 0.1', 'dataMax + 0.1']}
          hideLegend={false}
          showDefaultTooltip={false}
          additionalLines={[
            {
              dataKey: 'previousValue',
              color: '#999999',
              name: '前日',
              strokeWidth: 2
            }
          ]}
        >
          <RechartsTooltip content={<CustomTooltip />} />
        </ZoomableChart>
      </ChartContainer>
    </div>
  )
}
