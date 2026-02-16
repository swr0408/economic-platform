/**
 * RBA SMP 経済予測チャートコンポーネント
 *
 * RBA Statement on Monetary Policyの予測データを表示:
 * - 政策金利 (Cash Rate)
 * - GDP
 * - 世帯消費 (Household Consumption)
 * - 雇用 (Employment)
 * - 失業率 (Unemployment Rate)
 * - CPI
 * - CPI トリム平均 (Trimmed Mean Inflation)
 *
 * 最新予測 vs 前回予測を2線で比較表示
 * 指標を左右ボタンで切り替え（ECBマクロ経済予測パターン）
 *
 * データソース:
 * - Reserve Bank of Australia (RBA)
 * - https://www.rba.gov.au/publications/smp/forecasts-archive.html
 */
import { useState, useMemo } from 'react'
import { Button, Card } from 'antd'
import { LeftOutlined, RightOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import { NoDataMessage } from '../../usa/common/ChartComponents'
import { DARK_THEME } from '../../usa/common/chartConstants'

import type { RbaSmpForecastData, RbaSmpIndicatorData, RbaSmpForecastPoint } from '../../../../hooks/useDashboardData'

interface RbaMonetaryPolicyChartProps {
  data: RbaSmpForecastData | null
}

interface ChartDataPoint {
  date: string
  value: number
  previous?: number | null
  latest?: number | null
  [key: string]: unknown
}

interface IndicatorConfig {
  key: keyof RbaSmpForecastData['indicators']
  name_jp: string
  name_en: string
  unit: string
}

const INDICATOR_CONFIGS: IndicatorConfig[] = [
  { key: 'cash_rate', name_jp: '政策金利', name_en: 'Cash Rate', unit: '%' },
  { key: 'gdp', name_jp: 'GDP', name_en: 'GDP', unit: '%' },
  { key: 'household_consumption', name_jp: '世帯消費', name_en: 'Household Consumption', unit: '%' },
  { key: 'employment', name_jp: '雇用', name_en: 'Employment', unit: '%' },
  { key: 'unemployment_rate', name_jp: '失業率', name_en: 'Unemployment Rate', unit: '%' },
  { key: 'cpi', name_jp: 'CPI', name_en: 'CPI', unit: '%' },
  { key: 'trimmed_mean', name_jp: 'CPI(トリム平均)', name_en: 'Trimmed Mean Inflation', unit: '%' },
]

export default function RbaMonetaryPolicyChart({ data }: RbaMonetaryPolicyChartProps) {
  const [currentIndicatorIndex, setCurrentIndicatorIndex] = useState(0)

  const currentIndicator = INDICATOR_CONFIGS[currentIndicatorIndex]

  // Prepare chart data for current indicator
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.indicators || !currentIndicator) return []

    const indicatorData: RbaSmpIndicatorData | undefined = data.indicators[currentIndicator.key]
    if (!indicatorData) return []

    const latestPoints = indicatorData.latest || []
    const previousPoints = indicatorData.previous || []

    // Merge latest and previous into a single dataset
    const allDates = new Set<string>()
    latestPoints.forEach((p: RbaSmpForecastPoint) => allDates.add(p.date))
    previousPoints.forEach((p: RbaSmpForecastPoint) => allDates.add(p.date))

    const dataMap: Record<string, ChartDataPoint> = {}
    Array.from(allDates).forEach(date => {
      dataMap[date] = {
        date,
        value: 0,
        previous: null,
        latest: null,
      }
    })

    previousPoints.forEach((p: RbaSmpForecastPoint) => {
      if (dataMap[p.date]) {
        dataMap[p.date].previous = p.value
        dataMap[p.date].value = p.value || 0
      }
    })

    latestPoints.forEach((p: RbaSmpForecastPoint) => {
      if (dataMap[p.date]) {
        dataMap[p.date].latest = p.value
        dataMap[p.date].value = p.value || 0
      }
    })

    // Sort by date (format: "Jun-2026", "Dec-2026", etc.)
    return Object.values(dataMap).sort((a, b) => {
      const dateA = parseSmpDate(a.date)
      const dateB = parseSmpDate(b.date)
      return dateA.getTime() - dateB.getTime()
    })
  }, [data, currentIndicator])

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

  // Loading state
  if (data === null) {
    return <LoadingChart title="RBA 経済予測" />
  }

  // No data state
  if (!data?.indicators) {
    return (
      <ChartContainer title="RBA 経済予測" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latestPub = data.metadata?.latest_publication || ''
  const previousPub = data.metadata?.previous_publication || ''

  const formatValue = (value: number): string => `${value.toFixed(2)}%`

  return (
    <div id="rba-monetary-policy-chart">
      <Card
        title="RBA 経済予測"
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
              {currentIndicator?.name_jp}
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

        {/* Chart */}
        {chartData.length > 0 ? (
          <ChartContainer
            title={currentIndicator?.name_jp}
            showDataSource={true}
            dataSource="Reserve Bank of Australia"
            sourceUrl="https://www.rba.gov.au/publications/smp/forecasts-archive.html"
          >
            <ZoomableChart
              data={chartData}
              dataKey="value"
              height={400}
              color="#00BFFF"
              name="最新予測"
              tickFormatter={formatValue}
              tooltipFormatter={formatValue}
              tooltipLabelFormatter={(value) => String(value)}
              xAxisTickFormatter={(value) => String(value)}
              showZeroLine={false}
              showFiftyLine={false}
              connectNulls={true}
              hideMainLine={true}
              domain={['dataMin - 0.3', 'dataMax + 0.3']}
              enableDynamicTicks={false}
              additionalLines={[
                {
                  dataKey: 'latest',
                  color: '#00BFFF',
                  name: `最新 ${latestPub}`,
                  strokeWidth: 3,
                },
                {
                  dataKey: 'previous',
                  color: '#ff7875',
                  name: `前回 ${previousPub}`,
                  strokeWidth: 2,
                },
              ]}
            />
          </ChartContainer>
        ) : (
          <ChartContainer
            title={currentIndicator?.name_jp}
            showDataSource={true}
            dataSource="Reserve Bank of Australia"
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
 * Parse SMP date format (e.g., "Jun-2026") to Date object for sorting
 */
function parseSmpDate(dateStr: string): Date {
  try {
    const months: Record<string, number> = {
      Jan: 0, Feb: 1, Mar: 2, Apr: 3, May: 4, Jun: 5,
      Jul: 6, Aug: 7, Sep: 8, Oct: 9, Nov: 10, Dec: 11,
    }
    const parts = dateStr.split('-')
    if (parts.length === 2) {
      const monthNum = months[parts[0]]
      const year = parseInt(parts[1], 10)
      if (monthNum !== undefined && !isNaN(year)) {
        return new Date(year, monthNum, 1)
      }
    }
  } catch {
    // fallback
  }
  return new Date(0)
}
