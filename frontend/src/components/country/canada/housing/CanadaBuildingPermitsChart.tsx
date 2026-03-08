/**
 * カナダ建築許可チャートコンポーネント
 *
 * 建築許可（原数値・前月比・前年比）の推移を表示
 *
 * データソース:
 * - Statistics Canada Table 34-10-0292-01
 *
 * 発表スケジュール:
 * - 月次
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// 共通モジュールのインポート
import {
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMultiValueMonthlyTableData,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  ViewModeButtonGroup,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTableWithDataTypes } from '../../usa/common/MonthlyTable'
import { CHART_COLORS } from '../../usa/common/chartConstants'

// 型定義
import type { CaBuildingPermitsData } from '../../../../hooks/useDashboardData'

interface CanadaBuildingPermitsChartProps {
  data: CaBuildingPermitsData | null
}

type DataKind = 'value' | 'yoy' | 'mom'
type DisplayMode = 'chart' | 'heatmap'

// 指標種別設定
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'mom', label: '前月比' },
  { mode: 'yoy', label: '前年比' },
  { mode: 'value', label: '原数値' },
]

// 表示モード設定
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// カラー設定
const COLORS = {
  value: CHART_COLORS.positive,
  yoy: CHART_COLORS.primary,
  mom: CHART_COLORS.purple,
}

export default function CanadaBuildingPermitsChart({ data }: CanadaBuildingPermitsChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('mom')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    value: 'default' as PeriodType,
    yoy: 'default' as PeriodType,
    mom: 3 as PeriodType,
  })

  // propsのデータをチャート用に変換
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        value: item.value,
        yoy: item.yoy,
        mom: item.mom,
      }))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2000,
  })

  // テーブル用データ（前月比のみ）
  const momTableData = useMultiValueMonthlyTableData(
    chartData,
    {
      mom: (item) => item.mom,
    },
    10
  )

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="建築許可" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="建築許可" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値の表示内容
  const getLatestItems = () => {
    if (dataKind === 'value') {
      return [
        {
          label: '建築許可',
          value: latestValue?.value,
          color: COLORS.value,
          format: 'number' as const,
          suffix: '百万CAD',
        },
      ]
    } else if (dataKind === 'yoy') {
      return [
        {
          label: '前年比',
          value: latestValue?.yoy,
          color: COLORS.yoy,
          format: 'percent' as const,
        },
      ]
    } else {
      return [
        {
          label: '前月比',
          value: latestValue?.mom,
          color: COLORS.mom,
          format: 'percent' as const,
        },
      ]
    }
  }

  return (
    <div id="ca-building-permits-chart">
      <ChartContainer
        title="建築許可"
        showPeriodSelector={false}
        dataSource="Statistics Canada"
        sourceUrl="https://www.statcan.gc.ca/en/subjects-start/construction"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latestValue?.date}
          nextRelease={data.next_release ?? null}
        />

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
                        onClick={() => window.open('/compare?s=canada_building_permits', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
                  {dataKind === 'mom' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 原数値グラフ（線グラフ） */}
                  {dataKind === 'value' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'value', color: COLORS.value, name: '建築許可（百万CAD）' },
                        ]}
                        yAxisFormatter={(v) => `${(v / 1000).toFixed(1)}B`}
                        yDomain={['dataMin - 500', 'dataMax + 500']}
                        tooltipValueFormatter={(v) => `${v.toLocaleString()} 百万CAD`}
                      />
                    </>
                  )}

                  {/* 前年比グラフ（線グラフ） */}
                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'yoy', color: COLORS.yoy, name: '建築許可（前年比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 5', 'dataMax + 5']}
                        showZeroLine={true}
                      />
                    </>
                  )}

                  {/* 前月比ヒートマップ */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTableWithDataTypes
                      data={momTableData}
                      dataTypes={[{ type: 'mom', label: '前月比' }]}
                      selectedType="mom"
                      onTypeChange={() => {}}
                    />
                  )}

                  {/* 前月比グラフ（棒グラフ） */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          {
                            dataKey: 'mom',
                            color: COLORS.mom,
                            name: '建築許可（前月比）',
                          },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 5', 'dataMax + 5']}
                      />
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="canada_building_permits" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
