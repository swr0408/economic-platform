/**
 * 失業率内訳チャートコンポーネント
 *
 * FRED データを使用して失業者の内訳を表示
 * - レイオフ（Job Losers On Layoff）
 * - レイオフ以外の失業者（Other Job Losers）
 * - 自発的離職者（Job Leavers）
 * - 再参入者（Reentrants）
 * - 新規参入者（New Entrants）
 *
 * 共通コンポーネントを使用
 */
import { useState } from 'react'
import { Tabs } from 'antd'
import MarketImpactTab from '../../../indicator/MarketImpactTab'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { UnemploymentByReasonData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabelJP,
  createUnitFormatter,
  useHiddenSeries,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  StandardLineChart,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface UnemploymentByReasonChartProps {
  data: UnemploymentByReasonData | null
}

// カラー設定（サービスから取得したものを優先、フォールバック用）
const DEFAULT_COLORS = {
  layoff: '#ff4d4f',
  other_losers: '#fa8c16',
  leavers: '#52c41a',
  reentrants: '#1890ff',
  new_entrants: '#722ed1',
}

// 系列名（日本語）
const SERIES_NAMES = {
  layoff: 'レイオフ',
  other_losers: 'レイオフ以外',
  leavers: '自発的離職者',
  reentrants: '再参入者',
  new_entrants: '新規参入者',
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function UnemploymentByReasonChart({ data }: UnemploymentByReasonChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>(10)
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
    return <LoadingChart title="失業率内訳" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="失業率内訳" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release
  const seriesConfig = data.series_config || {}

  // 色を取得（サービス設定 > デフォルト）
  const getColor = (key: string): string => {
    return seriesConfig[key]?.color || DEFAULT_COLORS[key as keyof typeof DEFAULT_COLORS] || '#1890ff'
  }

  // 最新値の表示用アイテム
  const latestItems = latest ? [
    { label: SERIES_NAMES.layoff, value: latest.layoff, color: getColor('layoff'), format: 'number' as const, unit: 'k', decimals: 0 },
    { label: SERIES_NAMES.other_losers, value: latest.other_losers, color: getColor('other_losers'), format: 'number' as const, unit: 'k', decimals: 0 },
    { label: SERIES_NAMES.leavers, value: latest.leavers, color: getColor('leavers'), format: 'number' as const, unit: 'k', decimals: 0 },
    { label: SERIES_NAMES.reentrants, value: latest.reentrants, color: getColor('reentrants'), format: 'number' as const, unit: 'k', decimals: 0 },
    { label: SERIES_NAMES.new_entrants, value: latest.new_entrants, color: getColor('new_entrants'), format: 'number' as const, unit: 'k', decimals: 0 },
  ] : []

  return (
    <div id="unemployment-by-reason">
      <ChartContainer
        title="失業率内訳"
        showPeriodSelector={false}
        dataSource="FRED / BLS"
        sourceUrl="https://www.bls.gov/news.release/empsit.toc.htm"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={latestItems}
          date={latest?.date}
          nextRelease={nextRelease}
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
                  <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

                  {/* 折れ線グラフ */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      {
                        dataKey: 'layoff',
                        color: getColor('layoff'),
                        name: SERIES_NAMES.layoff,
                        hide: hiddenSeries.has('layoff'),
                      },
                      {
                        dataKey: 'other_losers',
                        color: getColor('other_losers'),
                        name: SERIES_NAMES.other_losers,
                        hide: hiddenSeries.has('other_losers'),
                      },
                      {
                        dataKey: 'leavers',
                        color: getColor('leavers'),
                        name: SERIES_NAMES.leavers,
                        hide: hiddenSeries.has('leavers'),
                      },
                      {
                        dataKey: 'reentrants',
                        color: getColor('reentrants'),
                        name: SERIES_NAMES.reentrants,
                        hide: hiddenSeries.has('reentrants'),
                      },
                      {
                        dataKey: 'new_entrants',
                        color: getColor('new_entrants'),
                        name: SERIES_NAMES.new_entrants,
                        hide: hiddenSeries.has('new_entrants'),
                      },
                    ]}
                    yAxisFormatter={(v) => `${(v / 1000).toFixed(0)}M`}
                    yDomain={['dataMin - 100', 'dataMax + 100']}
                    tooltipLabelFormatter={formatDateLabelJP}
                    tooltipFormatter={createUnitFormatter('k', 0)}
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
