/**
 * カナダ週間平均給与 チャートコンポーネント
 *
 * Statistics Canada から週間平均給与データを取得し、表示
 *
 * データ:
 * - Average weekly earnings including overtime for all employees（週間平均給与）
 * - 前年比（YoY）、前月比（MoM）
 *
 * データソース:
 * - Statistics Canada Table 14-10-0022-01
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
  StandardBarChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { CaWeeklyAverageSalaryData } from '../../../../hooks/useDashboardData'

interface CaWeeklyAverageSalaryChartProps {
  data: CaWeeklyAverageSalaryData | null
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
  yoy: '#8B4513', // サドルブラウン
  mom: '#20B2AA', // ライトシーグリーン
}

// データ種別
type DataKind = 'yoy' | 'mom'
type DisplayMode = 'chart' | 'heatmap'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
]

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

export default function CaWeeklyAverageSalaryChart({ data }: CaWeeklyAverageSalaryChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 10,
    mom: 10,
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
    return dataKind === 'yoy' ? latestValue.yoy : latestValue.mom
  }, [latestValue, dataKind])

  if (data === null) {
    return <LoadingChart title="カナダ週間平均給与" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="カナダ週間平均給与" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ca-weekly-average-salary-chart">
      <ChartContainer
        title="週間平均給与"
        showPeriodSelector={false}
        dataSource="Statistics Canada"
        sourceUrl="https://www.statcan.gc.ca/en/subjects-start/labour_"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={dataKind === 'yoy' ? '週間平均給与（前年比）' : '週間平均給与（前月比）'}
          value={displayValue}
          date={latestValue?.date}
          format="percent"
          decimals={2}
          valueColor={dataKind === 'yoy' ? COLORS.yoy : COLORS.mom}
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
                  {/* 上段: 指標種別 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      currentMode={dataKind}
                      onChange={(v) => setDataKind(v)}
                      options={DATA_KIND_OPTIONS}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=ca_weekly_average_salary', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
                  {dataKind === 'mom' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* コントロールバー */}
                  {!(dataKind === 'mom' && displayMode === 'heatmap') && (
                    <div style={{ marginBottom: 8 }}>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    </div>
                  )}

                  {/* 前年比グラフ */}
                  {dataKind === 'yoy' && (
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

                  {/* 前月比グラフ */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
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

                  {/* 前月比ヒートマップ */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTable
                      data={tableData}
                      helperText="※ 直近10年間の週間平均給与（前月比）データ（単位: %）"
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
                <MarketImpactTab indicatorId="ca_weekly_average_salary" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
