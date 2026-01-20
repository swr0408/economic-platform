/**
 * UK ONS失業給付申請件数チャートコンポーネント
 *
 * データ:
 * - ONS Claimant Count（原数値、前月比、前年比）
 *
 * データソース:
 * - ONS (Office for National Statistics)
 *
 * 発表スケジュール:
 * - ONS公式サイトの「Next release」日程に基づく
 * - 15:00-16:10 ロンドン時間
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
  SimpleLatestValueBox,
  StandardLineChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'
import {
  createChangeLegend,
  createChangeCellColorFn,
} from '../../usa/common/chartConstants'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { ONSClaimantCountData } from '../../../../hooks/useDashboardData'

interface ONSClaimantCountChartProps {
  data: ONSClaimantCountData | null
}

interface ChartDataPoint {
  date: string
  value: number
  mom?: number | null
  yoy?: number | null
  [key: string]: unknown
}

// グラフの色
const CHART_COLOR = '#8b5cf6'
const MOM_COLOR = '#10b981'
const YOY_COLOR = '#f59e0b'

// ビューモード
type ViewMode = 'value' | 'mom' | 'mom_table' | 'yoy'

// 前月増減幅テーブル用の凡例と色関数（50k閾値）
const MOM_TABLE_THRESHOLD = 50
const MOM_TABLE_LEGEND = createChangeLegend(50, 'k')
const getMomTableCellColor = createChangeCellColorFn(MOM_TABLE_THRESHOLD)

export default function ONSClaimantCountChart({ data }: ONSClaimantCountChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('mom')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    value: 'default',
    mom: 'default',
    mom_table: 'default',
    yoy: 'default',
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter(point => point.value !== null)
      .map(point => ({
        date: point.date,
        value: point.value as number,
        mom: point.mom,
        yoy: point.yoy,
      }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  // 前月増減幅テーブル用データ
  const momTableData = useMonthlyTableData(
    chartData,
    (item) => item.mom ?? null,
    10
  )

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  // データ比較ページを開く
  const handleCompare = useCallback(() => {
    window.open('/compare?s=uk_claimant_count&s=uk_unemployment_rate', '_blank')
  }, [])

  // 現在のビューモードに応じた値を取得
  const getLatestValue = () => {
    if (!latest) return undefined
    switch (viewMode) {
      case 'mom':
      case 'mom_table':
        return latest.mom ?? undefined
      case 'yoy':
        return latest.yoy ?? undefined
      default:
        return latest.value
    }
  }

  // 値のフォーマット
  const getValueFormat = () => {
    switch (viewMode) {
      case 'yoy':
        return 'percent'
      default:
        return 'number'
    }
  }

  // 単位
  const getUnit = () => {
    switch (viewMode) {
      case 'yoy':
        return '%'
      case 'mom':
      case 'mom_table':
        return 'k'
      default:
        return 'k'
    }
  }

  if (data === null) {
    return <LoadingChart title="ONS失業給付申請件数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="ONS失業給付申請件数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // チャート設定
  const getChartConfig = () => {
    switch (viewMode) {
      case 'mom':
        return {
          lines: [
            {
              dataKey: 'mom',
              color: MOM_COLOR,
              name: '前月比',
              hide: hiddenSeries.has('mom'),
            },
          ],
          yAxisFormatter: (v: number) => `${v}k`,
          tooltipValueFormatter: (v: number) => `${v.toFixed(1)}k`,
          yDomain: ['dataMin - 10', 'dataMax + 10'] as [string, string],
        }
      case 'yoy':
        return {
          lines: [
            {
              dataKey: 'yoy',
              color: YOY_COLOR,
              name: '前年比（%）',
              hide: hiddenSeries.has('yoy'),
            },
          ],
          yAxisFormatter: (v: number) => `${v}%`,
          tooltipValueFormatter: (v: number) => `${v.toFixed(2)}%`,
          yDomain: ['dataMin - 5', 'dataMax + 5'] as [string, string],
        }
      default:
        return {
          lines: [
            {
              dataKey: 'value',
              color: CHART_COLOR,
              name: '失業給付申請件数',
              hide: hiddenSeries.has('value'),
            },
          ],
          yAxisFormatter: (v: number) => `${v}k`,
          tooltipValueFormatter: (v: number) => `${v.toFixed(1)}k`,
          yDomain: ['dataMin - 50', 'dataMax + 50'] as [string, string],
        }
    }
  }

  const chartConfig = getChartConfig()

  return (
    <div id="uk-ons-claimant-count-chart">
      <ChartContainer
        title="失業給付申請件数"
        showPeriodSelector={false}
        dataSource="ONS"
        sourceUrl="https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/bulletins/uklabourmarket/latest"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={getLatestValue()}
          valueColor={(viewMode === 'mom' || viewMode === 'mom_table') ? MOM_COLOR : viewMode === 'yoy' ? YOY_COLOR : CHART_COLOR}
          date={latest?.date}
          nextRelease={data.next_release}
          format={getValueFormat()}
          decimals={viewMode === 'yoy' ? 2 : 1}
          unit={getUnit()}
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
                  <div style={{ marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      currentMode={viewMode}
                      onChange={setViewMode}
                      options={[
                        { mode: 'mom', label: '前月比グラフ' },
                        { mode: 'mom_table', label: '前月比テーブル' },
                        { mode: 'yoy', label: '前年比' },
                        { mode: 'value', label: '原数値' },
                      ]}
                    />
                  </div>

                  {/* チャート表示（原数値/前月比グラフ/前年比） */}
                  {(viewMode === 'value' || viewMode === 'mom' || viewMode === 'yoy') && (
                    <>
                      {/* 期間セレクター */}
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
                        lines={chartConfig.lines}
                        yAxisFormatter={chartConfig.yAxisFormatter}
                        tooltipValueFormatter={chartConfig.tooltipValueFormatter}
                        onLegendClick={handleLegendClick}
                        yDomain={chartConfig.yDomain}
                      />
                    </>
                  )}

                  {/* 前月増減幅テーブル */}
                  {viewMode === 'mom_table' && (
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
                <MarketImpactTab indicatorId="ons_claimant_count" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
