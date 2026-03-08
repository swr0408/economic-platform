/**
 * AU Monthly CPI Chart Component
 * オーストラリア月次消費者物価指数チャート
 *
 * データ項目:
 * - cpi_yoy/mom: 総合CPI（季節調整済み）
 * - trimmed_mean_yoy/mom: トリム平均
 * - weighted_median_yoy/mom: 加重中央値
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
  CHART_COLORS,
} from '../../usa/common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useHiddenSeries,
  useMultiValueMonthlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  ViewModeButtonGroup,
  DataTypeButtonGroup,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTableWithDataTypes } from '../../usa/common/MonthlyTable'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { AuMonthlyCpiData, AuMonthlyCpiDataPoint } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface ChartDataPoint {
  date: string
  cpi_yoy: number | null
  cpi_mom: number | null
  trimmed_mean_yoy: number | null
  trimmed_mean_mom: number | null
  weighted_median_yoy: number | null
  weighted_median_mom: number | null
}

interface AuMonthlyCpiChartProps {
  data: AuMonthlyCpiData | null
}

// データ種別
type DataKind = 'yoy' | 'mom'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// データタイプ
type CpiDataType = 'cpi' | 'trimmed_mean' | 'weighted_median'

const CPI_DATA_TYPE_OPTIONS: { type: CpiDataType; label: string }[] = [
  { type: 'cpi', label: '総合' },
  { type: 'trimmed_mean', label: 'トリム平均' },
  { type: 'weighted_median', label: '加重中央値' },
]

// カラー設定
const COLORS = {
  cpi_yoy: CHART_COLORS.primary,
  cpi_mom: CHART_COLORS.primary,
  trimmed_mean_yoy: CHART_COLORS.positive,
  trimmed_mean_mom: CHART_COLORS.positive,
  weighted_median_yoy: CHART_COLORS.purple,
  weighted_median_mom: CHART_COLORS.purple,
}

// =============================================================================
// 日付フォーマット
// =============================================================================

const formatDateLabel = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
}

const formatDateLabelJP = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}年${date.getMonth() + 1}月`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function AuMonthlyCpiChart({ data }: AuMonthlyCpiChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [dataType, setDataType] = useState<CpiDataType>('cpi')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 'default',
    mom: 3,
  })

  // データを変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((d: AuMonthlyCpiDataPoint) => d.cpi_yoy !== null || d.cpi_mom !== null)
      .map((d: AuMonthlyCpiDataPoint) => ({
        date: d.date,
        cpi_yoy: d.cpi_yoy,
        cpi_mom: d.cpi_mom,
        trimmed_mean_yoy: d.trimmed_mean_yoy,
        trimmed_mean_mom: d.trimmed_mean_mom,
        weighted_median_yoy: d.weighted_median_yoy,
        weighted_median_mom: d.weighted_median_mom,
      }))
  }, [data])

  // データを日付昇順にソート
  const sortedData = useSortedData(chartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2019,
  })

  // テーブル用データ
  const momTableData = useMultiValueMonthlyTableData(
    sortedData,
    {
      cpi: (item: ChartDataPoint) => item.cpi_mom,
      trimmed_mean: (item: ChartDataPoint) => item.trimmed_mean_mom,
      weighted_median: (item: ChartDataPoint) => item.weighted_median_mom,
    },
    10
  )

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="月次CPI" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="月次CPI" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  // 次回発表日のフォーマット
  const formatNextRelease = () => {
    if (!data?.next_release) return null
    const nr = data.next_release
    if (nr.date) {
      const dt = new Date(nr.date)
      return `${dt.getMonth() + 1}/${dt.getDate()}`
    }
    return null
  }

  return (
    <div id="au-monthly-cpi-chart">
      <ChartContainer
        title="月次CPI"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="Australian Bureau of Statistics"
        sourceUrl="https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/monthly-consumer-price-index-indicator"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '総合(SA)',
              value: dataKind === 'yoy' ? latest?.cpi_yoy : latest?.cpi_mom,
              color: COLORS.cpi_yoy,
              format: 'percent',
            },
            {
              label: 'トリム平均',
              value: dataKind === 'yoy' ? latest?.trimmed_mean_yoy : latest?.trimmed_mean_mom,
              color: COLORS.trimmed_mean_yoy,
              format: 'percent',
            },
            {
              label: '加重中央値',
              value: dataKind === 'yoy' ? latest?.weighted_median_yoy : latest?.weighted_median_mom,
              color: COLORS.weighted_median_yoy,
              format: 'percent',
            },
          ]}
          date={latest?.date}
          dateFormatter={formatDateLabelJP}
          nextRelease={data?.next_release ? { date: formatNextRelease() || '' } : undefined}
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
                    <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=au_monthly_cpi_yoy', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
                  {/* 下段: 表示形式（変動系のときのみ） */}
                  {dataKind === 'mom' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 前年比グラフ（折れ線グラフ） */}
                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'cpi_yoy', color: COLORS.cpi_yoy, name: '総合（前年比）', hide: hiddenSeries.has('cpi_yoy') },
                          { dataKey: 'trimmed_mean_yoy', color: COLORS.trimmed_mean_yoy, name: 'トリム平均（前年比）', hide: hiddenSeries.has('trimmed_mean_yoy') },
                          { dataKey: 'weighted_median_yoy', color: COLORS.weighted_median_yoy, name: '加重中央値（前年比）', hide: hiddenSeries.has('weighted_median_yoy') },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                        onLegendClick={handleLegendClick}
                      />
                    </>
                  )}

                  {/* 前月比ヒートマップ */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTableWithDataTypes
                      data={momTableData}
                      dataTypes={CPI_DATA_TYPE_OPTIONS}
                      selectedType={dataType}
                      onTypeChange={setDataType}
                      decimals={1}
                    />
                  )}

                  {/* 前月比グラフ（棒グラフ） */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <DataTypeButtonGroup options={CPI_DATA_TYPE_OPTIONS} currentType={dataType} onChange={setDataType} />
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          dataType === 'cpi'
                            ? { dataKey: 'cpi_mom', color: COLORS.cpi_mom, name: '総合（前月比）' }
                            : dataType === 'trimmed_mean'
                            ? { dataKey: 'trimmed_mean_mom', color: COLORS.trimmed_mean_mom, name: 'トリム平均（前月比）' }
                            : { dataKey: 'weighted_median_mom', color: COLORS.weighted_median_mom, name: '加重中央値（前月比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
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
                <MarketImpactTab indicatorId="au_monthly_cpi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
