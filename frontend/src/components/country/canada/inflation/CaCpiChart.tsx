/**
 * カナダ消費者物価指数（CPI）チャートコンポーネント
 *
 * 総合CPI（前年比・前月比）とコアCPI指標（trim, median, common）を表示
 *
 * データソース:
 * - Statistics Canada Table 18-10-0004-01 (YoY)
 * - Statistics Canada Table 18-10-0006-01 (Index for MoM)
 * - Statistics Canada Table 18-10-0256-02 (trim, median, common)
 *
 * 発表スケジュール:
 * - 毎月中旬
 * - 発表時刻: 08:30 ET
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { CaCpiData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
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
  SimpleLatestValueBox,
  ViewModeButtonGroup,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import MonthlyTable from '../../usa/common/MonthlyTable'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// =============================================================================
// 型定義
// =============================================================================

interface CaCpiChartProps {
  data: CaCpiData | null
}

// CPI表示モード
type DataKind = 'yoy' | 'mom' | 'core'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
  { mode: 'core', label: 'コアCPI' },
]

type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// カラー設定
const COLORS = {
  yoy: '#DC143C',  // カナダカラー（クリムゾン）
  mom: '#DC143C',
  trim: CHART_COLORS.purple,
  median: CHART_COLORS.positive,
  common: CHART_COLORS.orange,
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CaCpiChart({ data }: CaCpiChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 10,
    mom: 3,
    core: 10,
  })

  // データを日付昇順にソート
  const sortedData = useSortedData(data?.data)

  // チャート用データに変換
  const chartData = useMemo(() => {
    return sortedData.map(item => ({
      date: item.date,
      yoy: item.yoy ?? null,
      mom: item.mom ?? null,
      trim: item.trim ?? null,
      median: item.median ?? null,
      common: item.common ?? null,
    }))
  }, [sortedData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValues = useMemo(() => {
    if (!data?.latest) return null
    return data.latest
  }, [data])

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="カナダCPI" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="カナダCPI" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // MoMテーブル用データ
  const momTableData = useMonthlyTableData(
    chartData,
    (item) => item.mom,
    10
  )

  // 比較ボタンのURLを生成
  const getCompareUrl = () => {
    if (dataKind === 'yoy') {
      return '/compare?s=ca_cpi_yoy'
    } else if (dataKind === 'mom') {
      return '/compare?s=ca_cpi_mom'
    } else {
      return '/compare?s=ca_cpi_trim&s=ca_cpi_median&s=ca_cpi_common'
    }
  }

  return (
    <div id="ca-cpi-chart">
      <ChartContainer
        title="カナダCPI"
        showPeriodSelector={false}
        dataSource="Statistics Canada"
        sourceUrl="https://www.statcan.gc.ca/en/subjects-start/prices_and_price_indexes/consumer_price_indexes"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={dataKind === 'yoy' ? 'CPI（前年比）' : dataKind === 'mom' ? 'CPI（前月比）' : 'CPI-trim'}
          value={dataKind === 'yoy' ? latestValues?.yoy : dataKind === 'mom' ? latestValues?.mom : latestValues?.trim}
          valueColor={dataKind === 'core' ? COLORS.trim : COLORS.yoy}
          date={latestValues?.date}
          nextRelease={data.next_release ? {
            date: data.next_release.date,
            label: data.next_release.time_jst ? `${data.next_release.time_jst} JST` : undefined
          } : null}
          format="percent"
          decimals={2}
        />

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* 上段: データ種別 */}
                  <div style={{ marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      currentMode={dataKind}
                      options={DATA_KIND_OPTIONS}
                      onChange={setDataKind}
                    />
                  </div>

                  {/* 下段: 表示形式（momのときのみ） */}
                  {dataKind === 'mom' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* コントロールバー（ヒートマップ以外で表示） */}
                  {!(dataKind === 'mom' && displayMode === 'heatmap') && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <Tooltip title="比較ページを開く">
                        <Button
                          icon={<AreaChartOutlined />}
                          onClick={() => window.open(getCompareUrl(), '_blank')}
                        >
                          データ比較
                        </Button>
                      </Tooltip>
                    </div>
                  )}

                  {/* グラフ */}
                  {dataKind === 'yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'yoy', color: COLORS.yoy, name: 'CPI（前年比）', hide: hiddenSeries.has('yoy') },
                      ]}
                      yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                      yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                      showZeroLine={true}
                      onLegendClick={handleLegendClick}
                    />
                  )}

                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'mom', color: COLORS.mom, name: 'CPI（前月比）' },
                      ]}
                      yAxisFormatter={(v) => `${v.toFixed(2)}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                      showZeroLine={true}
                    />
                  )}

                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTable data={momTableData} />
                  )}

                  {dataKind === 'core' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'trim', color: COLORS.trim, name: 'CPI-trim', hide: hiddenSeries.has('trim') },
                        { dataKey: 'median', color: COLORS.median, name: 'CPI-median', hide: hiddenSeries.has('median') },
                        { dataKey: 'common', color: COLORS.common, name: 'CPI-common', hide: hiddenSeries.has('common') },
                      ]}
                      yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                      yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                      showZeroLine={true}
                      onLegendClick={handleLegendClick}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="ca_cpi" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
