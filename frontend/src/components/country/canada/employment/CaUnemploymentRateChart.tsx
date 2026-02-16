/**
 * カナダ失業率 チャートコンポーネント
 *
 * Statistics Canada から失業率データを取得し、表示
 *
 * データ:
 * - Unemployment Rate（失業率）
 *
 * データソース:
 * - Statistics Canada Table 14-10-0287-01
 *
 * 発表スケジュール:
 * - 毎月発表
 * - 発表時刻: 08:30 ET
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMonthlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { CaUnemploymentRateData } from '../../../../hooks/useDashboardData'

interface CaUnemploymentRateChartProps {
  data: CaUnemploymentRateData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  unemployment: '#DC143C', // カナダ赤
}

// ビューモード
type ViewMode = 'chart' | 'table'

export default function CaUnemploymentRateChart({ data }: CaUnemploymentRateChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    chart: 'default',
    table: 'default',
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((item) => ({
      date: item.date,
      value: item.value,
    }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ
  const tableData = useMonthlyTableData(
    chartData,
    (item) => item.value,
    10
  )

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = useMemo(() => {
    if (!chartData.length) return null
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].value !== null) {
        return chartData[i]
      }
    }
    return null
  }, [chartData])

  if (data === null) {
    return <LoadingChart title="カナダ失業率" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="カナダ失業率" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ca-unemployment-rate-chart">
      <ChartContainer
        title="失業率"
        showPeriodSelector={false}
        dataSource="Statistics Canada"
        sourceUrl="https://www.statcan.gc.ca/en/subjects-start/labour_"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="失業率"
          value={latestValue?.value}
          date={latestValue?.date}
          format="percent"
          decimals={1}
          valueColor={COLORS.unemployment}
          nextRelease={data.next_release}
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
                  {/* ビューモード切替 */}
                  <div style={{ marginBottom: 12 }}>
                    <Button.Group>
                      <Button
                        type={viewMode === 'chart' ? 'primary' : 'default'}
                        onClick={() => setViewMode('chart')}
                      >
                        グラフ
                      </Button>
                      <Button
                        type={viewMode === 'table' ? 'primary' : 'default'}
                        onClick={() => setViewMode('table')}
                      >
                        テーブル
                      </Button>
                    </Button.Group>
                  </div>

                  {viewMode === 'chart' && (
                    <>
                      {/* コントロールバー */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                        <Tooltip title="比較ページを開く">
                          <Button
                            icon={<AreaChartOutlined />}
                            onClick={() => window.open('/compare?s=ca_unemployment_rate', '_blank')}
                          >
                            データ比較
                          </Button>
                        </Tooltip>
                      </div>

                      {/* グラフ */}
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'value', color: COLORS.unemployment, name: '失業率' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        showZeroLine={false}
                      />
                    </>
                  )}

                  {viewMode === 'table' && (
                    <MonthlyTable
                      data={tableData}
                      helperText="※ 直近10年間の失業率データ（単位: %）"
                      formatValue={(value) => {
                        if (value === null) return '-'
                        return `${value.toFixed(1)}`
                      }}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ca_unemployment_rate" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
