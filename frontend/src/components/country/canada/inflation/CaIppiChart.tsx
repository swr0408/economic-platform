/**
 * カナダ工業製品価格指数（IPPI）チャートコンポーネント
 *
 * Industrial Product Price Index - 製造業の出荷価格の変動を測定
 *
 * データソース:
 * - Statistics Canada Table 18-10-0265-01
 *
 * 発表スケジュール:
 * - 毎月発表
 * - 発表時刻: 08:30 ET
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { CaIppiData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
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

interface CaIppiChartProps {
  data: CaIppiData | null
}

// IPPI表示モード
type DataKind = 'yoy' | 'mom'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
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
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CaIppiChart({ data }: CaIppiChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 10,
    mom: 3,
  })

  // データを日付昇順にソート
  const sortedData = useSortedData(data?.data)

  // チャート用データに変換
  const chartData = useMemo(() => {
    return sortedData.map(item => ({
      date: item.date,
      yoy: item.yoy ?? null,
      mom: item.mom ?? null,
      index: item.index ?? null,
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
    return <LoadingChart title="カナダIPPI" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="カナダIPPI" showPeriodSelector={false} showDataSource={false} handbookId="ippi">
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
      return '/compare?s=ca_ippi_yoy'
    } else {
      return '/compare?s=ca_ippi_mom'
    }
  }

  return (
    <div id="ca-ippi-chart">
      <ChartContainer
        title="カナダIPPI（工業製品価格指数）"
        showPeriodSelector={false}
        handbookId="ippi"
        dataSource="Statistics Canada"
        sourceUrl="https://www.statcan.gc.ca/en/subjects-start/prices_and_price_indexes/producer_price_indexes"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={dataKind === 'yoy' ? 'IPPI（前年比）' : 'IPPI（前月比）'}
          value={dataKind === 'yoy' ? latestValues?.yoy : latestValues?.mom}
          valueColor={COLORS.yoy}
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
                        { dataKey: 'yoy', color: COLORS.yoy, name: 'IPPI（前年比）' },
                      ]}
                      yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                      yDomain={['dataMin - 1', 'dataMax + 1']}
                      showZeroLine={true}
                    />
                  )}

                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'mom', color: COLORS.mom, name: 'IPPI（前月比）' },
                      ]}
                      yAxisFormatter={(v) => `${v.toFixed(2)}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                      showZeroLine={true}
                    />
                  )}

                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTable data={momTableData} />
                  )}
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="ca_ippi" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
