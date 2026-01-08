/**
 * NAHB住宅市場指数チャートコンポーネント
 *
 * NAHBから取得した住宅市場指数（HMI）を表示
 * データソース: NAHB / FMP
 *
 * タブ切り替え:
 * - 時系列: 現数値グラフのみ
 * - マーケットインパクト: 発表時の市場への影響分析
 */
import { useState } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { NAHBHMIData } from '../../../../hooks/useDashboardData'
import type { PeriodValue } from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../common/ChartComponents'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// =============================================================================
// 型定義
// =============================================================================

interface NAHBHMIChartProps {
  nahbHMIData: NAHBHMIData | null
}

// カラー設定
const COLORS = {
  value: '#8b5cf6',  // パープル（現数値）
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function NAHBHMIChart({ nahbHMIData }: NAHBHMIChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データを日付昇順にソート
  const chartData = useSortedData(nahbHMIData?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0

  // ローディング状態
  if (nahbHMIData === null) {
    return <LoadingChart title="NAHB住宅市場指数 (HMI)" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="NAHB住宅市場指数 (HMI)" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = nahbHMIData.latest

  return (
    <div id="nahb-hmi">
      <ChartContainer
        title="NAHB住宅市場指数"
        showPeriodSelector={false}
        dataSource="NAHB"
        sourceUrl="https://www.nahb.org/news-and-economics/housing-economics/indices/housing-market-index"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={latest?.value}
          valueColor={COLORS.value}
          date={latest?.date}
          nextRelease={nahbHMIData?.next_release}
          format="number"
          decimals={0}
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
                  {/* 期間セレクター */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く（NAHB住宅市場指数）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=nahb_hmi', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* チャート表示 */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: COLORS.value, name: 'HMI', hide: hiddenSeries.has('value') },
                    ]}
                    yAxisFormatter={(v) => `${v}`}
                    tooltipValueFormatter={(v) => `${Math.round(v)}`}
                    onLegendClick={handleLegendClick}
                    showZeroLine={false}
                    showFiftyLine={true}
                    yDomain={['dataMin - 5', 'dataMax + 5']}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="nahb_hmi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
