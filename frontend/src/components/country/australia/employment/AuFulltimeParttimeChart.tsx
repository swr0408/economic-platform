/**
 * AU Full-time/Part-time Employment Chart Component
 * オーストラリア フルタイム/パートタイム雇用者数チャート
 *
 * データ項目:
 * - fulltime / parttime: 雇用者数（千人、季節調整済み）
 * - fulltime_mom / parttime_mom: 前月増減（千人）
 * - fulltime_yoy / parttime_yoy: 前年比（%）
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

import type { AuFulltimeParttimeData, AuFulltimeParttimeDataPoint } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface ChartDataPoint {
  date: string
  fulltime: number | null
  parttime: number | null
  fulltime_mom: number | null
  parttime_mom: number | null
  fulltime_yoy: number | null
  parttime_yoy: number | null
  [key: string]: unknown
}

interface AuFulltimeParttimeChartProps {
  data: AuFulltimeParttimeData | null
}

// カラー設定
const COLORS = {
  fulltime: '#2E86C1',
  parttime: '#E74C3C',
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

// ヒートマップ用データ種別
type HeatmapType = 'ft' | 'pt'

const HEATMAP_TYPE_OPTIONS: { mode: HeatmapType; label: string }[] = [
  { mode: 'ft', label: 'フルタイム' },
  { mode: 'pt', label: 'パートタイム' },
]

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function AuFulltimeParttimeChart({ data }: AuFulltimeParttimeChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('mom')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [heatmapType, setHeatmapType] = useState<HeatmapType>('ft')

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    value: 10,
    mom: 3,
    yoy: 10,
  })

  // データを変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((d: AuFulltimeParttimeDataPoint) => ({
      date: d.date,
      fulltime: d.fulltime,
      parttime: d.parttime,
      fulltime_mom: d.fulltime_mom,
      parttime_mom: d.parttime_mom,
      fulltime_yoy: d.fulltime_yoy,
      parttime_yoy: d.parttime_yoy,
    }))
  }, [data])

  // データを日付昇順にソート
  const sortedData = useSortedData(chartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ（フルタイム / パートタイム それぞれ）
  const ftTableData = useMonthlyTableData(sortedData, (item) => item.fulltime_mom)
  const ptTableData = useMonthlyTableData(sortedData, (item) => item.parttime_mom)

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="雇用者数（フルタイム/パートタイム）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="雇用者数（フルタイム/パートタイム）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  // データ種別に応じた最新値
  const currentLatestValue = (() => {
    if (!latest) return null
    if (dataKind === 'value') return latest.fulltime
    if (dataKind === 'mom') return latest.fulltime_mom
    if (dataKind === 'yoy') return latest.fulltime_yoy
    return latest.fulltime
  })()

  const getLatestLabel = () => {
    if (dataKind === 'value') return 'フルタイム雇用者数'
    if (dataKind === 'mom') return 'フルタイム（前月増減）'
    if (dataKind === 'yoy') return 'フルタイム（前年比）'
    return 'フルタイム雇用者数'
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
    <div id="au-fulltime-parttime-chart">
      <ChartContainer
        title="雇用者数（フルタイム/パートタイム）"
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
          valueColor={COLORS.fulltime}
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
                        onClick={() => window.open(
                          dataKind === 'yoy'
                            ? '/compare?s=au_fulltime_yoy&s=au_parttime_yoy'
                            : '/compare?s=au_fulltime&s=au_parttime',
                          '_blank'
                        )}
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

                  {/* ヒートマップ時のデータ種別選択 */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={HEATMAP_TYPE_OPTIONS} currentMode={heatmapType} onChange={setHeatmapType} />
                    </div>
                  )}

                  {/* 雇用者数（折れ線グラフ） */}
                  {dataKind === 'value' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'fulltime', color: COLORS.fulltime, name: 'フルタイム（千人）' },
                          { dataKey: 'parttime', color: COLORS.parttime, name: 'パートタイム（千人）', yAxisId: 'right' },
                        ]}
                        yAxisFormatter={(v) => `${(v / 1000).toFixed(1)}M`}
                        rightYAxisFormatter={(v) => `${(v / 1000).toFixed(1)}M`}
                        yDomain={['dataMin - 100', 'dataMax + 100']}
                        tooltipValueFormatter={(v) => `${v.toFixed(1)} 千人`}
                      />
                    </>
                  )}

                  {/* 前月増減（棒グラフ） */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'fulltime_mom', color: COLORS.fulltime, name: 'フルタイム増減（千人）' },
                          { dataKey: 'parttime_mom', color: COLORS.parttime, name: 'パートタイム増減（千人）' },
                        ]}
                        yAxisFormatter={(v) => `${v.toFixed(0)}`}
                        tooltipValueFormatter={(v) => `${v.toFixed(1)} 千人`}
                      />
                    </>
                  )}

                  {/* 前月増減ヒートマップ */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTable
                      data={heatmapType === 'ft' ? ftTableData : ptTableData}
                      decimals={1}
                      helperText={heatmapType === 'ft'
                        ? '※ 直近10年間のフルタイム前月増減幅データ（単位: 千人）'
                        : '※ 直近10年間のパートタイム前月増減幅データ（単位: 千人）'
                      }
                    />
                  )}

                  {/* 前年比（折れ線グラフ） */}
                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'fulltime_yoy', color: COLORS.fulltime, name: 'フルタイム前年比' },
                          { dataKey: 'parttime_yoy', color: COLORS.parttime, name: 'パートタイム前年比' },
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
