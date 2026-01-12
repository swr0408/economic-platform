/**
 * BSI Comprehensive Chart Component
 * 法人企業景気予測調査 包括チャート
 * Reusable component for displaying any BSI sheet and period type
 */

import { useEffect, useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import { type PeriodValue } from '../../../common/PeriodSelector'
import {
  fetchBSIComprehensiveChart,
  getPeriodTypeDisplayName,
  type SheetName,
  type PeriodType,
} from '../../../../utils/japan/bsiApi'

interface ChartDataPoint {
  date: string
  value: number
  large_all_industries: number | null
  large_manufacturing: number | null
  large_non_manufacturing: number | null
  medium_all_industries: number | null
  small_all_industries: number | null
  [key: string]: unknown
}

interface BSIComprehensiveChartProps {
  sheetName: SheetName
  periodType: PeriodType
  chartTitle?: string
  description?: string
}

const DEFAULT_START_DATE = '2010-Q1'

const parseQuarterDate = (dateStr: string): Date | null => {
  try {
    const date = new Date(dateStr)
    return date
  } catch {
    return null
  }
}

const formatQuarterLabel = (dateStr: string): string => {
  try {
    const date = new Date(dateStr)
    const year = date.getFullYear() % 100
    const month = date.getMonth() + 1
    const quarter = Math.ceil(month / 3)
    return `'${year.toString().padStart(2, '0')} Q${quarter}`
  } catch {
    return dateStr
  }
}

const filterByPeriod = <T extends { date: string }>(
  data: T[],
  period: PeriodValue,
  defaultStart = DEFAULT_START_DATE
) => {
  if (period === 'all') {
    return data
  }

  const cutoff =
    period === 'default'
      ? (() => {
          const match = defaultStart.match(/^(\d{4})-Q(\d)$/)
          if (match) {
            const year = parseInt(match[1])
            const quarter = parseInt(match[2])
            const month = (quarter - 1) * 3
            return new Date(year, month, 1)
          }
          return new Date(defaultStart)
        })()
      : (() => {
          const years = typeof period === 'number' ? period : 0
          const d = new Date()
          d.setFullYear(d.getFullYear() - years)
          return d
        })()

  if (!cutoff) return data

  return data.filter(({ date }) => {
    const parsed = parseQuarterDate(date)
    return parsed && parsed >= cutoff
  })
}

export default function BSIComprehensiveChart({
  sheetName,
  periodType,
  chartTitle,
  description,
}: BSIComprehensiveChartProps) {
  const [rawData, setRawData] = useState<ChartDataPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>('default')
  const [sheetTitle, setSheetTitle] = useState<string>('')

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await fetchBSIComprehensiveChart(sheetName, periodType)

        setSheetTitle(response.sheet_title)

        // Transform data for chart
        const chartData: ChartDataPoint[] = response.chart_data.dates.map((date, index) => ({
          date,
          value: response.chart_data.large_all_industries[index] ?? 0,
          large_all_industries: response.chart_data.large_all_industries[index],
          large_manufacturing: response.chart_data.large_manufacturing[index],
          large_non_manufacturing: response.chart_data.large_non_manufacturing[index],
          medium_all_industries: response.chart_data.medium_all_industries[index],
          small_all_industries: response.chart_data.small_all_industries[index],
        }))

        setRawData(chartData)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'データの取得に失敗しました')
        console.error('Error loading BSI data:', err)
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [sheetName, periodType])

  const filteredData = useMemo(() => {
    return filterByPeriod(rawData, selectedPeriod)
  }, [rawData, selectedPeriod])

  const title =
    chartTitle || `法人企業景気予測調査 ${sheetTitle}BSI（企業規模別）- ${getPeriodTypeDisplayName(periodType)}`

  if (loading) {
    return <LoadingChart title={title} />
  }

  if (error) {
    return (
      <ChartContainer title={title} showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>{error}</div>
      </ChartContainer>
    )
  }

  if (filteredData.length === 0) {
    return (
      <ChartContainer title={title} showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>データがありません</div>
      </ChartContainer>
    )
  }

  return (
    <ChartContainer
      title={title}
      selectedPeriod={selectedPeriod}
      onPeriodChange={setSelectedPeriod}
      dataSource="e-Stat（財務省）"
    >
      {description && <div style={{ marginBottom: '16px', fontSize: '14px', color: '#666' }}>{description}</div>}
      <ZoomableChart
        data={filteredData}
        dataKey="large_all_industries"
        height={450}
        color="#1890ff"
        strokeWidth={2.5}
        name="大企業 全産業"
        showZeroLine={true}
        zeroLineValue={0}
        connectNulls={true}
        enableDynamicTicks={true}
        initialHiddenLines={['medium_all_industries', 'small_all_industries']}
        tooltipFormatter={(value: number) => `${value.toFixed(1)}`}
        tooltipLabelFormatter={(label: string) => {
          const date = new Date(label)
          const year = date.getFullYear()
          const month = date.getMonth() + 1
          const quarter = Math.ceil(month / 3)
          return `${year} Q${quarter}`
        }}
        xAxisTickFormatter={formatQuarterLabel}
        yAxisLabel="BSI (ポイント)"
        domain={['dataMin - 5', 'dataMax + 5']}
        additionalLines={[
          {
            dataKey: 'large_manufacturing',
            color: '#52c41a',
            name: '大企業 製造業',
            strokeWidth: 2.5,
          },
          {
            dataKey: 'large_non_manufacturing',
            color: '#fa8c16',
            name: '大企業 非製造業',
            strokeWidth: 2.5,
          },
          {
            dataKey: 'medium_all_industries',
            color: '#722ed1',
            name: '中堅企業 全産業',
            strokeWidth: 2,
          },
          {
            dataKey: 'small_all_industries',
            color: '#eb2f96',
            name: '中小企業 全産業',
            strokeWidth: 2,
          },
        ]}
      />
    </ChartContainer>
  )
}
