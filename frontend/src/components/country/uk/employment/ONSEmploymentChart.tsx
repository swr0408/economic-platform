/**
 * UK ONS雇用者数チャートコンポーネント
 *
 * データ:
 * - MGRZ: 総雇用者数（16歳以上、季節調整済）千人
 * - 前月増減幅（MoM）: 前月との差分（千人）
 * - 前3か月比（QoQ）: 3か月前との差分（千人）
 * - 前年比（YoY）: 前年同月比（%）
 *
 * データソース:
 * - ONS (Office for National Statistics)
 *
 * 発表スケジュール:
 * - FMPカレンダーから自動取得
 */
import { useState, useMemo, useCallback } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
  useViewModePeriodManagement,
  useMonthlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'
import {
  createChangeLegend,
  createChangeCellColorFn,
} from '../../usa/common/chartConstants'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { ONSEmploymentData } from '../../../../hooks/useDashboardData'

interface ONSEmploymentChartProps {
  data: ONSEmploymentData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  mom: number | null
  qoq: number | null
  yoy: number | null
  [key: string]: unknown
}

// グラフの色
const MOM_COLOR = '#3498db'
const QOQ_COLOR = '#9b59b6'
const YOY_COLOR = '#e74c3c'

// データ種別
type DataKind = 'qoq' | 'mom' | 'yoy'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'qoq', label: '対前3か月' },
  { mode: 'mom', label: '単月' },
  { mode: 'yoy', label: '前年比' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// 前月増減幅テーブル用の凡例と色関数（50k閾値）
const MOM_TABLE_LEGEND = createChangeLegend(50, 'k')
const getMomTableCellColor = createChangeCellColorFn(50)

// 前3か月増減幅テーブル用の凡例と色関数（100k閾値）
const QOQ_TABLE_LEGEND = createChangeLegend(100, 'k')
const getQoqTableCellColor = createChangeCellColorFn(100)

export default function ONSEmploymentChart({ data }: ONSEmploymentChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('qoq')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    qoq: 'default',
    mom: 'default',
    yoy: 'default',
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter(point => point.value !== null || point.mom !== null || point.qoq !== null || point.yoy !== null)
      .map(point => ({
        date: point.date,
        value: point.value,
        mom: point.mom,
        qoq: point.qoq,
        yoy: point.yoy,
      }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // 前月増減幅テーブル用データ
  const momTableData = useMonthlyTableData(
    chartData,
    (item) => item.mom ?? null,
    10
  )

  // 前3か月増減幅テーブル用データ
  const qoqTableData = useMonthlyTableData(
    chartData,
    (item) => item.qoq ?? null,
    10
  )

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  // データ比較ページを開く
  const handleCompare = useCallback(() => {
    const seriesId = dataKind === 'qoq' ? 'uk_employment_qoq' : dataKind === 'mom' ? 'uk_employment_mom' : 'uk_employment_yoy'
    window.open(`/compare?s=${seriesId}&s=uk_claimant_count_mom`, '_blank')
  }, [dataKind])


  if (data === null) {
    return <LoadingChart title="ONS雇用者数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="ONS雇用者数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値表示用アイテム
  const latestItems = latest ? [
    {
      label: '対前3か月',
      value: latest.qoq,
      color: QOQ_COLOR,
      format: 'number' as const,
      decimals: 1,
      suffix: 'k',
    },
    {
      label: '前月比',
      value: latest.mom,
      color: MOM_COLOR,
      format: 'number' as const,
      decimals: 1,
      suffix: 'k',
    },
    {
      label: '前年比',
      value: latest.yoy,
      color: YOY_COLOR,
      format: 'percent' as const,
      decimals: 2,
    },
  ] : []


  // チャート設定取得
  const getChartConfig = () => {
    switch (dataKind) {
      case 'qoq':
        return {
          dataKey: 'qoq',
          color: QOQ_COLOR,
          name: '対前3か月',
          yAxisFormatter: (v: number) => `${v}k`,
          tooltipFormatter: (v: number) => `${v.toFixed(1)}k`,
          yDomain: ['dataMin - 100', 'dataMax + 100'] as [string, string],
        }
      case 'mom':
        return {
          dataKey: 'mom',
          color: MOM_COLOR,
          name: '前月増減幅',
          yAxisFormatter: (v: number) => `${v}k`,
          tooltipFormatter: (v: number) => `${v.toFixed(1)}k`,
          yDomain: ['dataMin - 50', 'dataMax + 50'] as [string, string],
        }
      case 'yoy':
        return {
          dataKey: 'yoy',
          color: YOY_COLOR,
          name: '前年比',
          yAxisFormatter: (v: number) => `${v}%`,
          tooltipFormatter: (v: number) => `${v.toFixed(2)}%`,
          yDomain: ['dataMin - 0.5', 'dataMax + 0.5'] as [string, string],
        }
    }
  }

  const chartConfig = getChartConfig()

  // ヒートマップ表示の有無
  const showDisplayModeToggle = dataKind === 'qoq' || dataKind === 'mom'

  return (
    <div id="uk-ons-employment-chart">
      <ChartContainer
        title="雇用者数"
        showPeriodSelector={false}
        dataSource="ONS"
        sourceUrl="https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={latestItems}
          date={latest?.date}
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
                  {/* 上段: データ種別 */}
                  <div style={{ marginBottom: 8 }}>
                    <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />
                  </div>

                  {/* 下段: 表示形式（qoq/momのときのみ） */}
                  {showDisplayModeToggle && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* グラフ表示 */}
                  {!(showDisplayModeToggle && displayMode === 'heatmap') && (
                    <>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                        <Tooltip title="比較ページを開く">
                          <Button
                            icon={<AreaChartOutlined />}
                            onClick={handleCompare}
                          >
                            データ比較
                          </Button>
                        </Tooltip>
                      </div>
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          {
                            dataKey: chartConfig.dataKey,
                            color: chartConfig.color,
                            name: chartConfig.name,
                            hide: hiddenSeries.has(chartConfig.dataKey),
                          },
                        ]}
                        yAxisFormatter={chartConfig.yAxisFormatter}
                        tooltipValueFormatter={chartConfig.tooltipFormatter}
                        onLegendClick={handleLegendClick}
                        yDomain={chartConfig.yDomain}
                      />
                    </>
                  )}

                  {/* テーブル表示（前3か月比） */}
                  {dataKind === 'qoq' && displayMode === 'heatmap' && (
                    <MonthlyTable
                      data={qoqTableData}
                      formatValue={(value) => {
                        if (value === null) return '-'
                        return `${value >= 0 ? '+' : ''}${value.toFixed(1)}`
                      }}
                      getCellBgColor={getQoqTableCellColor}
                      legendItems={QOQ_TABLE_LEGEND}
                      helperText="※ 直近10年間の前3か月増減幅データ（単位: 千人）"
                      decimals={1}
                    />
                  )}

                  {/* テーブル表示（単月） */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTable
                      data={momTableData}
                      formatValue={(value) => {
                        if (value === null) return '-'
                        return `${value >= 0 ? '+' : ''}${value.toFixed(1)}`
                      }}
                      getCellBgColor={getMomTableCellColor}
                      legendItems={MOM_TABLE_LEGEND}
                      helperText="※ 直近10年間の前月増減幅データ（単位: 千人）"
                      decimals={1}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ons_employment" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
