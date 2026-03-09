/**
 * カナダ労働参加率 チャートコンポーネント
 *
 * Statistics Canada から労働参加率データを取得し、表示
 *
 * データ:
 * - Participation rate（労働参加率）
 *
 * データソース:
 * - Statistics Canada Table 14-10-0287-01
 *
 * 発表スケジュール:
 * - 毎月発表（失業率と同時）
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
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { CaLaborForceParticipationRateData } from '../../../../hooks/useDashboardData'

interface CaLaborForceParticipationRateChartProps {
  data: CaLaborForceParticipationRateData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  participation: '#1E90FF', // ドジャーブルー
}

// ビューモード
type ViewMode = 'chart'

export default function CaLaborForceParticipationRateChart({ data }: CaLaborForceParticipationRateChartProps) {
  const [viewMode] = useState<ViewMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    chart: 10,
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
    return <LoadingChart title="カナダ労働参加率" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="カナダ労働参加率" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ca-labor-force-participation-rate-chart">
      <ChartContainer
        title="労働参加率"
        showPeriodSelector={false}
        dataSource="Statistics Canada"
        sourceUrl="https://www.statcan.gc.ca/en/subjects-start/labour_"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="労働参加率"
          value={latestValue?.value}
          date={latestValue?.date}
          format="percent"
          decimals={1}
          valueColor={COLORS.participation}
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
                  {viewMode === 'chart' && (
                    <>
                      {/* コントロールバー */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                        <Tooltip title="比較ページを開く">
                          <Button
                            icon={<AreaChartOutlined />}
                            onClick={() => window.open('/compare?s=ca_labor_force_participation_rate', '_blank')}
                          >
                            データ比較
                          </Button>
                        </Tooltip>
                      </div>

                      {/* グラフ */}
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'value', color: COLORS.participation, name: '労働参加率' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        showZeroLine={false}
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
                <MarketImpactTab indicatorId="ca_labor_force_participation_rate" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
