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
type IPPIViewMode = 'yoy' | 'mom_chart' | 'mom_table'

// IPPIビューモードオプション
const IPPI_VIEW_MODE_OPTIONS: { mode: IPPIViewMode; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom_chart', label: '前月比' },
  { mode: 'mom_table', label: '前月比（テーブル）' },
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
  const [viewMode, setViewMode] = useState<IPPIViewMode>('yoy')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom_chart: 3,
    mom_table: 'default',
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
      <ChartContainer title="カナダIPPI" showPeriodSelector={false} showDataSource={false}>
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
        dataSource="Statistics Canada"
        sourceUrl="https://www.statcan.gc.ca/en/subjects-start/prices_and_price_indexes/producer_price_indexes"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={viewMode === 'yoy' ? 'IPPI（前年比）' : 'IPPI（前月比）'}
          value={viewMode === 'yoy' ? latestValues?.yoy : latestValues?.mom}
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
                  {/* ビューモード切替 */}
                  <ViewModeButtonGroup
                    currentMode={viewMode}
                    options={IPPI_VIEW_MODE_OPTIONS}
                    onChange={(mode) => setViewMode(mode as IPPIViewMode)}
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
                        { dataKey: 'yoy', color: COLORS.yoy, name: 'IPPI（前年比）' },
                      ]}
                      yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                      yDomain={['dataMin - 1', 'dataMax + 1']}
                      showZeroLine={true}
                    />
                  )}

                  {viewMode === 'mom_chart' && (
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

                  {viewMode === 'mom_table' && (
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
