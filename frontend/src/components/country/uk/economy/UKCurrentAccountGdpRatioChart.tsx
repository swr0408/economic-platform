/**
 * UK経常収支対GDP比チャートコンポーネント
 *
 * Current Account Balance as % of GDP, SA
 * シリーズ: AA6H (ONS PNBP Dataset)
 *
 * データソース:
 * - Office for National Statistics (ONS)
 *
 * 発表スケジュール:
 * - 四半期
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
  useQuarterlyTableData,
} from '../../usa/common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import { QuarterlyTable } from '../../usa/common/QuarterlyTable'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { UKCurrentAccountData } from '../../../../hooks/useDashboardData'

interface UKCurrentAccountGdpRatioChartProps {
  data: UKCurrentAccountData | null
}

interface ChartDataPoint {
  date: string
  value: number
  [key: string]: unknown
}

type ViewMode = 'value' | 'table'

const COLORS = {
  value: '#fa8c16',
}

export default function UKCurrentAccountGdpRatioChart({ data }: UKCurrentAccountGdpRatioChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('value')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    value: 'default',
    table: 'default',
  })

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.gdp_ratio) return []

    return data.gdp_ratio
      .map(item => ({
        date: item.date,
        value: item.value,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ（四半期別マトリックス）
  const tableData = useQuarterlyTableData(
    chartData,
    (item) => item.value,
    10
  )

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  if (data === null) {
    return <LoadingChart title="経常収支対GDP比（イギリス）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="経常収支対GDP比（イギリス）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="uk-current-account-gdp-ratio-chart">
      <ChartContainer
        title="経常収支対GDP比"
        showPeriodSelector={false}
        dataSource="ONS"
        sourceUrl="https://www.ons.gov.uk/economy/nationalaccounts/balanceofpayments/timeseries/aa6h/pnbp"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="経常収支対GDP比"
          value={latest ? `${latest.value >= 0 ? '+' : ''}${latest.value.toFixed(2)}%` : null}
          valueColor={COLORS.value}
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
                      { mode: 'value', label: '対GDP比' },
                      { mode: 'table', label: '対GDP比（テーブル）' },
                    ]}
                  />

                  {/* テーブル表示 */}
                  {viewMode === 'table' && (
                    <QuarterlyTable
                      data={tableData}
                      decimals={2}
                      showLegend={false}
                      helperText="※ 直近10年間の経常収支対GDP比データ（単位: %）"
                    />
                  )}

                  {/* 期間セレクター + グラフ */}
                  {viewMode === 'value' && (
                    <>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                        <Tooltip title="比較ページを開く">
                          <Button
                            icon={<AreaChartOutlined />}
                            onClick={() => window.open('/compare?s=uk_current_account_gdp_ratio', '_blank')}
                          >
                            データ比較
                          </Button>
                        </Tooltip>
                      </div>

                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          {
                            dataKey: 'value',
                            color: COLORS.value,
                            name: '経常収支対GDP比（%）',
                          },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
                        showZeroLine={true}
                      />
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="uk_current_account" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
