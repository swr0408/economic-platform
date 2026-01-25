/**
 * 新築住宅販売戸数チャートコンポーネント
 *
 * FRED HSN1Fから取得した新築一戸建て住宅販売戸数を表示
 * データソース: FRED (HSN1F)
 *
 * タブ切り替え:
 * - 時系列: 現数値グラフ、前年比グラフ、前月比テーブル、前月比グラフ
 * - マーケットインパクト: 発表時の市場への影響分析
 */
import { useState } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { NewHomeSalesData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMonthlyTableData,
  useHiddenSeries,
} from '../common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
  StandardBarChart,
} from '../common/ChartComponents'
import { MonthlyTable } from '../common/MonthlyTable'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// =============================================================================
// 型定義
// =============================================================================

interface NewHomeSalesChartProps {
  newHomeSalesData: NewHomeSalesData | null
}

type ViewMode = 'value' | 'yoy' | 'mom_table' | 'mom_chart'

// カラー設定
const COLORS = {
  value: '#10b981',  // エメラルドグリーン（現数値）
  yoy: '#1890ff',    // 青（前年比）
  mom: '#52c41a',    // 緑（前月比）
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function NewHomeSalesChart({ newHomeSalesData }: NewHomeSalesChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('value')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    value: 'default',
    yoy: 'default',
    mom_table: 'default',
    mom_chart: 3,
  })

  // データを日付昇順にソート
  const chartData = useSortedData(newHomeSalesData?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ（年別×月別のマトリックス）
  const momTableData = useMonthlyTableData(chartData, (item) => item.mom)

  const hasData = chartData.length > 0

  // ローディング状態
  if (newHomeSalesData === null) {
    return <LoadingChart title="新築住宅販売戸数 (HSN1F)" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="新築住宅販売戸数 (HSN1F)" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = newHomeSalesData.latest

  // 最新値の表示内容を決定
  const getLatestDisplayValue = () => {
    if (viewMode === 'value') {
      return latest?.value
    } else if (viewMode === 'yoy') {
      return latest?.yoy
    } else {
      return latest?.mom
    }
  }

  const getLatestColor = () => {
    if (viewMode === 'value') return COLORS.value
    if (viewMode === 'yoy') return COLORS.yoy
    return COLORS.mom
  }

  const getLatestUnit = () => {
    if (viewMode === 'value') return 'k'
    return undefined  // パーセントはformat="percent"で処理
  }

  const getLatestFormat = (): 'percent' | 'number' | 'raw' => {
    if (viewMode === 'value') return 'number'
    return 'percent'
  }

  return (
    <div id="new-home-sales">
      <ChartContainer
        title="新築住宅販売戸数"
        showPeriodSelector={false}
        dataSource="Census Bureau"
        sourceUrl="https://www.census.gov/construction/nrs/index.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={getLatestDisplayValue()}
          valueColor={getLatestColor()}
          unit={getLatestUnit()}
          date={latest?.date}
          nextRelease={newHomeSalesData?.next_release}
          format={getLatestFormat()}
          decimals={viewMode === 'value' ? 0 : 1}
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
                  <ViewModeButtonGroup
                    currentMode={viewMode}
                    onChange={(mode) => setViewMode(mode)}
                    options={[
                      { mode: 'value', label: '現数値' },
                      { mode: 'yoy', label: '前年比' },
                      { mode: 'mom_chart', label: '前月比' },
                      { mode: 'mom_table', label: '前月比（テーブル）' },
                    ]}
                  />

                  {/* 期間セレクター */}
                  {(viewMode === 'value' || viewMode === 'yoy' || viewMode === 'mom_chart') && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <Tooltip title="比較ページを開く（新築住宅販売戸数）">
                        <Button
                          icon={<AreaChartOutlined />}
                          onClick={() => window.open('/compare?s=new_home_sales', '_blank')}
                        >
                          データ比較
                        </Button>
                      </Tooltip>
                    </div>
                  )}

                  {/* コンテンツ表示 */}
                  {viewMode === 'mom_table' && <MonthlyTable data={momTableData} />}

                  {viewMode === 'value' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'value', color: COLORS.value, name: '販売戸数（千戸）', hide: hiddenSeries.has('value') },
                      ]}
                      yAxisFormatter={(v) => `${v}`}
                      tooltipValueFormatter={(v) => `${v.toLocaleString()}k`}
                      onLegendClick={handleLegendClick}
                      showZeroLine={false}
                      yDomain={['dataMin - 25', 'dataMax + 25']}
                    />
                  )}

                  {viewMode === 'yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'yoy', color: COLORS.yoy, name: '前年比', hide: hiddenSeries.has('yoy') },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      onLegendClick={handleLegendClick}
                      yDomain={['dataMin - 5', 'dataMax + 5']}
                    />
                  )}

                  {viewMode === 'mom_chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'mom', color: COLORS.mom, name: '前月比' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="new_home_sales" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
