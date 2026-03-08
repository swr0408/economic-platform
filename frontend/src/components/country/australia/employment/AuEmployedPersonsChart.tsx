/**
 * AU Employed Persons Chart Component
 * オーストラリア 雇用者数チャート
 *
 * データ項目:
 * - value: Employed Persons (thousands, Seasonally Adjusted)
 * - mom_change: 前月増減（千人）
 * - yoy_change: 前年比（%）
 *
 * データソース: Australian Bureau of Statistics (ABS)
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
  useMonthlyTableData,
  useViewModePeriodManagement,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
  StandardBarChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'
import { MonthlyTable } from '../../usa/common/MonthlyTable'

import type { AuEmployedPersonsData, AuEmployedPersonsDataPoint } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface ChartDataPoint {
  date: string
  value: number | null
  mom_change: number | null
  yoy_change: number | null
  [key: string]: unknown
}

interface AuEmployedPersonsChartProps {
  data: AuEmployedPersonsData | null
}

// カラー設定
const COLORS = {
  value: '#2E86C1',
  mom_change: '#E67E22',
  yoy_change: '#27AE60',
}

// データ種別
type DataKind = 'value' | 'yoy' | 'mom'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'mom', label: '前月増減' },
  { mode: 'value', label: '雇用者数' },
  { mode: 'yoy', label: '前年比' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function AuEmployedPersonsChart({ data }: AuEmployedPersonsChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('mom')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    value: 'default',
    mom: 3,
    yoy: 'default',
  })

  // データを変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((d: AuEmployedPersonsDataPoint) => ({
      date: d.date,
      value: d.value,
      mom_change: d.mom_change,
      yoy_change: d.yoy_change,
    }))
  }, [data])

  // データを日付昇順にソート
  const sortedData = useSortedData(chartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ
  const momTableData = useMonthlyTableData(sortedData, (item) => item.mom_change)

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="雇用者数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="雇用者数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  // データ種別に応じた最新値
  const currentLatestValue = (() => {
    if (!latest) return null
    if (dataKind === 'value') return latest.value
    if (dataKind === 'mom') return latest.mom_change
    if (dataKind === 'yoy') return latest.yoy_change
    return latest.value
  })()

  const currentColor = dataKind === 'mom' ? COLORS.mom_change : dataKind === 'yoy' ? COLORS.yoy_change : COLORS.value

  const getLatestLabel = () => {
    if (dataKind === 'value') return '雇用者数'
    if (dataKind === 'mom') return '雇用者数（前月増減）'
    if (dataKind === 'yoy') return '雇用者数（前年比）'
    return '雇用者数'
  }

  const getUnit = () => {
    if (dataKind === 'yoy') return '%'
    return '千人'
  }

  const getFormat = (): 'number' | 'percent' => {
    if (dataKind === 'yoy') return 'percent'
    return 'number'
  }

  return (
    <div id="au-employed-persons-chart">
      <ChartContainer
        title="雇用者数"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="Australian Bureau of Statistics"
        sourceUrl="https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={getLatestLabel()}
          value={currentLatestValue}
          unit={getUnit()}
          date={latest?.date}
          valueColor={currentColor}
          nextRelease={data?.next_release ?? undefined}
          format={getFormat()}
          decimals={dataKind === 'yoy' ? 1 : 0}
        />

        {/* タブ切替 */}
        <Tabs
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
                      options={DATA_KIND_OPTIONS}
                      currentMode={dataKind}
                      onChange={setDataKind}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=au_employed_persons', '_blank')}
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

                  {dataKind === 'value' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'value', color: COLORS.value, name: '雇用者数（千人）' },
                        ]}
                        yAxisFormatter={(v) => `${(v / 1000).toFixed(1)}M`}
                        yDomain={['dataMin - 100', 'dataMax + 100']}
                        tooltipValueFormatter={(v) => `${v.toFixed(1)} 千人`}
                      />
                    </>
                  )}

                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'mom_change', color: COLORS.mom_change, name: '前月増減（千人）' },
                        ]}
                        yAxisFormatter={(v) => `${v.toFixed(0)}`}
                        tooltipValueFormatter={(v) => `${v.toFixed(1)} 千人`}
                      />
                    </>
                  )}

                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTable
                      data={momTableData}
                      decimals={1}
                      helperText="※ 直近10年間の前月増減幅データ（単位: 千人）"
                    />
                  )}

                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'yoy_change', color: COLORS.yoy_change, name: '前年比' },
                        ]}
                        yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                        showZeroLine={true}
                      />
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="au_number_of_employees" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
