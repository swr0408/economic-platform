/**
 * ミシガン大学消費者信頼感指数チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { MichiganConsumerSentimentData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { CHART_COLORS } from '../common/chartConstants'
import {
  usePeriodFiltering,
  formatDateLabelJP,
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

interface MichiganConsumerSentimentChartProps {
  data: MichiganConsumerSentimentData | null
}

// マージされたデータの型
interface MergedChartItem {
  date: string
  value: number | null      // ICS_ALL（総合指数）
  current: number | null    // ICC（現況指数）
  expected: number | null   // ICE（期待指数）
}

// カラー設定
const COLORS = {
  value: CHART_COLORS.purple,    // 総合（ICS）
  current: CHART_COLORS.primary, // 現況（ICC）
  expected: CHART_COLORS.positive, // 期待（ICE）
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function MichiganConsumerSentimentChart({ data }: MichiganConsumerSentimentChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // 指数データと構成要素データをマージして日付昇順にソート
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    const dateMap = new Map<string, MergedChartItem>()

    // 指数データを追加
    for (const item of data.data) {
      dateMap.set(item.date, {
        date: item.date,
        value: item.value,
        current: null,
        expected: null,
      })
    }

    // 構成要素データをマージ
    if (data.components && data.components.length > 0) {
      for (const comp of data.components) {
        const existing = dateMap.get(comp.date)
        if (existing) {
          existing.current = comp.current
          existing.expected = comp.expected
        } else {
          dateMap.set(comp.date, {
            date: comp.date,
            value: null,
            current: comp.current,
            expected: comp.expected,
          })
        }
      }
    }

    return Array.from(dateMap.values())
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="ミシガン大学消費者信頼感指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="ミシガン大学消費者信頼感指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const latestComponents = data.latest_components
  const nextRelease = data.next_release

  return (
    <div id="michigan-consumer-sentiment">
      <ChartContainer
        title="ミシガン大学消費者信頼感指数"
        showPeriodSelector={false}
        dataSource="University of Michigan"
        sourceUrl="https://www.sca.isr.umich.edu/"
      >
        {/* 最新値・次回発表表示 */}
        <LatestValueBox
          items={[
            { label: '総合', value: latest?.value, color: COLORS.value, format: 'number', decimals: 1 },
            { label: '現況', value: latestComponents?.current, color: COLORS.current, format: 'number', decimals: 1 },
            { label: '期待', value: latestComponents?.expected, color: COLORS.expected, format: 'number', decimals: 1 },
          ]}
          date={latest?.date}
          nextRelease={nextRelease}
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=michigan_consumer_sentiment', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: COLORS.value, name: 'ミシガン大学消費者信頼感指数', hide: hiddenSeries.has('value') },
                      { dataKey: 'current', color: COLORS.current, name: '現況', hide: hiddenSeries.has('current') },
                      { dataKey: 'expected', color: COLORS.expected, name: '見通し', hide: hiddenSeries.has('expected') },
                    ]}
                    yDomain={['dataMin - 5', 'dataMax + 5']}
                    tooltipLabelFormatter={formatDateLabelJP}
                    tooltipFormatter={createNumberFormatter(1)}
                    onLegendClick={handleLegendClick}
                    showZeroLine={false}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="michigan_consumer_sentiment" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
