/**
 * NZ NZIER企業景況指数チャートコンポーネント
 *
 * データ:
 * - value: NZIER Business Conditions Index（ネット%）
 * - qoq: 前期比（ポイント差分、フロントエンドで計算）
 *
 * データソース:
 * - NZIER Quarterly Survey of Business Opinion (QSBO)
 * - https://www.nzier.org.nz/
 *
 * FMPマッピング:
 * - Business Confidence (econalpha_id: nz_nzier_business_conditions_index)
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
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  ViewModeButtonGroup,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { QuarterlyTable } from '../../usa/common/QuarterlyTable'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { NzNzierBusinessConditionsIndexData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface ChartDataPoint {
  date: string
  value: number | null
  qoq: number | null
}

interface NzNzierBusinessConditionsIndexChartProps {
  data: NzNzierBusinessConditionsIndexData | null
}

// 指標種別
type DataType = 'index' | 'qoq'

const DATA_TYPE_OPTIONS: { mode: DataType; label: string }[] = [
  { mode: 'index', label: '指数' },
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
  index: '#16a34a',
  qoq: CHART_COLORS.primary,
}

// =============================================================================
// 日付フォーマット
// =============================================================================

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

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function NzNzierBusinessConditionsIndexChart({ data }: NzNzierBusinessConditionsIndexChartProps) {
  const [dataType, setDataType] = useState<DataType>('index')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // 指標種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataType, {
    qoq: 5,
    index: 20,
  })

  // データを変換（QoQはフロントエンドで計算）
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    // まず日付順にソート
    const sorted = [...data.data]
      .filter((d) => d.value !== null)
      .sort((a, b) => a.date.localeCompare(b.date))

    // QoQ（前期比）を計算
    return sorted.map((d, i) => ({
      date: d.date,
      value: d.value,
      qoq: i > 0 && sorted[i - 1].value !== null && d.value !== null
        ? Math.round((d.value - sorted[i - 1].value!) * 10) / 10
        : null,
    }))
  }, [data])

  // データを日付昇順にソート
  const sortedData = useSortedData(chartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // 前期比テーブル用データ
  const qoqTableData = useMemo(() => {
    const yearSet = new Set<number>()
    const quarterlyData: Record<number, Record<number, number | null>> = {}

    for (const item of sortedData) {
      if (!item.date || item.qoq === null) continue
      const [yearStr, monthStr] = item.date.split('-')
      const year = parseInt(yearStr, 10)
      const month = parseInt(monthStr, 10)
      const quarter = Math.ceil(month / 3) - 1 // 0-indexed

      yearSet.add(year)
      if (!quarterlyData[year]) quarterlyData[year] = {}
      quarterlyData[year][quarter] = item.qoq
    }

    const years = Array.from(yearSet).sort((a, b) => b - a).slice(0, 10)
    return { years, quarterlyData }
  }, [sortedData])

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="NZIER企業景況指数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="NZIER企業景況指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = sortedData[sortedData.length - 1]

  return (
    <div id="nzier-business-conditions">
      <ChartContainer
        title="NZIER企業景況指数"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="NZIER"
        sourceUrl="https://www.nzier.org.nz/publications/nziers-qsbo-shows-a-strong-rebound-in-confidence-as-recovery-starts-to-gain-traction"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: 'NZIER企業景況（QoQ）',
              value: latest?.qoq,
              color: COLORS.qoq,
              format: 'number',
              decimals: 1,
            },
            {
              label: 'NZIER企業景況指数',
              value: latest?.value,
              color: COLORS.index,
              format: 'number',
              decimals: 1,
            },
          ]}
          date={latest?.date}
          dateFormatter={formatQuarterLabelJP}
          nextRelease={data?.next_release ?? undefined}
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
                    <ViewModeButtonGroup options={DATA_TYPE_OPTIONS} currentMode={dataType} onChange={setDataType} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=nz_nzier_business_conditions_index', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 下段: 表示形式（前期比のときのみ） */}
                  {dataType === 'qoq' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 指数（折れ線グラフ） */}
                  {dataType === 'index' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'value', color: COLORS.index, name: 'NZIER企業景況指数', hide: hiddenSeries.has('value') },
                        ]}
                        yAxisFormatter={(v) => `${v}`}
                        yDomain={['dataMin - 10', 'dataMax + 10']}
                        showZeroLine={true}
                        xAxisFormatter={formatQuarterLabel}
                        tooltipLabelFormatter={formatQuarterLabelJP}
                        tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
                        onLegendClick={handleLegendClick}
                      />
                    </>
                  )}

                  {/* 前期比チャート（棒グラフ） */}
                  {dataType === 'qoq' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'qoq', color: COLORS.qoq, name: 'NZIER企業景況（前期比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}`}
                        yDomain={['dataMin - 5', 'dataMax + 5']}
                        xAxisFormatter={formatQuarterLabel}
                        tooltipLabelFormatter={formatQuarterLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}pt`}
                      />
                    </>
                  )}

                  {/* 前期比ヒートマップ */}
                  {dataType === 'qoq' && displayMode === 'heatmap' && (
                    <QuarterlyTable
                      data={qoqTableData}
                      decimals={1}
                      helperText="※ 直近10年間の前期比データ（単位: ポイント）"
                      formatValue={(v) => {
                        if (v === null || v === undefined) return '-'
                        return `${v >= 0 ? '+' : ''}${v.toFixed(1)}`
                      }}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="nz_nzier_business_conditions_index" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
