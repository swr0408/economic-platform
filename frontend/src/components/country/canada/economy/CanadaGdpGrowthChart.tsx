/**
 * カナダGDP成長率チャートコンポーネント
 *
 * 四半期GDP成長率（前期比・前期比年率・前年比）の推移を表示
 *
 * データソース:
 * - Statistics Canada Table 36-10-0104-01
 *
 * 発表スケジュール:
 * - 四半期ごと（対象期間終了の約2ヶ月後）
 * - 発表時刻: 08:30 ET
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
  useQuarterlyTableData,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  ViewModeButtonGroup,
  StandardLineChart,
  MOM_LEGEND_DEFAULT,
} from '../../usa/common/ChartComponents'
import { QuarterlyTable } from '../../usa/common/QuarterlyTable'
import { CHART_COLORS } from '../../usa/common/chartConstants'

// 型定義
import type { CaGdpGrowthData } from '../../../../hooks/useDashboardData'

interface CanadaGdpGrowthChartProps {
  data: CaGdpGrowthData | null
}

type DataKind = 'qoq_simple' | 'qoq' | 'yoy'
type DisplayMode = 'chart' | 'heatmap'

// 指標種別設定
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'qoq_simple', label: '前期比' },
  { mode: 'qoq', label: '前期比年率' },
  { mode: 'yoy', label: '前年比' },
]

// 表示モード設定
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

export default function CanadaGdpGrowthChart({ data }: CanadaGdpGrowthChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('qoq_simple')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    qoq_simple: 'default' as PeriodType,
    qoq: 'default' as PeriodType,
    yoy: 'default' as PeriodType,
  })

  // propsのデータをチャート用に変換
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        qoq_simple: item.qoq_simple,
        qoq: item.qoq,
        yoy: item.yoy,
      }))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2000,
  })

  // テーブル用データ（前期比）
  const qoqTableData = useQuarterlyTableData(
    chartData,
    (item) => item.qoq_simple,
    10
  )

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="GDP成長率" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="GDP成長率" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 表示ラベルを取得
  const getDataKindLabel = (kind: DataKind) => {
    switch (kind) {
      case 'qoq_simple': return '前期比'
      case 'qoq': return '前期比年率'
      case 'yoy': return '前年比'
    }
  }

  // 最新値を取得（DataKindに応じて）
  const getLatestValue = () => {
    if (!latestValue) return undefined
    switch (dataKind) {
      case 'qoq_simple': return latestValue.qoq_simple
      case 'qoq': return latestValue.qoq
      case 'yoy': return latestValue.yoy
    }
  }

  // グラフ用のデータキーを取得
  const getDataKey = () => {
    switch (dataKind) {
      case 'qoq_simple': return 'qoq_simple'
      case 'qoq': return 'qoq'
      case 'yoy': return 'yoy'
    }
  }

  // 比較ページ用のキーを取得
  const getCompareKey = () => {
    switch (dataKind) {
      case 'qoq_simple': return 'qoq_simple'
      case 'qoq': return 'qoq'
      case 'yoy': return 'yoy'
    }
  }

  return (
    <div id="ca-gdp-growth-chart">
      <ChartContainer
        title="GDP成長率"
        showPeriodSelector={false}
        dataSource="Statistics Canada"
        sourceUrl="https://www.statcan.gc.ca/en/subjects-start/economic_accounts"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={getDataKindLabel(dataKind)}
          value={getLatestValue()}
          valueColor={CHART_COLORS.primary}
          date={latestValue?.date}
          nextRelease={data.next_release ? {
            date: data.next_release.date,
            label: data.next_release.time_jst ? `${data.next_release.time_jst} JST` : undefined
          } : null}
          format="percent"
          decimals={1}
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
                    <ViewModeButtonGroup
                      options={DATA_KIND_OPTIONS}
                      currentMode={dataKind}
                      onChange={setDataKind}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(`/compare?s=ca_gdp_growth_${getCompareKey()}`, '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
                  {dataKind === 'qoq_simple' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 前期比ヒートマップ */}
                  {dataKind === 'qoq_simple' && displayMode === 'heatmap' && (
                    <QuarterlyTable
                      data={qoqTableData}
                      decimals={1}
                      showLegend={true}
                      legendItems={MOM_LEGEND_DEFAULT}
                      helperText="※ 直近10年間の前期比データ（単位: %）"
                    />
                  )}

                  {/* グラフ表示 */}
                  {!(dataKind === 'qoq_simple' && displayMode === 'heatmap') && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          {
                            dataKey: getDataKey(),
                            color: CHART_COLORS.primary,
                            name: `GDP（${getDataKindLabel(dataKind)}）`,
                          },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
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
              children: <MarketImpactTab indicatorId="ca_gdp_growth" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
