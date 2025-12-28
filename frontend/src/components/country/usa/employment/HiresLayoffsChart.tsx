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
  TOOLTIP_STYLE,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabel,
  formatDateLabelJP,
  useHiddenSeries,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
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
// カスタムツールチップ
// =============================================================================

interface TooltipPayload {
  name: string
  value: number
  color: string
  dataKey: string
}

interface CustomTooltipProps {
  active?: boolean
  payload?: TooltipPayload[]
  label?: string
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, padding: '8px 12px' }}>
        {formatDateLabelJP(label || '')}
      </div>
      {payload.map((item, index) => {
        // 千人単位
        const displayValue = item.value !== null && item.value !== undefined
          ? `${item.value.toLocaleString()}k`
          : '-'
        return (
          <div
            key={index}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 4,
              fontSize: 13,
              padding: '4px 12px',
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span
                style={{
                  display: 'inline-block',
                  width: 10,
                  height: 10,
                  borderRadius: 2,
                  backgroundColor: item.color,
                  marginRight: 6,
                }}
              />
              {item.name}
            </span>
            <span style={{ fontWeight: 500, color: item.color }}>
              {displayValue}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function HiresLayoffsChart({ data }: HiresLayoffsChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')
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
            <Tooltip content={<CustomTooltip />} />
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
      </ChartContainer>
    </div>
  )
}
