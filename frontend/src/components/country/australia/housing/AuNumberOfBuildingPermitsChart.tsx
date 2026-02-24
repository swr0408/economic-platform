/**
 * オーストラリア 建築許可件数チャートコンポーネント
 *
 * ABS (Australian Bureau of Statistics) から建築許可件数データを表示
 * Series ID: A422070J (Seasonally Adjusted, Total dwelling units)
 *
 * ビューモード:
 * - value: 原数値（線グラフ）
 * - mom: 前月比%（棒グラフ）
 * - yoy: 前年比%（線グラフ）
 *
 * データソース:
 * - ABS: https://www.abs.gov.au/statistics/industry/building-and-construction/building-approvals-australia
 *
 * 発表スケジュール: 月次
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
  useMultiValueMonthlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
  StandardBarChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import { MonthlyTableWithDataTypes } from '../../usa/common/MonthlyTable'

import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { AuNumberOfBuildingPermitsData } from '../../../../hooks/useDashboardData'

interface AuNumberOfBuildingPermitsChartProps {
  data: AuNumberOfBuildingPermitsData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  mom: number | null
  yoy: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  value: '#1E88E5',  // 青（原数値）
  mom: '#43A047',    // 緑（前月比）
  yoy: '#E53935',    // 赤（前年比）
}

type ViewMode = 'value' | 'mom' | 'mom_table' | 'yoy'

export default function AuNumberOfBuildingPermitsChart({ data }: AuNumberOfBuildingPermitsChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('mom')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    value: 'default',
    mom: 3,
    mom_table: 'default',
    yoy: 'default',
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []
    return data.data.map((item) => ({
      date: item.date,
      value: item.value,
      mom: item.mom ?? null,
      yoy: item.yoy ?? null,
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
  const momTableData = useMultiValueMonthlyTableData(
    chartData,
    { mom: (item) => item.mom },
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

  // 現在のビューモードに応じた表示情報
  const { currentValue, currentLabel, currentColor, currentFormat, currentDecimals } = useMemo(() => {
    if (viewMode === 'value') {
      return {
        currentValue: latestValue?.value ?? null,
        currentLabel: '建築許可件数（季節調整済み）',
        currentColor: COLORS.value,
        currentFormat: 'number' as const,
        currentDecimals: 0,
      }
    }
    if (viewMode === 'mom' || viewMode === 'mom_table') {
      return {
        currentValue: latestValue?.mom ?? null,
        currentLabel: '建築許可件数（前月比）',
        currentColor: COLORS.mom,
        currentFormat: 'percent' as const,
        currentDecimals: 2,
      }
    }
    // yoy
    return {
      currentValue: latestValue?.yoy ?? null,
      currentLabel: '建築許可件数（前年比）',
      currentColor: COLORS.yoy,
      currentFormat: 'percent' as const,
      currentDecimals: 2,
    }
  }, [viewMode, latestValue])

  // データ比較用overlayConfig ID
  const getCompareUrl = () => {
    switch (viewMode) {
      case 'value': return '/compare?s=au_number_of_building_permits'
      case 'mom': case 'mom_table': return '/compare?s=au_number_of_building_permits_mom'
      case 'yoy': return '/compare?s=au_number_of_building_permits_yoy'
      default: return '/compare?s=au_number_of_building_permits'
    }
  }

  if (data === null) {
    return <LoadingChart title="建築許可件数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="建築許可件数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="au-number-of-building-permits-chart">
      <ChartContainer
        title="建築許可件数"
        showPeriodSelector={false}
        dataSource="Australian Bureau of Statistics"
        sourceUrl="https://www.abs.gov.au/statistics/industry/building-and-construction/building-approvals-australia"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={currentLabel}
          value={currentValue}
          date={latestValue?.date}
          format={currentFormat}
          decimals={currentDecimals}
          valueColor={currentColor}
          nextRelease={data.next_release ?? null}
          unit={viewMode === 'value' ? '件' : undefined}
        />

        {/* タブ切替（時系列 / マーケットインパクト） */}
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
                    onChange={(mode) => setViewMode(mode as ViewMode)}
                    options={[
                      { mode: 'mom', label: '前月比' },
                      { mode: 'mom_table', label: '前月比（テーブル）' },
                      { mode: 'yoy', label: '前年比' },
                      { mode: 'value', label: '原数値' },
                    ]}
                  />

                  {/* 期間セレクター + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(getCompareUrl(), '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* === 原数値チャート（線グラフ） === */}
                  {viewMode === 'value' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'value', color: COLORS.value, name: '建築許可件数' },
                      ]}
                      yAxisFormatter={(v) => `${(v / 1000).toFixed(0)}K`}
                      tooltipValueFormatter={(v) => `${v.toLocaleString()}件`}
                      yDomain={['dataMin - 1000', 'dataMax + 1000']}
                    />
                  )}

                  {/* === 前月比チャート（棒グラフ） === */}
                  {viewMode === 'mom' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'mom', color: COLORS.mom, name: '前月比 (%)' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                    />
                  )}

                  {/* === 前月比テーブル === */}
                  {viewMode === 'mom_table' && (
                    <MonthlyTableWithDataTypes
                      data={momTableData}
                      dataTypes={[{ type: 'mom', label: '前月比' }]}
                      selectedType="mom"
                      onTypeChange={() => {}}
                    />
                  )}

                  {/* === 前年比チャート（線グラフ） === */}
                  {viewMode === 'yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'yoy', color: COLORS.yoy, name: '前年比 (%)' },
                      ]}
                      yAxisFormatter={(v) => `${v.toFixed(0)}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                      yDomain={['dataMin - 5', 'dataMax + 5']}
                      showZeroLine={true}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="au_number_of_building_permits" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
