/**
 * カナダ平均時給 チャートコンポーネント
 *
 * Statistics Canada から平均時給データを取得し、表示
 *
 * データ:
 * - Average hourly wages（平均時給）
 * - 前年比（YoY）、前月比（MoM）
 *
 * データソース:
 * - Statistics Canada Table 14-10-0065-01
 *
 * 発表スケジュール:
 * - 毎月発表（雇用統計と同時）
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
  StandardBarChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { CaAverageHourlyWageData } from '../../../../hooks/useDashboardData'

interface CaAverageHourlyWageChartProps {
  data: CaAverageHourlyWageData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  yoy: number | null
  mom: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  yoy: '#228B22', // フォレストグリーン
  mom: '#4169E1', // ロイヤルブルー
}

// ビューモード
type ViewMode = 'yoy' | 'mom' | 'table'

const VIEW_MODE_OPTIONS = [
  { mode: 'yoy' as const, label: '前年比' },
  { mode: 'mom' as const, label: '前月比' },
  { mode: 'table' as const, label: 'テーブル' },
]

export default function CaAverageHourlyWageChart({ data }: CaAverageHourlyWageChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom: 'default',
    table: 'default',
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((item) => ({
      date: item.date,
      value: item.value,
      yoy: item.yoy,
      mom: item.mom,
    }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ（前月比）
  const tableData = useMonthlyTableData(
    chartData,
    (item) => item.mom,
    10
  )

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = useMemo(() => {
    if (!chartData.length) return null
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].yoy !== null || chartData[i].mom !== null) {
        return chartData[i]
      }
    }
    return null
  }, [chartData])

  // 表示する最新値を取得
  const displayValue = useMemo(() => {
    if (!latestValue) return null
    return viewMode === 'yoy' ? latestValue.yoy : latestValue.mom
  }, [latestValue, viewMode])

  if (data === null) {
    return <LoadingChart title="カナダ平均時給" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="カナダ平均時給" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ca-average-hourly-wage-chart">
      <ChartContainer
        title="平均時給"
        showPeriodSelector={false}
        dataSource="Statistics Canada"
        sourceUrl="https://www.statcan.gc.ca/en/subjects-start/labour_"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={viewMode === 'yoy' ? '平均時給（前年比）' : '平均時給（前月比）'}
          value={displayValue}
          date={latestValue?.date}
          format="percent"
          decimals={2}
          valueColor={viewMode === 'yoy' ? COLORS.yoy : COLORS.mom}
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
                  <ViewModeButtonGroup
                    currentMode={viewMode}
                    onChange={(v) => setViewMode(v)}
                    options={VIEW_MODE_OPTIONS}
                  />

                  {/* コントロールバー */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, marginTop: 12 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=ca_average_hourly_wage', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* グラフ */}
                  {viewMode === 'yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'yoy', color: COLORS.yoy, name: '前年比' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                      yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                      showZeroLine={true}
                    />
                  )}

                  {viewMode === 'mom' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'mom', color: COLORS.mom, name: '前月比' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                      yDomain={['dataMin - 0.3', 'dataMax + 0.3']}
                      showZeroLine={true}
                    />
                  )}

                  {viewMode === 'table' && (
                    <MonthlyTable
                      data={tableData}
                      helperText="※ 直近10年間の平均時給（前月比）データ（単位: %）"
                      formatValue={(value) => {
                        if (value === null) return '-'
                        return `${value.toFixed(2)}`
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
                <MarketImpactTab indicatorId="ca_average_hourly_wage" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
