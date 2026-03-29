/**
 * 中古住宅販売戸数チャートコンポーネント
 *
 * NARから取得した中古住宅販売戸数を表示
 * データソース: NAR / FMP
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
import type { ExistingHomeSalesData } from '../../../../hooks/useDashboardData'

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

interface ExistingHomeSalesChartProps {
  existingHomeSalesData: ExistingHomeSalesData | null
}

// 指標種別
type DataKind = 'value' | 'yoy' | 'mom'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'value', label: '現数値' },
  { mode: 'yoy', label: '前年比' },
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
  value: '#8b5cf6',  // パープル（現数値）
  yoy: '#1890ff',    // 青（前年比）
  mom: '#52c41a',    // 緑（前月比）
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function ExistingHomeSalesChart({ existingHomeSalesData }: ExistingHomeSalesChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('value')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // 指標種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    value: 10,
    yoy: 10,
    mom: 3,
  })

  // データを日付昇順にソート
  const chartData = useSortedData(existingHomeSalesData?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ（年別×月別のマトリックス）
  const momTableData = useMonthlyTableData(chartData, (item) => item.mom)

  const hasData = chartData.length > 0

  // ローディング状態
  if (existingHomeSalesData === null) {
    return <LoadingChart title="中古住宅販売戸数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="中古住宅販売戸数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = existingHomeSalesData.latest

  // 最新値の表示内容を決定
  const getLatestDisplayValue = () => {
    if (dataKind === 'value') {
      return latest?.value
    } else if (dataKind === 'yoy') {
      return latest?.yoy
    } else {
      return latest?.mom
    }
  }

  const getLatestColor = () => {
    if (dataKind === 'value') return COLORS.value
    if (dataKind === 'yoy') return COLORS.yoy
    return COLORS.mom
  }

  const getLatestUnit = () => {
    if (dataKind === 'value') return 'M'
    return undefined  // パーセントはformat="percent"で処理
  }

  const getLatestFormat = (): 'percent' | 'number' | 'raw' => {
    if (dataKind === 'value') return 'number'
    return 'percent'
  }

  return (
    <div id="existing-home-sales">
      <ChartContainer
        title="中古住宅販売戸数"
        showPeriodSelector={false}
        dataSource="NAR"
        sourceUrl="https://www.nar.realtor/research-and-statistics/housing-statistics/existing-home-sales"
        handbookId="existing-home-sales"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={getLatestDisplayValue()}
          valueColor={getLatestColor()}
          unit={getLatestUnit()}
          date={latest?.date}
          nextRelease={existingHomeSalesData?.next_release}
          format={getLatestFormat()}
          decimals={dataKind === 'value' ? 2 : 1}
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
                    <Tooltip title="比較ページを開く（中古住宅販売戸数）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=existing_home_sales', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 下段: 表示形式（前月比のときのみ） */}
                  {dataKind === 'mom' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 前月比ヒートマップ */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && <MonthlyTable data={momTableData} />}

                  {/* 現数値グラフ */}
                  {dataKind === 'value' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'value', color: COLORS.value, name: '販売戸数（百万戸）', hide: hiddenSeries.has('value') },
                      ]}
                      yAxisFormatter={(v) => `${v}`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}M`}
                      onLegendClick={handleLegendClick}
                      showZeroLine={false}
                      yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                    />
                    </>
                  )}

                  {/* 前年比グラフ */}
                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'yoy', color: COLORS.yoy, name: '前年比', hide: hiddenSeries.has('yoy') },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      onLegendClick={handleLegendClick}
                      yDomain={['dataMin - 5', 'dataMax + 5']}
                    />
                    </>
                  )}

                  {/* 前月比チャート */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'mom', color: COLORS.mom, name: '前月比' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                    />
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="existing_home_sales" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
