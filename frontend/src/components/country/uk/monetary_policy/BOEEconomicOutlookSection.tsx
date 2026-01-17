import { useState, useMemo } from 'react'
import { Button, Card, Empty, Spin } from 'antd'
import { LeftOutlined, RightOutlined } from '@ant-design/icons'
import { DARK_THEME } from '../../usa/common/chartConstants'
import type {
  BOEMarketExpectationsData,
  BOECPIProjectionsData,
  BOEGDPForecastData,
  BOEUnemploymentForecastData,
  BOEServicesInflationData,
  BOEWageGrowthData,
  BOEAverageWeeklyEarningsData,
  BOEUnitWageCostsData,
  BOEInflationExpectationsData,
  BOEBankRateNextRelease,
} from '../../../../hooks/useDashboardData'
import BOEMarketExpectationsChart from './BOEMarketExpectationsChart'
import BOECPIProjectionsChart from './BOECPIProjectionsChart'
import BOEGDPForecastChart from './BOEGDPForecastChart'
import BOEUnemploymentForecastChart from './BOEUnemploymentForecastChart'
import BOEServicesInflationChart from './BOEServicesInflationChart'
import BOEWageGrowthChart from './BOEWageGrowthChart'
import BOEAverageWeeklyEarningsChart from './BOEAverageWeeklyEarningsChart'
import BOEUnitWageCostsChart from './BOEUnitWageCostsChart'
import BOEInflationExpectationsChart from './BOEInflationExpectationsChart'

interface BOEEconomicOutlookSectionProps {
  marketExpectationsData: BOEMarketExpectationsData | null
  cpiProjectionsData: BOECPIProjectionsData | null
  gdpForecastData: BOEGDPForecastData | null
  unemploymentForecastData: BOEUnemploymentForecastData | null
  servicesInflationData: BOEServicesInflationData | null
  wageGrowthData: BOEWageGrowthData | null
  averageWeeklyEarningsData: BOEAverageWeeklyEarningsData | null
  unitWageCostsData: BOEUnitWageCostsData | null
  inflationExpectationsData: BOEInflationExpectationsData | null
  isLoading?: boolean
}

interface ChartConfig {
  key: string
  label: string
  hasData: boolean
}

// Format next release date to Japanese
const formatNextRelease = (nextRelease: BOEBankRateNextRelease | null | undefined): string => {
  if (!nextRelease?.date) return ''

  try {
    const date = new Date(nextRelease.date)
    const year = date.getFullYear()
    const month = date.getMonth() + 1
    const day = date.getDate()

    let result = `${year}年${month}月${day}日`

    // Add JST time if available
    if (nextRelease.time_jst) {
      result += ` ${nextRelease.time_jst}`
    }

    return result
  } catch {
    return nextRelease.date
  }
}

/**
 * BOE経済見通しセクション
 * カルーセル形式で複数のチャートを表示
 */
