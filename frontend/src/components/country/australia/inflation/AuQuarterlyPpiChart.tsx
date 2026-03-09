/**
 * AU Quarterly PPI Chart Component
 * オーストラリア四半期生産者物価指数チャート
 *
 * データ項目:
 * - ppi_qoq: PPI 前期比
 * - ppi_yoy: PPI 前年比
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
  useMultiValueQuarterlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  ViewModeButtonGroup,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { QuarterlyTableWithDataTypes } from '../../usa/common/QuarterlyTable'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { AuQuarterlyPpiData, AuQuarterlyPpiDataPoint } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface ChartDataPoint {
  date: string
  ppi_qoq: number | null
  ppi_yoy: number | null
}

interface AuQuarterlyPpiChartProps {
  data: AuQuarterlyPpiData | null
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

// カラー設定
const COLORS = {
  ppi_yoy: CHART_COLORS.primary,
  ppi_qoq: CHART_COLORS.primary,
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

export default function AuQuarterlyPpiChart({ data }: AuQuarterlyPpiChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [tableDataType, setTableDataType] = useState<string>('qoq')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 20,
    qoq: 5,
  })

  // データを変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((d: AuQuarterlyPpiDataPoint) =>
        d.ppi_qoq !== null || d.ppi_yoy !== null
      )
      .map((d: AuQuarterlyPpiDataPoint) => ({
        date: d.date,
        ppi_qoq: d.ppi_qoq,
        ppi_yoy: d.ppi_yoy,
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
  const qoqTableData = useMultiValueQuarterlyTableData(
    sortedData,
    {
      qoq: (item: ChartDataPoint) => item.ppi_qoq,
      yoy: (item: ChartDataPoint) => item.ppi_yoy,
    },
    10
  )

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="四半期PPI" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="四半期PPI" showPeriodSelector={false} showDataSource={false}>
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
    <div id="au-quarterly-ppi-chart">
      <ChartContainer
        title="PPI"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="Australian Bureau of Statistics"
        sourceUrl="https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/producer-price-indexes-australia"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: 'PPI（QoQ）',
              value: latest?.ppi_qoq,
              color: COLORS.ppi_qoq,
              format: 'percent',
            },
            {
              label: 'PPI（YoY）',
              value: latest?.ppi_yoy,
              color: COLORS.ppi_yoy,
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
                        onClick={() => window.open('/compare?s=au_quarterly_ppi_yoy', '_blank')}
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
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'ppi_yoy', color: COLORS.ppi_yoy, name: 'PPI（前年比）', hide: hiddenSeries.has('ppi_yoy') },
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

                  {/* ヒートマップ */}
                  {dataKind === 'qoq' && displayMode === 'heatmap' && (
                    <QuarterlyTableWithDataTypes
                      data={qoqTableData}
                      dataTypes={[
                        { type: 'qoq', label: 'PPI（QoQ）' },
                        { type: 'yoy', label: 'PPI（YoY）' },
                      ]}
                      selectedType={tableDataType}
                      onTypeChange={setTableDataType}
                      decimals={1}
                      helperText="※ 直近10年間のデータ（単位: %）"
                    />
                  )}

                  {/* 前期比グラフ（棒グラフ） */}
                  {dataKind === 'qoq' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'ppi_qoq', color: COLORS.ppi_qoq, name: 'PPI（前期比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
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
                <MarketImpactTab indicatorId="au_quarterly_ppi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
