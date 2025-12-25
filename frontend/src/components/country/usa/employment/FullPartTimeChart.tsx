/**
 * フルタイム/パートタイム雇用者数チャートコンポーネント
 *
 * FRED データを使用して雇用形態別雇用者数を表示
 * - フルタイム雇用者数（Employed Full Time: LNS12500000）- 左Y軸
 * - パートタイム雇用者数（Employed Part Time: LNS12600000）- 右Y軸
 *
 * フルタイムとパートタイムはスケールが大きく異なるため
 * 左右のY軸で表示
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
import type { FullPartTimeEmploymentData } from '../../../../hooks/useDashboardData'

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

interface FullPartTimeChartProps {
  data: FullPartTimeEmploymentData | null
}

// カラー設定（サービスから取得したものを優先、フォールバック用）
const DEFAULT_COLORS = {
  fulltime: CHART_COLORS.primary,     // 青（左軸）
  parttime: CHART_COLORS.orange,      // オレンジ（右軸）
}

// 系列名（日本語）
const SERIES_NAMES = {
  fulltime: 'フルタイム',
  parttime: 'パートタイム',
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
        // 千人単位でそのまま表示（FREDは千人単位で提供）
        const valueInThousands = item.value.toLocaleString()
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
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16 }}>
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
            <span style={{ fontWeight: 500 }}>
              {valueInThousands}k
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

export default function FullPartTimeChart({ data }: FullPartTimeChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')
  const { hiddenSeries, handleLegendClick, isHidden } = useHiddenSeries<'fulltime' | 'parttime'>()

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
    return <LoadingChart title="フルタイム / パートタイム雇用者数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="フルタイム / パートタイム雇用者数" showPeriodSelector={false} showDataSource={false}>
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
    { label: SERIES_NAMES.fulltime, value: latest.fulltime, color: getColor('fulltime'), format: 'number' as const, unit: 'k', decimals: 0 },
    { label: SERIES_NAMES.parttime, value: latest.parttime, color: getColor('parttime'), format: 'number' as const, unit: 'k', decimals: 0 },
  ] : []

  return (
    <div id="fullpart-time">
      <ChartContainer
        title="フルタイム / パートタイム雇用者数"
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

        {/* 期間セレクター */}
        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

        {/* 左右Y軸の折れ線グラフ */}
        <ResponsiveContainer width="100%" height={450}>
          <ComposedChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid {...CARTESIAN_GRID_PROPS} />
            <XAxis
              dataKey="date"
              tickFormatter={formatDateLabel}
              tick={AXIS_STYLE.tick}
              interval={AXIS_STYLE.interval}
            />
            {/* 左Y軸: フルタイム（千人単位でそのまま表示） */}
            <YAxis
              yAxisId="left"
              domain={['dataMin - 1000', 'dataMax + 1000']}
              tick={AXIS_STYLE.tick}
              tickFormatter={(v) => `${v.toLocaleString()}`}
              label={{
                value: 'フルタイム（k）',
                angle: -90,
                position: 'insideLeft',
                style: { fontSize: 11, fill: getColor('fulltime') }
              }}
            />
            {/* 右Y軸: パートタイム（千人単位でそのまま表示） */}
            <YAxis
              yAxisId="right"
              orientation="right"
              domain={['dataMin - 500', 'dataMax + 500']}
              tick={AXIS_STYLE.tick}
              tickFormatter={(v) => `${v.toLocaleString()}`}
              label={{
                value: 'パートタイム（k）',
                angle: 90,
                position: 'insideRight',
                style: { fontSize: 11, fill: getColor('parttime') }
              }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              onClick={(e) => handleLegendClick(e.dataKey as string)}
              wrapperStyle={{ cursor: 'pointer' }}
            />

            {/* フルタイム（左軸） */}
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="fulltime"
              stroke={getColor('fulltime')}
              strokeWidth={2}
              dot={false}
              name={SERIES_NAMES.fulltime}
              hide={isHidden('fulltime')}
              isAnimationActive={false}
              connectNulls={true}
            />

            {/* パートタイム（右軸） */}
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="parttime"
              stroke={getColor('parttime')}
              strokeWidth={2}
              dot={false}
              name={SERIES_NAMES.parttime}
              hide={isHidden('parttime')}
              isAnimationActive={false}
              connectNulls={true}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
