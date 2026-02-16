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
type CPIViewMode = 'yoy' | 'mom_chart' | 'mom_table' | 'core'

// CPIビューモードオプション
const CPI_VIEW_MODE_OPTIONS: { mode: CPIViewMode; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom_chart', label: '前月比' },
  { mode: 'mom_table', label: '前月比（テーブル）' },
  { mode: 'core', label: 'コアCPI' },
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
  const [viewMode, setViewMode] = useState<CPIViewMode>('yoy')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom_chart: 3,
    mom_table: 'default',
    core: 'default',
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
    if (viewMode === 'yoy') {
      return '/compare?s=ca_cpi_yoy'
    } else if (viewMode === 'mom_chart' || viewMode === 'mom_table') {
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
          label={viewMode === 'yoy' ? 'CPI（前年比）' : (viewMode === 'mom_chart' || viewMode === 'mom_table') ? 'CPI（前月比）' : 'CPI-trim'}
          value={viewMode === 'yoy' ? latestValues?.yoy : (viewMode === 'mom_chart' || viewMode === 'mom_table') ? latestValues?.mom : latestValues?.trim}
          valueColor={viewMode === 'core' ? COLORS.trim : COLORS.yoy}
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
                  {/* ビューモード切替 */}
                  <ViewModeButtonGroup
                    currentMode={viewMode}
                    options={CPI_VIEW_MODE_OPTIONS}
                    onChange={(mode) => setViewMode(mode as CPIViewMode)}
                  />

                  {/* コントロールバー */}
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

                  {/* グラフ */}
                  {viewMode === 'yoy' && (
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

                  {viewMode === 'mom_chart' && (
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

                  {viewMode === 'mom_table' && (
                    <MonthlyTable data={momTableData} />
                  )}

                  {viewMode === 'core' && (
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
