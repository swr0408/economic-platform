/**
 * NZ ANZ企業景況感指数チャートコンポーネント
 *
 * データ:
 * - value: ANZ Business Confidence Index
 * - mom: 前月比（ポイント差分、フロントエンドで計算）
 *
 * データソース:
 * - ANZ Business Outlook Survey
 * - https://www.anz.co.nz/about-us/economic-markets-research/business-outlook/
 *
 * FMPマッピング:
 * - ANZ Business Confidence (econalpha_id: nz_anz_corporate business_sentiment)
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
  useMonthlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  ViewModeButtonGroup,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { NzAnzBusinessOutlookSurveyData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface ChartDataPoint {
  date: string
  value: number | null
  mom: number | null
}

interface NzAnzBusinessOutlookSurveyChartProps {
  data: NzAnzBusinessOutlookSurveyData | null
}

// 指標種別
type DataType = 'index' | 'mom'

const DATA_TYPE_OPTIONS: { mode: DataType; label: string }[] = [
  { mode: 'index', label: '指数' },
  { mode: 'mom', label: '前月比' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// カラー設定
const COLORS = {
  index: '#3c8dff',
  mom: CHART_COLORS.primary,
}

// =============================================================================
// 日付フォーマット
// =============================================================================

const formatDateLabel = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}/${String(date.getMonth() + 1).padStart(2, '0')}`
}

const formatDateLabelJP = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}年${date.getMonth() + 1}月`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function NzAnzBusinessOutlookSurveyChart({ data }: NzAnzBusinessOutlookSurveyChartProps) {
  const [dataType, setDataType] = useState<DataType>('index')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // 指標種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataType, {
    mom: 3,
    index: 10,
  })

  // データを変換（MoMはフロントエンドで計算）
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    // まず日付順にソート
    const sorted = [...data.data]
      .filter((d) => d.value !== null)
      .sort((a, b) => a.date.localeCompare(b.date))

    // MoM（前月比）を計算
    return sorted.map((d, i) => ({
      date: d.date,
      value: d.value,
      mom: i > 0 && sorted[i - 1].value !== null && d.value !== null
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

  // テーブル用データ
  const momTableData = useMonthlyTableData(sortedData, (item: ChartDataPoint) => item.mom)

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="ANZ企業景況感指数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="ANZ企業景況感指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = sortedData[sortedData.length - 1]

  return (
    <div id="anz-business-outlook-survey">
      <ChartContainer
        title="ANZ企業景況感指数"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="ANZ"
        sourceUrl="https://www.anz.co.nz/about-us/economic-markets-research/business-outlook/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: 'ANZ企業景況感（MoM）',
              value: latest?.mom,
              color: COLORS.mom,
              format: 'number',
              decimals: 1,
            },
            {
              label: 'ANZ企業景況感指数',
              value: latest?.value,
              color: COLORS.index,
              format: 'number',
              decimals: 1,
            },
          ]}
          date={latest?.date}
          dateFormatter={formatDateLabelJP}
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
                        onClick={() => window.open('/compare?s=nz_anz_business_outlook_survey', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 下段: 表示形式（前月比のときのみ） */}
                  {dataType === 'mom' && (
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
                          { dataKey: 'value', color: COLORS.index, name: 'ANZ企業景況感指数', hide: hiddenSeries.has('value') },
                        ]}
                        yAxisFormatter={(v) => `${v}`}
                        yDomain={['dataMin - 10', 'dataMax + 10']}
                        showZeroLine={true}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateLabelJP}
                        tooltipValueFormatter={(v) => `${v.toFixed(1)}`}
                        onLegendClick={handleLegendClick}
                      />
                    </>
                  )}

                  {/* 前月比チャート（棒グラフ） */}
                  {dataType === 'mom' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'mom', color: COLORS.mom, name: 'ANZ企業景況感（前月比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}`}
                        yDomain={['dataMin - 5', 'dataMax + 5']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}pt`}
                      />
                    </>
                  )}

                  {/* 前月比ヒートマップ */}
                  {dataType === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTable
                      data={momTableData}
                      decimals={1}
                      helperText="※ 直近10年間の前月比データ（単位: ポイント）"
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="nz_anz_corporate business_sentiment" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
