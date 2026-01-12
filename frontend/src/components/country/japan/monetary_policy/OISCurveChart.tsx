/**
 * JSCC OISカーブチャートコンポーネント
 *
 * JSCC (Japan Securities Clearing Corporation) のOISカーブ（1W〜1Y）を表示
 *
 * データソース:
 * - JSCC Settlement Rates PDF
 * - https://www.jpx.co.jp/jscc/en/cimhll0000000umu-att/SettlementRates_{YYYYMMDD}.pdf
 *
 * 発表スケジュール:
 * - 営業日毎、16:00 JST頃
 */
import { useEffect, useState } from 'react'
import { Typography, Card } from 'antd'
import { Line } from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'

// 共通モジュールのインポート
import { NoDataMessage } from '../../usa/common/ChartComponents'
import { DARK_THEME } from '../../usa/common/chartConstants'

const { Text } = Typography

// 型定義
interface OISDataPoint {
  tenor: string
  rate: number
}

interface OISDayData {
  date: string
  data: OISDataPoint[]
}

interface OISCurveData {
  current: OISDayData
  previous?: OISDayData
  last_updated: string
  cached?: boolean
  source?: string
  error?: string
}

interface OISChartDataPoint {
  date: string
  value: number
  tenor: string
  currentRate: number
  previousRate: number | null
  key: string
  [key: string]: unknown
}

interface OISCurveChartProps {
  height?: number
}

// Tenor sort order for proper display
const TENOR_ORDER = ['1W', '2W', '3W', '1M', '2M', '3M', '4M', '5M', '6M', '7M', '8M', '9M', '10M', '11M', '1Y']

/**
 * Format OIS curve data for chart display with both current and previous day
 * Merges data by tenor and creates separate fields for each day
 */
function formatOISCurveForChart(oisData: OISCurveData): OISChartDataPoint[] {
  const currentData = oisData.current.data
  const previousData = oisData.previous?.data || []

  // Create a map by tenor
  const tenorMap = new Map<string, { current?: number; previous?: number }>()

  currentData.forEach((point) => {
    tenorMap.set(point.tenor, { current: point.rate })
  })

  previousData.forEach((point) => {
    const existing = tenorMap.get(point.tenor)
    if (existing) {
      existing.previous = point.rate
    } else {
      tenorMap.set(point.tenor, { previous: point.rate })
    }
  })

  // Convert to array format for chart
  return Array.from(tenorMap.entries()).map(
    ([tenor, rates]): OISChartDataPoint => ({
      date: tenor, // Use tenor as 'date' for X-axis
      value: rates.current ?? 0, // Primary value (required by ZoomableChart)
      tenor: tenor,
      currentRate: rates.current ?? 0,
      previousRate: rates.previous ?? null,
      key: `${oisData.current.date}-${tenor}`,
    })
  )
}

/**
 * Sort chart data by tenor order
 */
function sortByTenor(data: OISChartDataPoint[]): OISChartDataPoint[] {
  return data.sort((a, b) => {
    const aIndex = TENOR_ORDER.indexOf(a.tenor)
    const bIndex = TENOR_ORDER.indexOf(b.tenor)
    return aIndex - bIndex
  })
}

/**
 * Fetch JSCC OIS Curve data from backend
 */
async function fetchOISCurve(): Promise<OISCurveData> {
  const response = await fetch('/api/japan/ois-curve')

  if (!response.ok) {
    throw new Error(`Failed to fetch OIS curve data: ${response.statusText}`)
  }

  const data: OISCurveData = await response.json()
  return data
}

export default function OISCurveChart({ height = 400 }: OISCurveChartProps) {
  const [oisData, setOisData] = useState<OISCurveData | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let isSubscribed = true

    const loadData = () => {
      setLoading(true)
      setError(null)

      fetchOISCurve()
        .then((data) => {
          if (isSubscribed) {
            setOisData(data)
          }
        })
        .catch((err) => {
          console.error('Failed to load OIS curve data:', err)
          if (isSubscribed) {
            setError('OISカーブデータの読み込みに失敗しました')
          }
        })
        .finally(() => {
          if (isSubscribed) {
            setLoading(false)
          }
        })
    }

    loadData()

    return () => {
      isSubscribed = false
    }
  }, [])

  const chartData = (() => {
    if (!oisData || !oisData.current || !oisData.current.data) return []
    const formatted = formatOISCurveForChart(oisData)
    return sortByTenor(formatted)
  })()

  if (loading && !oisData) {
    return <LoadingChart title="OISカーブ (1W-1Y)" message="OISカーブデータを読み込み中..." height={height} />
  }

  if (error && !oisData) {
    return (
      <ChartContainer title="OISカーブ (1W-1Y)" showPeriodSelector={false} showDataSource={false}>
        <Card style={{ height }}>
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
            <Text type="danger">{error}</Text>
          </div>
        </Card>
      </ChartContainer>
    )
  }

  if (chartData.length === 0) {
    return (
      <ChartContainer title="OISカーブ (1W-1Y)" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const currentDate = oisData?.current?.date
  const previousDate = oisData?.previous?.date
  const hasPrevious = previousDate && oisData?.previous?.data && oisData.previous.data.length > 0

  return (
    <div id="ois-curve-chart">
      <ChartContainer
        title="OISカーブ (1W-1Y)"
        dataSource="JSCC"
        sourceUrl="https://www.jpx.co.jp/jscc/toukei_irs.html"
        showPeriodSelector={false}
      >
        {/* 日付情報 */}
        <div
          style={{
            marginBottom: 12,
            fontSize: 13,
            color: DARK_THEME.textSecondary,
            display: 'flex',
            gap: 16,
            flexWrap: 'wrap',
          }}
        >
          <span>
            <span
              style={{ display: 'inline-block', width: 12, height: 3, backgroundColor: '#1890ff', marginRight: 6 }}
            />
            {currentDate}（当日）
          </span>
          {hasPrevious && (
            <span>
              <span
                style={{ display: 'inline-block', width: 12, height: 3, backgroundColor: '#52c41a', marginRight: 6 }}
              />
              {previousDate}（前営業日）
            </span>
          )}
        </div>

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
          showZeroLine={true}
          showFiftyLine={false}
          zeroLineValue={0}
          enableDynamicTicks={true}
          hideMainLine={false}
        >
          {hasPrevious && (
            <Line
              type="monotone"
              dataKey="previousRate"
              stroke="#52c41a"
              strokeWidth={2}
              dot={false}
              name={previousDate ? `${previousDate}` : '前営業日'}
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
