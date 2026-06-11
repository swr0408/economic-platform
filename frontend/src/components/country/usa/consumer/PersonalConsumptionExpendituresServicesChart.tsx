/**
 * 個人消費支出：サービス（Personal Consumption Expenditures: Services）チャート
 *
 * FRED PCES シリーズから取得したサービス支出を表示
 * - 前年比: YoY変化率（%、折れ線）
 * - 前月比: MoM変化率（%、棒グラフ + 月次ヒートマップ）
 *
 * データソース: FRED https://fred.stlouisfed.org/series/PCES
 */
import { useState } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PersonalConsumptionExpendituresServicesData } from '../../../../hooks/useDashboardData'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// 共通モジュールのインポート
import { CHART_COLORS } from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMonthlyTableData,
  formatDateLabelJP,
} from '../common/useChartData'
import {
  ViewModeButtonGroup,
  SimpleLatestValueBox,
  NoDataMessage,
  StandardLineChart,
  StandardBarChart,
} from '../common/ChartComponents'
import { MonthlyTable } from '../common/MonthlyTable'

// =============================================================================
// 型定義
// =============================================================================

interface PersonalConsumptionExpendituresServicesChartProps {
  data: PersonalConsumptionExpendituresServicesData | null
}

// 指標種別
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

// カラー設定
const COLORS = {
  yoy: CHART_COLORS.positive,
  mom: CHART_COLORS.orange,
}

const TITLE = '個人消費支出：サービス'

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function PersonalConsumptionExpendituresServicesChart({
  data,
}: PersonalConsumptionExpendituresServicesChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // 指標種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 10,
    mom: 3,
  })

  // データを日付昇順にソート
  const chartData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // 月別テーブルデータ（前月比）
  const momTableData = useMonthlyTableData(chartData, (item) => item.mom, 10)

  const hasData = chartData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title={TITLE} />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title={TITLE} showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="personal-consumption-services">
      <ChartContainer
        title={TITLE}
        showPeriodSelector={false}
        dataSource="FRED / BEA"
        sourceUrl="https://fred.stlouisfed.org/series/PCES"
        handbookId="personal-consumption-services"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="前年比"
          value={latest?.yoy}
          valueColor={COLORS.yoy}
          subLabel="前月比"
          subValue={latest?.mom}
          subValueColor={COLORS.mom}
          date={latest?.date}
          nextRelease={data.next_release}
          format="percent"
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
                        onClick={() => window.open('/compare?s=personal_consumption_expenditures_services', '_blank')}
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

                  {/* 前年比グラフ */}
                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'yoy', color: COLORS.yoy, name: '前年比' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 2', 'dataMax + 2']}
                        tooltipLabelFormatter={formatDateLabelJP}
                        showLegend={false}
                      />
                    </>
                  )}

                  {/* 前月比ヒートマップ */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTable data={momTableData} thresholdType="default" showLegend={true} />
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
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                        tooltipLabelFormatter={formatDateLabelJP}
                      />
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="personal_income" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
