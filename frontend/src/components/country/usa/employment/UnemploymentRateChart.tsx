/**
 * 失業率チャートコンポーネント
 *
 * FRED UNRATE（失業率）& U6RATE（広義の失業率）を表示
 * 共通モジュールを使用
 */
import { useState } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import MarketImpactTab from '../../../indicator/MarketImpactTab'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { UnemploymentRateData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { CHART_COLORS } from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabelJP,
  createPercentFormatter,
  useHiddenSeries,
} from '../common/useChartData'
import {
  SimpleLatestValueBox,
  NoDataMessage,
  StandardLineChart,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface UnemploymentRateChartProps {
  data: UnemploymentRateData | null
}

// カラー設定
const COLORS = {
  unrate: CHART_COLORS.primary,
  u6rate: CHART_COLORS.orange,
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function UnemploymentRateChart({ data }: UnemploymentRateChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データのソート
  const sortedData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="失業率 / 広義の失業率" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="失業率 / 広義の失業率" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release

  return (
    <div id="unemployment">
      <ChartContainer
        title="失業率 / 広義の失業率"
        showPeriodSelector={false}
        dataSource="FRED / BLS"
        sourceUrl="https://www.bls.gov/news.release/empsit.toc.htm"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="失業率 (U-3)"
          value={latest?.unrate}
          subLabel="広義の失業率 (U-6)"
          subValue={latest?.u6rate}
          valueColor={COLORS.unrate}
          subValueColor={COLORS.u6rate}
          date={latest?.date}
          nextRelease={nextRelease}
          format="number"
          unit="%"
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
                  {/* 期間セレクター */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=unemployment_rate', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 折れ線グラフ */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      {
                        dataKey: 'unrate',
                        color: COLORS.unrate,
                        name: '失業率 (U-3)',
                        hide: hiddenSeries.has('unrate'),
                      },
                      {
                        dataKey: 'u6rate',
                        color: COLORS.u6rate,
                        name: '広義の失業率 (U-6)',
                        hide: hiddenSeries.has('u6rate'),
                      },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    yDomain={['dataMin - 1', 'dataMax + 1']}
                    tooltipLabelFormatter={formatDateLabelJP}
                    tooltipFormatter={createPercentFormatter(1, false)}
                    showZeroLine={false}
                    onLegendClick={handleLegendClick}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="unemployment_rate" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
