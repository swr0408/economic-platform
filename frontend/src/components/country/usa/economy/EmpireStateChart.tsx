/**
 * NY連銀製造業景気指数チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { EmpireStateData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  usePeriodFiltering,
  formatDateLabel,
  useHiddenSeries,
  createNumberFormatter,
  type PeriodType,
} from '../common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../common/ChartComponents'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// =============================================================================
// 型定義
// =============================================================================

interface EmpireStateChartProps {
  data: EmpireStateData | null
}

// シリーズ設定
const SERIES_CONFIG = {
  current: {
    name: '現況指数',
    color: '#1890ff',
    strokeWidth: 2,
  },
  future: {
    name: '期待指数',
    color: '#fa541c',
    strokeWidth: 2,
  },
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function EmpireStateChart({ data }: EmpireStateChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<string>(['future'])

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        current: item.current,
        future: item.future,
      }))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="NY連銀製造業景気指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="NY連銀製造業景気指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestData = data.latest

  return (
    <div id="empire-state-chart">
      <ChartContainer
        title="NY連銀製造業景気指数"
        showPeriodSelector={false}
        dataSource="Federal Reserve Bank of New York / FRED"
        sourceUrl="https://www.newyorkfed.org/survey/empire/empiresurvey_overview"
      >
        {/* 最新値表示 */}
        {latestData && (
          <LatestValueBox
            items={[
              { label: '現況指数', value: latestData.current, format: 'number', decimals: 1, color: SERIES_CONFIG.current.color },
              { label: '期待指数', value: latestData.future, format: 'number', decimals: 1, color: SERIES_CONFIG.future.color },
            ]}
            date={latestData.date}
            nextRelease={data.next_release}
          />
        )}

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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=empire_state', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'current', color: SERIES_CONFIG.current.color, name: SERIES_CONFIG.current.name, hide: hiddenSeries.has('current') },
                      { dataKey: 'future', color: SERIES_CONFIG.future.color, name: SERIES_CONFIG.future.name, hide: hiddenSeries.has('future') },
                    ]}
                    yDomain={['dataMin - 5', 'dataMax + 5']}
                    yAxisFormatter={(v) => v.toFixed(0)}
                    tooltipLabelFormatter={formatDateLabel}
                    tooltipFormatter={createNumberFormatter(1)}
                    onLegendClick={handleLegendClick}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="empire_state" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