export default function BOEEconomicOutlookSection({
  marketExpectationsData,
  cpiProjectionsData,
  gdpForecastData,
  unemploymentForecastData,
  servicesInflationData,
  wageGrowthData,
  averageWeeklyEarningsData,
  unitWageCostsData,
  inflationExpectationsData,
  isLoading = false,
}: BOEEconomicOutlookSectionProps) {
  const [currentChartIndex, setCurrentChartIndex] = useState(0)

  // Get next release date from any available data source
  const nextReleaseInfo = useMemo(() => {
    // All economic outlook data uses the same MPR release date
    const sources = [
      marketExpectationsData?.next_release,
      cpiProjectionsData?.next_release,
      gdpForecastData?.next_release,
      unemploymentForecastData?.next_release,
      servicesInflationData?.next_release,
      wageGrowthData?.next_release,
      averageWeeklyEarningsData?.next_release,
      unitWageCostsData?.next_release,
      inflationExpectationsData?.next_release,
    ]

    // Return the first available next_release
    for (const source of sources) {
      if (source?.date) {
        return source
      }
    }
    return null
  }, [
    marketExpectationsData,
    cpiProjectionsData,
    gdpForecastData,
    unemploymentForecastData,
    servicesInflationData,
    wageGrowthData,
    averageWeeklyEarningsData,
    unitWageCostsData,
    inflationExpectationsData,
  ])

  const nextReleaseText = formatNextRelease(nextReleaseInfo)

  // 基本仕様（常設）のみ表示
  // 1. 政策金利（Bank Rate 前提パス）
  // 2. CPI（総合）見通し
  // 3. GDP成長率 見通し
  // 4. 失業率 見通し
  // 5. サービスインフレ（基調/粘着性）
  // 6. 賃金（足元トラッカー）
  // 7. 平均週間賃金（AWE）見通し
  // 8. 単位賃金コスト（UWC）見通し
  // 9. インフレ期待（家計/企業）
  // ※ CPI構成項目（37. Short-term inflation）は2025年11月以降の拡張データのため除外
  // ※ CPI寄与度は分解粒度が号で変わりやすいため除外
  const charts: ChartConfig[] = [
    {
      key: 'market-expectations',
      label: '政策金利 見通し',
      hasData: !!marketExpectationsData?.latest || !!marketExpectationsData?.previous,
    },
    {
      key: 'gdp-forecast',
      label: 'GDP成長率 見通し',
      hasData: (gdpForecastData?.table_data?.length ?? 0) > 0,
    },
    {
      key: 'unemployment-forecast',
      label: '失業率 見通し',
      hasData: (unemploymentForecastData?.table_data?.length ?? 0) > 0,
    },
    {
      key: 'cpi-projections',
      label: 'インフレ 見通し',
      hasData: (cpiProjectionsData?.table_data?.length ?? 0) > 0,
    },
    {
      key: 'services-inflation',
      label: 'サービスインフレ（基調）',
      hasData: !!servicesInflationData?.services_inflation?.data,
    },
    {
      key: 'inflation-expectations',
      label: 'インフレ期待（家計/企業）',
      hasData: !!inflationExpectationsData?.inflation_expectations?.data,
    },
    {
      key: 'average-weekly-earnings',
      label: '平均週間賃金（AWE）見通し',
      hasData: !!averageWeeklyEarningsData?.average_weekly_earnings?.latest,
    },
    {
      key: 'wage-growth',
      label: '民間セクター賃金上昇率',
      hasData: !!wageGrowthData?.wage_growth?.data,
    },
    {
      key: 'unit-wage-costs',
      label: '単位賃金コスト（UWC）見通し',
      hasData: !!unitWageCostsData?.unit_wage_costs?.latest,
    },
  ]

  const handlePrevious = () => {
    setCurrentChartIndex((prev) => (prev > 0 ? prev - 1 : charts.length - 1))
  }

  const handleNext = () => {
    setCurrentChartIndex((prev) => (prev < charts.length - 1 ? prev + 1 : 0))
  }

  const currentChart = charts[currentChartIndex]

  const renderChart = () => {
    if (isLoading) {
      return (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
          <Spin size="large" />
        </div>
      )
    }

    switch (currentChart.key) {
      case 'market-expectations':
        return <BOEMarketExpectationsChart data={marketExpectationsData} />
      case 'cpi-projections':
        return <BOECPIProjectionsChart data={cpiProjectionsData} />
      case 'gdp-forecast':
        return <BOEGDPForecastChart data={gdpForecastData} />
      case 'unemployment-forecast':
        return <BOEUnemploymentForecastChart data={unemploymentForecastData} />
      case 'services-inflation':
        return <BOEServicesInflationChart data={servicesInflationData} />
      case 'wage-growth':
        return <BOEWageGrowthChart data={wageGrowthData} />
      case 'average-weekly-earnings':
        return <BOEAverageWeeklyEarningsChart data={averageWeeklyEarningsData} />
      case 'unit-wage-costs':
        return <BOEUnitWageCostsChart data={unitWageCostsData} />
      case 'inflation-expectations':
        return <BOEInflationExpectationsChart data={inflationExpectationsData} />
      default:
        return <Empty description="チャートが見つかりません" />
    }
  }

  // Card title with next release date
  const cardTitle = (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span>金融政策報告書</span>
      {nextReleaseText && (
        <span style={{ fontSize: 12, fontWeight: 'normal', color: DARK_THEME.textSecondary }}>
          次回発表: {nextReleaseText}
        </span>
      )}
    </div>
  )

  return (
    <div id="boe-economic-outlook-section">
      <Card
        title={cardTitle}
        style={{
          marginBottom: 24,
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
            gap: 20,
            marginBottom: 20,
            padding: 10,
            backgroundColor: DARK_THEME.bgTertiary,
            borderRadius: 8,
          }}
        >
          <Button icon={<LeftOutlined />} onClick={handlePrevious} size="large" />
          <div
            style={{
              textAlign: 'center',
              minWidth: 400,
            }}
          >
            <div
              style={{
                fontSize: 18,
                fontWeight: 'bold',
                marginBottom: 4,
                color: DARK_THEME.textPrimary,
              }}
            >
              {currentChart.label}
            </div>
            <div
              style={{
                fontSize: 12,
                color: DARK_THEME.textSecondary,
                marginTop: 4,
              }}
            >
              {currentChartIndex + 1} / {charts.length}
            </div>
          </div>
          <Button icon={<RightOutlined />} onClick={handleNext} size="large" />
        </div>

        {/* Current Chart */}
        <div id={`boe-${currentChart.key}-chart`}>{renderChart()}</div>
      </Card>
    </div>
  )
}
