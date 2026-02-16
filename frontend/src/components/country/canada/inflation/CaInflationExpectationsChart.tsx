/**
 * カナダインフレ期待チャートコンポーネント
 *
 * BOC消費者調査による消費者のインフレ期待（1年・2年・5年先）を表示
 *
 * データソース:
 * - Bank of Canada Valet API
 * - CES_C1_SHORT_TERM: 1年先インフレ期待
 * - CES_C1_MID_TERM: 2年先インフレ期待
 * - CES_C1_LONG_TERM: 5年先インフレ期待
 *
 * 発表スケジュール:
 * - 四半期ごと
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'
import type { CaInflationExpectationsData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
} from '../../usa/common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// =============================================================================
// 型定義
// =============================================================================

interface CaInflationExpectationsChartProps {
  data: CaInflationExpectationsData | null
}

// カラー設定
const COLORS = {
  exp_1y: '#DC143C',  // カナダカラー（クリムゾン）
  exp_2y: CHART_COLORS.purple,
  exp_5y: CHART_COLORS.positive,
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CaInflationExpectationsChart({ data }: CaInflationExpectationsChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>('default')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データを日付昇順にソート
  const sortedData = useSortedData(data?.data)

  // チャート用データに変換
  const chartData = useMemo(() => {
    return sortedData.map(item => ({
      date: item.date,
      exp_1y: item.exp_1y ?? null,
      exp_2y: item.exp_2y ?? null,
      exp_5y: item.exp_5y ?? null,
    }))
  }, [sortedData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: selectedPeriod,
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
    return <LoadingChart title="カナダインフレ期待" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="カナダインフレ期待" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 比較ボタンのURLを生成
  const getCompareUrl = () => {
    return '/compare?s=ca_inflation_exp_1y&s=ca_inflation_exp_2y&s=ca_inflation_exp_5y'
  }

  return (
    <div id="ca-inflation-expectations-chart">
      <ChartContainer
        title="カナダインフレ期待（消費者調査）"
        showPeriodSelector={false}
        dataSource="Bank of Canada"
        sourceUrl="https://www.bankofcanada.ca/publications/canadian-survey-of-consumer-expectations/"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="1年先インフレ期待"
          value={latestValues?.exp_1y}
          valueColor={COLORS.exp_1y}
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
                  {/* コントロールバー */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
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
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'exp_1y', color: COLORS.exp_1y, name: '1年先', hide: hiddenSeries.has('exp_1y') },
                      { dataKey: 'exp_2y', color: COLORS.exp_2y, name: '2年先', hide: hiddenSeries.has('exp_2y') },
                      { dataKey: 'exp_5y', color: COLORS.exp_5y, name: '5年先', hide: hiddenSeries.has('exp_5y') },
                    ]}
                    yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                    tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                    yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                    showZeroLine={false}
                    onLegendClick={handleLegendClick}
                  />
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="ca_inflation_expectations" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
