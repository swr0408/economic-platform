/**
 * UK政府債務残高対GDP比チャートコンポーネント
 *
 * PS: Net Debt (excluding public sector banks) as a % of GDP: NSA
 * シリーズ: HF6X (ONS PUSF Dataset)
 *
 * データソース:
 * - Office for National Statistics (ONS)
 *
 * 発表スケジュール:
 * - 月次
 *
 * 単位:
 * - % of GDP
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMonthlyTableData,
} from '../../usa/common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  SimpleLatestValueBox,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { UKGovernmentDebtToGdpRatioData } from '../../../../hooks/useDashboardData'

interface UkGovernmentDebtToGdpRatioChartProps {
  data: UKGovernmentDebtToGdpRatioData | null
}

interface ChartDataPoint {
  date: string
  value: number
  mom_change: number | null
  [key: string]: unknown
}

type ViewMode = 'value' | 'mom_chart' | 'mom_table'

const COLORS = {
  value: '#722ed1',
  mom: '#52c41a',
}

export default function UkGovernmentDebtToGdpRatioChart({ data }: UkGovernmentDebtToGdpRatioChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('value')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    value: 'default',
    mom_chart: 3,
    mom_table: 'default',
  })

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    // MoM changeをMapに
    const momMap = new Map<string, number>()
    if (data.mom_change) {
      data.mom_change.forEach(item => {
        momMap.set(item.date, item.value)
      })
    }

    return data.data
      .map(item => ({
        date: item.date,
        value: item.value,
        mom_change: momMap.get(item.date) ?? null,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ（年別×月別のマトリックス）
  const tableData = useMonthlyTableData(chartData, (item) =>
    viewMode === 'mom_table' ? item.mom_change : item.value
  )

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  // 現在の表示値
  const currentValue = useMemo(() => {
    if (!latest) return null
    return viewMode === 'value' ? latest.value : latest.mom_change
  }, [latest, viewMode])

  const currentColor = viewMode === 'value' ? COLORS.value : COLORS.mom

  if (data === null) {
    return <LoadingChart title="政府債務残高対GDP比（イギリス）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="政府債務残高対GDP比（イギリス）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="uk-government-debt-to-gdp-ratio-chart">
      <ChartContainer
        title="政府債務残高対GDP比"
        showPeriodSelector={false}
        dataSource="ONS"
        sourceUrl="https://www.ons.gov.uk/economy/governmentpublicsectorandtaxes/publicsectorfinance/timeseries/hf6x/pusf"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={viewMode === 'value' ? '政府債務残高対GDP比' : '前月増減幅'}
          value={currentValue != null ? (viewMode === 'value' ? `${currentValue.toFixed(1)}%` : `${currentValue >= 0 ? '+' : ''}${currentValue.toFixed(2)}pp`) : null}
          valueColor={currentColor}
          date={latest?.date}
          nextRelease={data.next_release ?? undefined}
          format="raw"
        />

        {/* タブ切替 */}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  <ViewModeButtonGroup
                    currentMode={viewMode}
                    onChange={(mode) => setViewMode(mode)}
                    options={[
                      { mode: 'value', label: '原数値' },
                      { mode: 'mom_chart', label: '前月増減幅' },
                      { mode: 'mom_table', label: '前月増減幅（テーブル）' },
                    ]}
                  />

                  {/* 期間セレクター */}
                  {(viewMode === 'value' || viewMode === 'mom_chart') && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <Tooltip title="比較ページを開く">
                        <Button
                          icon={<AreaChartOutlined />}
                          onClick={() => window.open('/compare?s=uk_government_debt_to_gdp_ratio', '_blank')}
                        >
                          データ比較
                        </Button>
                      </Tooltip>
                    </div>
                  )}

                  {/* コンテンツ表示 */}
                  {viewMode === 'mom_table' && <MonthlyTable data={tableData} />}

                  {viewMode === 'value' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        {
                          dataKey: 'value',
                          color: COLORS.value,
                          name: '政府債務残高対GDP比（%）',
                        },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
                    />
                  )}

                  {viewMode === 'mom_chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        {
                          dataKey: 'mom_change',
                          color: COLORS.mom,
                          name: '前月増減幅（%ポイント）',
                        },
                      ]}
                      yAxisFormatter={(v) => `${v}pp`}
                      tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}pp`}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="uk_government_debt_to_gdp_ratio" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
