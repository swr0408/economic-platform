/**
 * RBNZ MPS 経済見通しチャートコンポーネント
 *
 * RBNZ Monetary Policy Statement の予測データを表示:
 * - 政策金利（OCR）パス: 今回 vs 前回
 * - ヘッドラインCPI / Non-tradables / Tradables
 * - インフレ内訳（今回 vs 前回）
 * - 民間LCI賃金インフレ: 今回 vs 前回
 * - Output Gap: 今回 vs 前回
 * - 失業率: 今回 vs 前回
 * - OCR & 中立OCRスイート
 * - NZドル為替レート
 *
 * 指標を左右ボタンで切り替え（RBA SMP パターン）
 *
 * データソース:
 * - RBNZ MPS Data Pack
 * - https://www.rbnz.govt.nz/hub/publications/monetary-policy-statement
 */
import { useState, useMemo } from 'react'
import { Button, Card } from 'antd'
import { LeftOutlined, RightOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import { NoDataMessage } from '../../usa/common/ChartComponents'
import { DARK_THEME } from '../../usa/common/chartConstants'
import { usePeriodFiltering } from '../../usa/common/useChartData'

import type {
  NzMpsForecastData,
  NzMpsForecastPoint,
} from '../../../../hooks/useDashboardData'

interface NzEconomicForecastChartProps {
  data: NzMpsForecastData | null
}

interface ChartDataPoint {
  date: string
  value: number
  [key: string]: unknown
}

type IndicatorType = 'simple' | 'multi_series' | 'multi_latest_previous'

interface IndicatorConfig {
  key: string
  name_jp: string
  name_en: string
  type: IndicatorType
  unit: string
}

const INDICATOR_CONFIGS: IndicatorConfig[] = [
  { key: 'ocr', name_jp: '政策金利（OCR）パス', name_en: 'OCR Path', type: 'simple', unit: '%' },
  { key: 'gdp_qoq', name_jp: 'GDP前期比', name_en: 'GDP Quarterly % Change', type: 'simple', unit: '%' },
  { key: 'cpi_headline', name_jp: 'CPI（ヘッドライン / Non-tradables / Tradables）', name_en: 'Headline CPI', type: 'multi_series', unit: '%' },
  { key: 'inflation_components', name_jp: 'インフレ内訳（今回 vs 前回）', name_en: 'Inflation Components', type: 'multi_latest_previous', unit: '%' },
  { key: 'wage_inflation', name_jp: '民間LCI賃金インフレ', name_en: 'Private Sector LCI Wage Inflation', type: 'simple', unit: '%' },
  { key: 'output_gap', name_jp: 'Output Gap', name_en: 'Output Gap', type: 'simple', unit: '%' },
  { key: 'unemployment_rate', name_jp: '失業率', name_en: 'Unemployment Rate', type: 'simple', unit: '%' },
  { key: 'neutral_ocr', name_jp: 'OCR & 中立OCRスイート', name_en: 'OCR & Neutral OCR Suite', type: 'multi_series', unit: '%' },
]

// simple型の色
const LATEST_COLOR = '#00BFFF'
const PREVIOUS_COLOR = '#ff7875'

// multi_series型の色パレット
const MULTI_COLORS = ['#00BFFF', '#ff7875', '#52c41a', '#faad14', '#722ed1', '#13c2c2']

// multi_latest_previous型の色パレット（系列ごとにlatest実線/previous破線）
const MLP_COLORS = [
  { latest: '#00BFFF', previous: '#00BFFF' },
  { latest: '#ff7875', previous: '#ff7875' },
  { latest: '#52c41a', previous: '#52c41a' },
]

export default function NzEconomicForecastChart({ data }: NzEconomicForecastChartProps) {
  const [currentIndicatorIndex, setCurrentIndicatorIndex] = useState(0)
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>(10)

  const currentConfig = INDICATOR_CONFIGS[currentIndicatorIndex]

  // Build chart data and additional lines based on indicator type
  const { chartData, additionalLines } = useMemo(() => {
    if (!data?.indicators || !currentConfig) {
      return { chartData: [] as ChartDataPoint[], additionalLines: [] as any[] }
    }

    const indicatorData = (data.indicators as any)[currentConfig.key]
    if (!indicatorData) {
      return { chartData: [] as ChartDataPoint[], additionalLines: [] as any[] }
    }

    const latestPub = data.metadata?.latest_publication || '最新'
    const previousPub = data.metadata?.previous_publication || '前回'

    if (currentConfig.type === 'simple') {
      return buildSimpleChart(indicatorData, latestPub, previousPub)
    } else if (currentConfig.type === 'multi_series') {
      return buildMultiSeriesChart(indicatorData)
    } else if (currentConfig.type === 'multi_latest_previous') {
      return buildMultiLatestPreviousChart(indicatorData, latestPub, previousPub)
    }

    return { chartData: [] as ChartDataPoint[], additionalLines: [] as any[] }
  }, [data, currentConfig])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  const handlePrevious = () => {
    setCurrentIndicatorIndex((prev) =>
      prev > 0 ? prev - 1 : INDICATOR_CONFIGS.length - 1
    )
  }

  const handleNext = () => {
    setCurrentIndicatorIndex((prev) =>
      prev < INDICATOR_CONFIGS.length - 1 ? prev + 1 : 0
    )
  }

  if (data === null) {
    return <LoadingChart title="RBNZ 経済見通し" />
  }

  if (!data?.indicators) {
    return (
      <ChartContainer title="RBNZ 経済見通し" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const formatValue = (value: number): string => {
    if (currentConfig.unit === '%') return `${value.toFixed(2)}%`
    return value.toFixed(2)
  }

  return (
    <div id="economic-forecast">
      <Card
        title="RBNZ 経済見通し（MPS）"
        style={{
          marginBottom: '24px',
          background: DARK_THEME.bgSecondary,
          borderColor: DARK_THEME.borderLight,
        }}
        styles={{
          header: {
            background: DARK_THEME.bgTertiary,
            borderColor: DARK_THEME.borderLight,
            color: DARK_THEME.textPrimary,
          },
          body: {
            background: DARK_THEME.bgSecondary,
          },
        }}
      >
        {/* Navigation Controls */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            gap: '20px',
            marginBottom: '20px',
            padding: '10px',
            backgroundColor: DARK_THEME.bgTertiary,
            borderRadius: '8px',
          }}
        >
          <Button icon={<LeftOutlined />} onClick={handlePrevious} size="large" />
          <div style={{ textAlign: 'center', minWidth: '250px' }}>
            <div
              style={{
                fontSize: '18px',
                fontWeight: 'bold',
                marginBottom: '4px',
                color: DARK_THEME.textPrimary,
              }}
            >
              {currentConfig?.name_jp}
            </div>
            <div
              style={{
                fontSize: '12px',
                color: DARK_THEME.textSecondary,
                marginTop: '4px',
              }}
            >
              {currentIndicatorIndex + 1} / {INDICATOR_CONFIGS.length}
            </div>
          </div>
          <Button icon={<RightOutlined />} onClick={handleNext} size="large" />
        </div>

        {/* Period Selector */}
        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

        {/* Chart */}
        {filteredData.length > 0 ? (
          <ChartContainer
            title={currentConfig?.name_jp}
            showDataSource={true}
            dataSource="RBNZ"
            sourceUrl="https://www.rbnz.govt.nz/hub/publications/monetary-policy-statement"
          >
            <ZoomableChart
              data={filteredData}
              dataKey="value"
              height={400}
              color={LATEST_COLOR}
              name="value"
              tickFormatter={formatValue}
              tooltipFormatter={formatValue}
              tooltipLabelFormatter={(value) => String(value)}
              xAxisTickFormatter={(value) => String(value)}
              showZeroLine={currentConfig.key === 'output_gap' || currentConfig.key === 'gdp_qoq'}
              showFiftyLine={false}
              connectNulls={true}
              hideMainLine={true}
              domain={['dataMin - 0.3', 'dataMax + 0.3']}
              enableDynamicTicks={false}
              additionalLines={additionalLines}
            />
          </ChartContainer>
        ) : (
          <ChartContainer
            title={currentConfig?.name_jp}
            showDataSource={true}
            dataSource="RBNZ"
          >
            <div
              style={{
                padding: '20px',
                textAlign: 'center',
                color: DARK_THEME.textSecondary,
              }}
            >
              データがありません
            </div>
          </ChartContainer>
        )}
      </Card>
    </div>
  )
}

/**
 * simple型: latest vs previous の2系列
 */
function buildSimpleChart(
  indicatorData: { latest: NzMpsForecastPoint[]; previous: NzMpsForecastPoint[] },
  latestLabel: string,
  previousLabel: string,
) {
  const latestPoints = indicatorData.latest || []
  const previousPoints = indicatorData.previous || []

  const allDates = new Set<string>()
  latestPoints.forEach((p) => allDates.add(p.date))
  previousPoints.forEach((p) => allDates.add(p.date))

  const dataMap: Record<string, ChartDataPoint> = {}
  Array.from(allDates).forEach((date) => {
    dataMap[date] = { date, value: 0, latest: null, previous: null }
  })

  previousPoints.forEach((p) => {
    if (dataMap[p.date]) {
      dataMap[p.date].previous = p.value
      dataMap[p.date].value = p.value || 0
    }
  })

  latestPoints.forEach((p) => {
    if (dataMap[p.date]) {
      dataMap[p.date].latest = p.value
      dataMap[p.date].value = p.value || 0
    }
  })

  const chartData = Object.values(dataMap).sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
  )

  const additionalLines = [
    { dataKey: 'latest', color: LATEST_COLOR, name: `最新 ${latestLabel}`, strokeWidth: 3 },
    { dataKey: 'previous', color: PREVIOUS_COLOR, name: `前回 ${previousLabel}`, strokeWidth: 2 },
  ]

  return { chartData, additionalLines }
}

/**
 * multi_series型: 複数の独立した系列
 */
function buildMultiSeriesChart(
  indicatorData: {
    series: Record<string, NzMpsForecastPoint[]>
    series_config: { key: string; name: string }[]
  },
) {
  const allDates = new Set<string>()
  const configs = indicatorData.series_config || []

  configs.forEach((sc) => {
    const points = indicatorData.series[sc.key] || []
    points.forEach((p) => allDates.add(p.date))
  })

  const dataMap: Record<string, ChartDataPoint> = {}
  Array.from(allDates).forEach((date) => {
    const point: ChartDataPoint = { date, value: 0 }
    configs.forEach((sc) => {
      point[sc.key] = null
    })
    dataMap[date] = point
  })

  configs.forEach((sc) => {
    const points = indicatorData.series[sc.key] || []
    points.forEach((p) => {
      if (dataMap[p.date]) {
        dataMap[p.date][sc.key] = p.value
        if (p.value !== null) {
          dataMap[p.date].value = p.value
        }
      }
    })
  })

  const chartData = Object.values(dataMap).sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
  )

  const additionalLines = configs.map((sc, i) => ({
    dataKey: sc.key,
    color: MULTI_COLORS[i % MULTI_COLORS.length],
    name: sc.name,
    strokeWidth: 2,
  }))

  return { chartData, additionalLines }
}

