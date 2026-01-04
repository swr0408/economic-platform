/**
 * JOLTS採用数 / 解雇数チャートコンポーネント
 *
 * FRED データを使用して表示
 * - JOLTS採用数（JTSHIL）- 千人
 * - JOLTS解雇数（JTSLDL）- 千人
 *
 * 共通コンポーネントを使用
 */
import { useState } from 'react'
import { Tabs } from 'antd'
import MarketImpactTab from '../../../indicator/MarketImpactTab'
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { JoltsHiresLayoffsData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabel,
  useHiddenSeries,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  ValueTooltip,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface HiresLayoffsChartProps {
  data: JoltsHiresLayoffsData | null
}

// カラー設定（サービスから取得したものを優先、フォールバック用）
const DEFAULT_COLORS = {
  hires: CHART_COLORS.primary,     // 青
  layoffs: CHART_COLORS.negative,  // 赤
}

// 系列名（日本語）
const SERIES_NAMES = {
  hires: 'JOLTS採用数',
  layoffs: 'JOLTS解雇数',
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function HiresLayoffsChart({ data }: HiresLayoffsChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { handleLegendClick, isHidden } = useHiddenSeries<'hires' | 'layoffs'>()

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
    return <LoadingChart title="JOLTS採用数 / 解雇数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="JOLTS採用数 / 解雇数" showPeriodSelector={false} showDataSource={false}>
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
    { label: SERIES_NAMES.hires, value: latest.hires, color: getColor('hires'), format: 'number' as const, unit: 'k', decimals: 0 },
    { label: SERIES_NAMES.layoffs, value: latest.layoffs, color: getColor('layoffs'), format: 'number' as const, unit: 'k', decimals: 0 },
  ] : []

  return (
    <div id="jolts-hires-layoffs">
      <ChartContainer
        title="JOLTS採用数 / 解雇数"
        showPeriodSelector={false}
        dataSource="FRED / BLS"
        sourceUrl="https://www.bls.gov/jlt/"
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

                  {/* チャート */}
                  <ResponsiveContainer width="100%" height={450}>
                    <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                      <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                      <XAxis
                        dataKey="date"
                        tickFormatter={formatDateLabel}
                        tick={AXIS_STYLE.tick}
                        interval={AXIS_STYLE.interval}
                      />
                      <YAxis
                        tick={AXIS_STYLE.tick}
                        tickFormatter={(v) => `${v.toLocaleString()}`}
                        label={{
                          angle: -90,
                          position: 'insideLeft',
                          dy: 20,
                          style: { fontSize: 11, fill: '#666' }
                        }}
                      />
                      <Tooltip content={<ValueTooltip unit="k" />} />
                      <Legend
                        onClick={(e) => handleLegendClick(e.dataKey as string)}
                        wrapperStyle={{ cursor: 'pointer' }}
                      />

                      {/* JOLTS採用数 */}
                      <Line
                        type="monotone"
                        dataKey="hires"
                        stroke={getColor('hires')}
                        strokeWidth={2}
                        dot={false}
                        name={SERIES_NAMES.hires}
                        hide={isHidden('hires')}
                        isAnimationActive={false}
                        connectNulls={true}
                      />

                      {/* JOLTS解雇数 */}
                      <Line
                        type="monotone"
                        dataKey="layoffs"
                        stroke={getColor('layoffs')}
                        strokeWidth={2}
                        dot={false}
                        name={SERIES_NAMES.layoffs}
                        hide={isHidden('layoffs')}
                        isAnimationActive={false}
                        connectNulls={true}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="jolts_openings" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
