/**
 * ECBマクロ経済予測チャートコンポーネント
 *
 * ECBスタッフ予測の主要マクロ経済指標を表示:
 * - GDP成長率予測
 * - インフレ率（HICP）予測
 * - 失業率予測
 * - コアインフレ予測
 * - 短期金利予測
 * - 民間消費予測
 * - 外需予測
 * - 賃金上昇率予測
 *
 * データソース:
 * - European Central Bank Staff Projections (ECB MPD)
 *
 * 発表スケジュール:
 * - 四半期ごと（3月・6月・9月・12月）
 * - ECB理事会での金融政策決定時に公表
 */
import { useState, useMemo } from 'react'
import { Button, Card } from 'antd'
import { LeftOutlined, RightOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import { NoDataMessage } from '../../usa/common/ChartComponents'
import { DARK_THEME } from '../../usa/common/chartConstants'

import type { ECBMacroProjectionsData, ECBProjectionDataPoint, ECBIndicatorData } from '../../../../hooks/useDashboardData'
import { formatProjectionDate, INDICATOR_CONFIGS, type IndicatorConfig } from '../../../../utils/eurozone/ecbMacroProjectionsApi'

interface ECBMacroProjectionsChartProps {
  data: ECBMacroProjectionsData | null
}

interface ChartDataPoint {
  date: string
  value: number
  previous?: number | null
  latest?: number | null
  [key: string]: unknown
}

// Convert vintage code to month name (e.g., "S25" -> "2025/9")
const getMonthFromVintage = (vintage: string): string => {
  if (!vintage || vintage.length < 2) return vintage

  const seasonCode = vintage.charAt(0)
  const year = '20' + vintage.substring(1)

  const seasonMonths: Record<string, string> = {
    'W': '3',   // Winter/March
    'G': '6',   // Spring/June
    'S': '9',   // Summer/September
    'A': '12'   // Autumn/December
  }

  const month = seasonMonths[seasonCode] || ''
  return `${year}/${month}`
}

export default function ECBMacroProjectionsChart({ data }: ECBMacroProjectionsChartProps) {
  const [currentIndicatorIndex, setCurrentIndicatorIndex] = useState(0)

  const currentIndicator: IndicatorConfig = INDICATOR_CONFIGS[currentIndicatorIndex]

  // Prepare chart data for current indicator
  const { annualChartData, quarterlyChartData, hasQuarterlyData } = useMemo(() => {
    if (!data?.indicators || !currentIndicator) {
      return { annualChartData: [], quarterlyChartData: [], hasQuarterlyData: false }
    }

    const indicatorData: ECBIndicatorData | undefined = data.indicators[currentIndicator.key]
    if (!indicatorData) {
      return { annualChartData: [], quarterlyChartData: [], hasQuarterlyData: false }
    }

    // Prepare annual data
    const annualLatest = indicatorData.annual_latest || []
    const annualPrevious = indicatorData.annual_previous || []

    const allAnnualDates = new Set<string>()
    annualLatest.forEach((p: ECBProjectionDataPoint) => allAnnualDates.add(p.date))
    annualPrevious.forEach((p: ECBProjectionDataPoint) => allAnnualDates.add(p.date))

    const annualDataMap: Record<string, ChartDataPoint> = {}
    Array.from(allAnnualDates).sort().forEach(date => {
      annualDataMap[date] = {
        date,
        value: 0,
        previous: null,
        latest: null
      }
    })

    annualPrevious.forEach((p: ECBProjectionDataPoint) => {
      if (annualDataMap[p.date]) {
        annualDataMap[p.date].previous = p.value
        annualDataMap[p.date].value = p.value || 0
      }
    })

    annualLatest.forEach((p: ECBProjectionDataPoint) => {
      if (annualDataMap[p.date]) {
        annualDataMap[p.date].latest = p.value
        annualDataMap[p.date].value = p.value || 0
      }
    })

    const annual = Object.values(annualDataMap).sort((a, b) => a.date.localeCompare(b.date))

    // Prepare quarterly data
    const quarterlyLatest = indicatorData.quarterly_latest || []
    const quarterlyPrevious = indicatorData.quarterly_previous || []

    // Check if quarterly data actually exists (not just empty arrays)
    const hasQuarterlyData = quarterlyLatest.length > 0 || quarterlyPrevious.length > 0

    const allQuarterlyDates = new Set<string>()
    quarterlyLatest.forEach((p: ECBProjectionDataPoint) => allQuarterlyDates.add(p.date))
    quarterlyPrevious.forEach((p: ECBProjectionDataPoint) => allQuarterlyDates.add(p.date))

    const quarterlyDataMap: Record<string, ChartDataPoint> = {}
    Array.from(allQuarterlyDates).sort().forEach(date => {
      quarterlyDataMap[date] = {
        date,
        value: 0,
        previous: null,
        latest: null
      }
    })

    quarterlyPrevious.forEach((p: ECBProjectionDataPoint) => {
      if (quarterlyDataMap[p.date]) {
        quarterlyDataMap[p.date].previous = p.value
        quarterlyDataMap[p.date].value = p.value || 0
      }
    })

    quarterlyLatest.forEach((p: ECBProjectionDataPoint) => {
      if (quarterlyDataMap[p.date]) {
        quarterlyDataMap[p.date].latest = p.value
        quarterlyDataMap[p.date].value = p.value || 0
      }
    })

    const quarterly = Object.values(quarterlyDataMap).sort((a, b) => a.date.localeCompare(b.date))

    return {
      annualChartData: annual,
      quarterlyChartData: quarterly,
      hasQuarterlyData
    }
  }, [data, currentIndicator])

  const formatValue = (value: number): string => {
    return `${value.toFixed(2)}%`
  }

  const formatDateLabel = (dateStr: string): string => {
    return formatProjectionDate(dateStr)
  }

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
    return <LoadingChart title="ECBマクロ経済予測" />
  }

  // No data state
  if (!data?.indicators) {
    return (
      <ChartContainer title="ECBマクロ経済予測" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const showAnnualChart = annualChartData.length > 0
  const showQuarterlyChart = hasQuarterlyData && quarterlyChartData.length > 0

  const latestVintage = data.metadata?.latest_vintage || ''
  const previousVintage = data.metadata?.previous_vintage || ''
  const latestMonth = getMonthFromVintage(latestVintage)
  const previousMonth = getMonthFromVintage(previousVintage)

  return (
    <div id="ecb-macro-projections-chart">
      <Card
        title="マクロ経済予測"
        style={{
          marginBottom: '24px',
          background: DARK_THEME.bgSecondary,
          borderColor: DARK_THEME.borderLight
        }}
        styles={{
          header: {
            background: DARK_THEME.bgTertiary,
            borderColor: DARK_THEME.borderLight,
            color: DARK_THEME.textPrimary
          },
          body: {
            background: DARK_THEME.bgSecondary
          }
        }}
      >
        {/* Navigation Controls */}
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: '20px',
          marginBottom: '20px',
          padding: '10px',
          backgroundColor: DARK_THEME.bgTertiary,
          borderRadius: '8px'
        }}>
          <Button
            icon={<LeftOutlined />}
            onClick={handlePrevious}
            size="large"
          />
          <div style={{
            textAlign: 'center',
            minWidth: '400px'
          }}>
            <div style={{
              fontSize: '18px',
              fontWeight: 'bold',
              marginBottom: '4px',
              color: DARK_THEME.textPrimary
            }}>
              {currentIndicator?.name_jp}
            </div>
            <div style={{
              fontSize: '12px',
              color: DARK_THEME.textSecondary,
              marginTop: '4px'
            }}>
              {currentIndicatorIndex + 1} / {INDICATOR_CONFIGS.length}
            </div>
          </div>
          <Button
            icon={<RightOutlined />}
            onClick={handleNext}
            size="large"
          />
        </div>

        {/* Annual Projections */}
        {showAnnualChart && (
          <ChartContainer
            title={`${currentIndicator?.name_jp}（年次）`}
            showDataSource={true}
            dataSource="European Central Bank (ECB)"
            sourceUrl="https://www.ecb.europa.eu/press/projections/html/index.en.html"
            handbookId="ecb-macro-projections"
          >
            <ZoomableChart
              data={annualChartData}
              dataKey="value"
              height={400}
              color="#1890ff"
              name="最新予測"
              tickFormatter={formatValue}
              tooltipFormatter={formatValue}
              xAxisTickFormatter={formatDateLabel}
              showZeroLine={true}
              connectNulls={true}
              hideMainLine={true}
              domain={['dataMin - 0.5', 'dataMax + 0.5']}
              additionalLines={[
                {
                  dataKey: 'latest',
                  color: '#1890ff',
                  name: `最新 ${latestMonth}`,
                  strokeWidth: 3
                },
                {
                  dataKey: 'previous',
                  color: '#ff7875',
                  name: `前回 ${previousMonth}`,
                  strokeWidth: 2
                }
              ]}
            />
          </ChartContainer>
        )}

        {showQuarterlyChart && <br />}

        {/* Quarterly Projections */}
        {showQuarterlyChart && (
          <ChartContainer
            title={`${currentIndicator?.name_jp}（四半期）`}
            showDataSource={true}
            dataSource="European Central Bank (ECB)"
          >
            <ZoomableChart
              data={quarterlyChartData}
              dataKey="value"
              height={400}
              color="#52c41a"
              name="最新予測"
              tickFormatter={formatValue}
              tooltipFormatter={formatValue}
              xAxisTickFormatter={formatDateLabel}
              showZeroLine={true}
              connectNulls={true}
              hideMainLine={true}
              domain={['dataMin - 0.1', 'dataMax + 0.1']}
              additionalLines={[
                {
                  dataKey: 'latest',
                  color: '#52c41a',
                  name: `最新 ${latestMonth}`,
                  strokeWidth: 3
                },
                {
                  dataKey: 'previous',
                  color: '#ffa940',
                  name: `前回 ${previousMonth}`,
                  strokeWidth: 2
                }
              ]}
            />
          </ChartContainer>
        )}

        {!showAnnualChart && !showQuarterlyChart && (
          <ChartContainer
            title="ECBマクロ経済予測"
            showDataSource={true}
            dataSource="European Central Bank (ECB)"
          >
            <div style={{ padding: '20px', textAlign: 'center', color: DARK_THEME.textSecondary }}>
              データがありません
            </div>
          </ChartContainer>
        )}
      </Card>
    </div>
  )
}
