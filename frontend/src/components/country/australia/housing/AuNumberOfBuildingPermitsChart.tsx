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

// データ種別
type DataKind = 'value' | 'yoy' | 'mom'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'mom', label: '前月比' },
  { mode: 'yoy', label: '前年比' },
  { mode: 'value', label: '原数値' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

export default function AuNumberOfBuildingPermitsChart({ data }: AuNumberOfBuildingPermitsChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('mom')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    value: 'default',
    mom: 3,
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
  const momTableData = useMonthlyTableData(chartData, (item) => item.mom)

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

  // 現在のデータ種別に応じた表示情報
  const { currentValue, currentLabel, currentColor, currentFormat, currentDecimals } = useMemo(() => {
    if (dataKind === 'value') {
      return {
        currentValue: latestValue?.value ?? null,
        currentLabel: '建築許可件数（季節調整済み）',
        currentColor: COLORS.value,
        currentFormat: 'number' as const,
        currentDecimals: 0,
      }
    }
    if (dataKind === 'mom') {
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
  }, [dataKind, latestValue])

  // データ比較用overlayConfig ID
  const getCompareUrl = () => {
    switch (dataKind) {
      case 'value': return '/compare?s=au_number_of_building_permits'
      case 'mom': return '/compare?s=au_number_of_building_permits_mom'
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
          unit={dataKind === 'value' ? '件' : undefined}
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
                  {/* 上段: データ種別 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      currentMode={dataKind}
                      onChange={setDataKind}
                      options={DATA_KIND_OPTIONS}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(getCompareUrl(), '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 下段: 表示形式（momのときのみ） */}
                  {dataKind === 'mom' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 期間セレクター（テーブル以外） */}
                  {!(dataKind === 'mom' && displayMode === 'heatmap') && (
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                  )}

                  {/* === 原数値チャート（線グラフ） === */}
                  {dataKind === 'value' && (
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
                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'mom', color: COLORS.mom, name: '前月比 (%)' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                    />
                  )}

                  {/* === 前月比ヒートマップ === */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTable data={momTableData} />
                  )}

                  {/* === 前年比チャート（線グラフ） === */}
                  {dataKind === 'yoy' && (
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
