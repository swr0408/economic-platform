/**
 * AU Quarterly CPI Chart Component
 * オーストラリア四半期消費者物価指数チャート
 *
 * データ項目:
 * - cpi_qoq: 総合CPI（原系列）前期比
 * - cpi_yoy: 総合CPI（原系列）前年比（Index計算）
 * - cpi_sa_yoy: 総合CPI（季節調整済み）前年比
 * - trimmed_mean_yoy: トリム平均 前年比
 * - weighted_median_yoy: 加重中央値 前年比
 * - trimmed_mean_qoq: トリム平均 前期比 (RBA G1)
 * - weighted_median_qoq: 加重中央値 前期比 (RBA G1)
 *
 * データソース: Australian Bureau of Statistics (ABS) + RBA
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
  useMultiValueQuarterlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  ViewModeButtonGroup,
  DataTypeButtonGroup,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { QuarterlyTableWithDataTypes } from '../../usa/common/QuarterlyTable'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { AuQuarterlyCpiData, AuQuarterlyCpiDataPoint } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface ChartDataPoint {
  date: string
  cpi_qoq: number | null
  cpi_yoy: number | null
  cpi_sa_yoy: number | null
  trimmed_mean_yoy: number | null
  weighted_median_yoy: number | null
  trimmed_mean_qoq: number | null
  weighted_median_qoq: number | null
}

interface AuQuarterlyCpiChartProps {
  data: AuQuarterlyCpiData | null
}

// データ種別
type DataKind = 'yoy' | 'qoq'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'qoq', label: '前期比' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// データタイプ（前年比用）
type YoyDataType = 'cpi' | 'cpi_sa' | 'trimmed_mean' | 'weighted_median'

const YOY_DATA_TYPE_OPTIONS: { type: YoyDataType; label: string }[] = [
  { type: 'cpi', label: '総合' },
  { type: 'cpi_sa', label: '総合(SA)' },
  { type: 'trimmed_mean', label: 'トリム平均' },
  { type: 'weighted_median', label: '加重中央値' },
]

// データタイプ（前期比用）
type QoqDataType = 'cpi' | 'trimmed_mean' | 'weighted_median'

const QOQ_DATA_TYPE_OPTIONS: { type: QoqDataType; label: string }[] = [
  { type: 'cpi', label: '総合' },
  { type: 'trimmed_mean', label: 'トリム平均' },
  { type: 'weighted_median', label: '加重中央値' },
]

// カラー設定
const COLORS = {
  cpi_yoy: CHART_COLORS.primary,
  cpi_qoq: CHART_COLORS.primary,
  cpi_sa_yoy: '#00BFFF',
  trimmed_mean_yoy: CHART_COLORS.positive,
  trimmed_mean_qoq: CHART_COLORS.positive,
  weighted_median_yoy: CHART_COLORS.purple,
  weighted_median_qoq: CHART_COLORS.purple,
}

// =============================================================================
// 日付フォーマット
// =============================================================================

const formatDateLabel = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  const month = date.getMonth() + 1
  const quarter = Math.ceil(month / 3)
  return `${date.getFullYear()}/Q${quarter}`
}

const formatDateLabelJP = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  const month = date.getMonth() + 1
  const quarter = Math.ceil(month / 3)
  return `${date.getFullYear()}年 Q${quarter}`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function AuQuarterlyCpiChart({ data }: AuQuarterlyCpiChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [yoyDataType, setYoyDataType] = useState<YoyDataType>('cpi')
  const [qoqDataType, setQoqDataType] = useState<QoqDataType>('cpi')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 'default',
    qoq: 5,
  })

  // データを変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((d: AuQuarterlyCpiDataPoint) =>
        d.cpi_qoq !== null || d.cpi_yoy !== null || d.cpi_sa_yoy !== null ||
        d.trimmed_mean_yoy !== null || d.weighted_median_yoy !== null ||
        d.trimmed_mean_qoq !== null || d.weighted_median_qoq !== null
      )
      .map((d: AuQuarterlyCpiDataPoint) => ({
        date: d.date,
        cpi_qoq: d.cpi_qoq,
        cpi_yoy: d.cpi_yoy,
        cpi_sa_yoy: d.cpi_sa_yoy,
        trimmed_mean_yoy: d.trimmed_mean_yoy,
        weighted_median_yoy: d.weighted_median_yoy,
        trimmed_mean_qoq: d.trimmed_mean_qoq,
        weighted_median_qoq: d.weighted_median_qoq,
      }))
  }, [data])

  // データを日付昇順にソート
  const sortedData = useSortedData(chartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ（3種類のQoQ）
  const qoqTableData = useMultiValueQuarterlyTableData(
    sortedData,
    {
      cpi: (item: ChartDataPoint) => item.cpi_qoq,
      trimmed_mean: (item: ChartDataPoint) => item.trimmed_mean_qoq,
      weighted_median: (item: ChartDataPoint) => item.weighted_median_qoq,
    },
    10
  )

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="四半期CPI" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="四半期CPI" showPeriodSelector={false} showDataSource={false}>
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
    <div id="au-quarterly-cpi-chart">
      <ChartContainer
        title="四半期CPI"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="Australian Bureau of Statistics"
        sourceUrl="https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '総合（QoQ）',
              value: latest?.cpi_qoq,
              color: COLORS.cpi_qoq,
              format: 'percent',
            },
            {
              label: 'TM（QoQ）',
              value: latest?.trimmed_mean_qoq,
              color: COLORS.trimmed_mean_qoq,
              format: 'percent',
            },
            {
              label: 'WM（QoQ）',
              value: latest?.weighted_median_qoq,
              color: COLORS.weighted_median_qoq,
              format: 'percent',
            },
            {
              label: '総合（YoY）',
              value: latest?.cpi_yoy,
              color: COLORS.cpi_yoy,
              format: 'percent',
            },
            {
              label: '総合SA',
              value: latest?.cpi_sa_yoy,
              color: COLORS.cpi_sa_yoy,
              format: 'percent',
            },
            {
              label: 'トリム平均',
              value: latest?.trimmed_mean_yoy,
              color: COLORS.trimmed_mean_yoy,
              format: 'percent',
            },
            {
              label: '加重中央値',
              value: latest?.weighted_median_yoy,
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
                        onClick={() => window.open('/compare?s=au_quarterly_cpi_yoy', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
                  {/* 下段: 表示形式（変動系のときのみ） */}
                  {dataKind === 'qoq' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 前年比グラフ（折れ線グラフ） */}
                  {dataKind === 'yoy' && (
                    <>
                      <DataTypeButtonGroup
                        options={YOY_DATA_TYPE_OPTIONS}
                        currentType={yoyDataType}
                        onChange={setYoyDataType}
                      />
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={
                          yoyDataType === 'cpi'
                            ? [{ dataKey: 'cpi_yoy', color: COLORS.cpi_yoy, name: '総合（前年比）', hide: hiddenSeries.has('cpi_yoy') }]
                            : yoyDataType === 'cpi_sa'
                            ? [{ dataKey: 'cpi_sa_yoy', color: COLORS.cpi_sa_yoy, name: '総合SA（前年比）', hide: hiddenSeries.has('cpi_sa_yoy') }]
                            : yoyDataType === 'trimmed_mean'
                            ? [{ dataKey: 'trimmed_mean_yoy', color: COLORS.trimmed_mean_yoy, name: 'トリム平均（前年比）', hide: hiddenSeries.has('trimmed_mean_yoy') }]
                            : [{ dataKey: 'weighted_median_yoy', color: COLORS.weighted_median_yoy, name: '加重中央値（前年比）', hide: hiddenSeries.has('weighted_median_yoy') }]
                        }
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                        onLegendClick={handleLegendClick}
                      />
                    </>
                  )}

                  {/* 前期比ヒートマップ */}
                  {dataKind === 'qoq' && displayMode === 'heatmap' && (
                    <QuarterlyTableWithDataTypes
                      data={qoqTableData}
                      dataTypes={[
                        { type: 'cpi', label: '総合（QoQ）' },
                        { type: 'trimmed_mean', label: 'トリム平均（QoQ）' },
                        { type: 'weighted_median', label: '加重中央値（QoQ）' },
                      ]}
                      selectedType={qoqDataType}
                      onTypeChange={(t) => setQoqDataType(t as QoqDataType)}
                      decimals={1}
                      helperText="※ 直近10年間のデータ（単位: %）"
                    />
                  )}

                  {/* 前期比グラフ（棒グラフ） */}
                  {dataKind === 'qoq' && displayMode === 'chart' && (
                    <>
                      <DataTypeButtonGroup
                        options={QOQ_DATA_TYPE_OPTIONS}
                        currentType={qoqDataType}
                        onChange={setQoqDataType}
                      />
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={
                          qoqDataType === 'cpi'
                            ? [{ dataKey: 'cpi_qoq', color: COLORS.cpi_qoq, name: '総合（前期比）' }]
                            : qoqDataType === 'trimmed_mean'
                            ? [{ dataKey: 'trimmed_mean_qoq', color: COLORS.trimmed_mean_qoq, name: 'トリム平均（前期比）' }]
                            : [{ dataKey: 'weighted_median_qoq', color: COLORS.weighted_median_qoq, name: '加重中央値（前期比）' }]
                        }
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
                <MarketImpactTab indicatorId="au_quarterly_cpi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