/**
 * multi_latest_previous型: 複数系列 × latest/previous
 */
function buildMultiLatestPreviousChart(
  indicatorData: {
    series: Record<string, { latest: NzMpsForecastPoint[]; previous: NzMpsForecastPoint[] }>
    series_config: { key: string; name: string }[]
  },
  latestLabel: string,
  previousLabel: string,
) {
  const allDates = new Set<string>()
  const configs = indicatorData.series_config || []

  configs.forEach((sc) => {
    const seriesData = indicatorData.series[sc.key]
    if (seriesData) {
      seriesData.latest?.forEach((p) => allDates.add(p.date))
      seriesData.previous?.forEach((p) => allDates.add(p.date))
    }
  })

  const dataMap: Record<string, ChartDataPoint> = {}
  Array.from(allDates).forEach((date) => {
    const point: ChartDataPoint = { date, value: 0 }
    configs.forEach((sc) => {
      point[`${sc.key}_latest`] = null
      point[`${sc.key}_previous`] = null
    })
    dataMap[date] = point
  })

  configs.forEach((sc) => {
    const seriesData = indicatorData.series[sc.key]
    if (!seriesData) return

    seriesData.latest?.forEach((p) => {
      if (dataMap[p.date]) {
        dataMap[p.date][`${sc.key}_latest`] = p.value
        if (p.value !== null) dataMap[p.date].value = p.value
      }
    })

    seriesData.previous?.forEach((p) => {
      if (dataMap[p.date]) {
        dataMap[p.date][`${sc.key}_previous`] = p.value
        if (p.value !== null) dataMap[p.date].value = p.value
      }
    })
  })

  const chartData = Object.values(dataMap).sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
  )

  const additionalLines: any[] = []
  configs.forEach((sc, i) => {
    const colors = MLP_COLORS[i % MLP_COLORS.length]
    additionalLines.push({
      dataKey: `${sc.key}_latest`,
      color: colors.latest,
      name: `${sc.name} ${latestLabel}`,
      strokeWidth: 3,
    })
    additionalLines.push({
      dataKey: `${sc.key}_previous`,
      color: colors.previous,
      name: `${sc.name} ${previousLabel}`,
      strokeWidth: 1,
      strokeDasharray: '5 5',
    })
  })

  return { chartData, additionalLines }
}

