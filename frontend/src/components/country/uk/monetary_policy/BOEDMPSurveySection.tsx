import { useState, useMemo } from 'react'
import { Button, Card, Empty, Spin } from 'antd'
import { LeftOutlined, RightOutlined } from '@ant-design/icons'
import { DARK_THEME } from '../../usa/common/chartConstants'
import type { BOEDMPSurveyData, BOEDMPSurveyNextRelease } from '../../../../hooks/useDashboardData'
import BOEDMPCPIExpectationsChart from './BOEDMPCPIExpectationsChart'
import BOEDMPPriceGrowthChart from './BOEDMPPriceGrowthChart'
import BOEDMPWageGrowthChart from './BOEDMPWageGrowthChart'
import BOEDMPEmploymentGrowthChart from './BOEDMPEmploymentGrowthChart'

interface BOEDMPSurveySectionProps {
  data: BOEDMPSurveyData | null
  isLoading?: boolean
}

interface ChartConfig {
  key: string
  label: string
  hasData: boolean
}

// Format next release date to Japanese
const formatNextRelease = (nextRelease: BOEDMPSurveyNextRelease | null | undefined): string => {
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

    // Add estimated marker if applicable
    if (nextRelease.estimated) {
      result += ' (推定)'
    }

    return result
  } catch {
    return nextRelease.date
  }
}

/**
 * BOE Decision Maker Panel (DMP) サーベイセクション
 * カルーセル形式で複数のDMPチャートを表示
 */
export default function BOEDMPSurveySection({
  data,
  isLoading = false,
}: BOEDMPSurveySectionProps) {
  const [currentChartIndex, setCurrentChartIndex] = useState(0)

  const nextReleaseText = useMemo(() => {
    return formatNextRelease(data?.next_release)
  }, [data?.next_release])

  const charts: ChartConfig[] = [
    {
      key: 'dmp-cpi-expectations',
      label: 'CPIインフレ期待',
      hasData: !!data?.survey_data?.cpi_expectations?.date?.length,
    },
    {
      key: 'dmp-price-growth',
      label: '価格上昇率',
      hasData: !!data?.survey_data?.price_growth?.date?.length,
    },
    {
      key: 'dmp-wage-growth',
      label: '賃金上昇率',
      hasData: !!data?.survey_data?.wage_growth?.date?.length,
    },
    {
      key: 'dmp-employment-growth',
      label: '雇用成長率',
      hasData: !!data?.survey_data?.employment_growth?.date?.length,
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
      case 'dmp-cpi-expectations':
        return <BOEDMPCPIExpectationsChart data={data} />
      case 'dmp-price-growth':
        return <BOEDMPPriceGrowthChart data={data} />
      case 'dmp-wage-growth':
        return <BOEDMPWageGrowthChart data={data} />
      case 'dmp-employment-growth':
        return <BOEDMPEmploymentGrowthChart data={data} />
      default:
        return <Empty description="チャートが見つかりません" />
    }
  }

  // Card title with next release date
  const cardTitle = (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span>Decision Maker Panel (DMP) サーベイ</span>
      {nextReleaseText && (
        <span style={{ fontSize: 12, fontWeight: 'normal', color: DARK_THEME.textSecondary }}>
          次回発表: {nextReleaseText}
        </span>
      )}
    </div>
  )

  return (
    <div id="boe-dmp-survey-section">
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
              minWidth: 300,
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
