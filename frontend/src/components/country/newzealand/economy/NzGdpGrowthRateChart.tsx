/**
 * NZ GDP成長率チャートコンポーネント
 *
 * データ項目:
 * - qoq: 前期比（%）- 季節調整済み実質連鎖
 * - yoy: 前年同期比（%）- 同四半期前年比
 *
 * データソース: Stats NZ
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
  useHiddenSeries,
  useQuarterlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
  StandardBarChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import { QuarterlyTable } from '../../usa/common/QuarterlyTable'

import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { NzGdpGrowthRateData } from '../../../../hooks/useDashboardData'

interface NzGdpGrowthRateChartProps {
  data: NzGdpGrowthRateData | null
}

interface ChartDataPoint {
  date: string
  qoq: number | null
  yoy: number | null
}

const COLORS = {
  qoq: '#2563eb',
  yoy: '#2563eb',
}

// 指標種別
type DataKind = 'qoq' | 'yoy'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'qoq', label: '前期比' },
  { mode: 'yoy', label: '前年比' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

const formatQuarterLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  const monthNum = parseInt(month, 10)
  const quarter = Math.ceil(monthNum / 3)
  return `${year}/Q${quarter}`
}

const formatQuarterLabelJP = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  const monthNum = parseInt(month, 10)
  const quarter = Math.ceil(monthNum / 3)
  return `${year}年 Q${quarter}`
}

export default function NzGdpGrowthRateChart({ data }: NzGdpGrowthRateChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('qoq')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    qoq: 5,
    yoy: 20,
  })

  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((item) => item.qoq !== null || item.yoy !== null)
      .map((item) => ({
        date: item.date,
        qoq: item.qoq,
        yoy: item.yoy,
      }))
  }, [data])

  const sortedData = useSortedData(chartData)

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // ヒートマップ用データ（単一系列）
  const quarterlyTableData = useQuarterlyTableData(
    sortedData,
    (item: ChartDataPoint) => item.qoq,
    10
  )

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="GDP成長率" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="GDP成長率" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  return (
    <div id="nz-gdp-growth-rate">
      <ChartContainer
        title="GDP成長率"
        showPeriodSelector={false}
        dataSource="Stats NZ"
        sourceUrl="https://www.stats.govt.nz/indicators/gross-domestic-product-gdp/"
        handbookId="gdp"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: 'QoQ',
              value: latest?.qoq,
              color: COLORS.qoq,
              format: 'percent',
            },
            {
              label: 'YoY',
              value: latest?.yoy,
              color: COLORS.yoy,
              format: 'percent',
            },
          ]}
          date={latest?.date}
          dateFormatter={formatQuarterLabelJP}
          nextRelease={data?.next_release ? { date: data.next_release.date } : undefined}
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
                      options={DATA_KIND_OPTIONS}
                      currentMode={dataKind}
                      onChange={setDataKind}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=nz_gdp_growth_rate', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 下段: 表示形式（前期比のときのみ） */}
                  {dataKind === 'qoq' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 前期比チャート（棒グラフ） */}
                  {dataKind === 'qoq' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'qoq', color: COLORS.qoq, name: 'GDP（前期比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                        xAxisFormatter={formatQuarterLabel}
                        tooltipLabelFormatter={formatQuarterLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                      />
                    </>
                  )}

                  {/* 前期比ヒートマップ */}
                  {dataKind === 'qoq' && displayMode === 'heatmap' && (
                    <QuarterlyTable
                      data={quarterlyTableData}
                      decimals={1}
                      helperText="※ 直近10年間の前期比データ（単位: %、季節調整済み実質）"
                      formatValue={(v) => {
                        if (v === null || v === undefined) return '-'
                        return `${v >= 0 ? '+' : ''}${v.toFixed(1)}`
                      }}
                    />
                  )}

                  {/* 前年比チャート（折れ線グラフ） */}
                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'yoy', color: COLORS.yoy, name: 'GDP（前年比）', hide: hiddenSeries.has('yoy') },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                        showZeroLine={true}
                        xAxisFormatter={formatQuarterLabel}
                        tooltipLabelFormatter={formatQuarterLabelJP}
                        onLegendClick={handleLegendClick}
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
                <MarketImpactTab indicatorId="nz_gdp_growth_rate" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
