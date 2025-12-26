/**
 * NER Pulse（週次雇用変動）チャートコンポーネント
 *
 * ADP Media Centerから取得した週次雇用変動データを表示
 *
 * 表示モード:
 * - 週次増減グラフ（棒グラフ）
 *
 * 共通コンポーネントを使用
 */
import { useMemo } from 'react'
import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import type { NERPulseData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  TOOLTIP_STYLE,
} from '../common/chartConstants'
import {
  LatestValueBox,
  NoDataMessage,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface NERPulseChartProps {
  data: NERPulseData | null
}

// カラー設定
const CHART_COLOR = CHART_COLORS.primary

// =============================================================================
// ヘルパー関数
// =============================================================================

/** 日付をフォーマット (YYYY-MM-DD -> MM/DD) */
function formatWeekEnding(dateStr: string): string {
  try {
    const date = new Date(dateStr)
    const month = date.getMonth() + 1
    const day = date.getDate()
    return `${month}/${day}`
  } catch {
    return dateStr
  }
}

/** 日付をフォーマット (YYYY-MM-DD -> YYYY年MM月DD日週) */
function formatWeekEndingJP(dateStr: string): string {
  try {
    const date = new Date(dateStr)
    const year = date.getFullYear()
    const month = date.getMonth() + 1
    const day = date.getDate()
    return `${year}年${month}月${day}日週`
  } catch {
    return dateStr
  }
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

function ChangeTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, padding: '8px 12px' }}>
        {formatWeekEndingJP(label || '')}
      </div>
      {payload.map((item, index) => {
        const value = item.value
        const sign = value >= 0 ? '+' : ''
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
            <span style={{ fontWeight: 500, color: value >= 0 ? '#52c41a' : '#ff4d4f' }}>
              {sign}{value.toLocaleString()}
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

export default function NERPulseChart({ data }: NERPulseChartProps) {
  // データを日付順にソート（古い順）
  const sortedData = useMemo(() => {
    if (!data?.data) return []
    return [...data.data].sort((a, b) =>
      new Date(a.week_ending).getTime() - new Date(b.week_ending).getTime()
    )
  }, [data?.data])

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="NER Pulse（週次雇用変動）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="NER Pulse（週次雇用変動）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latest) return []

    return [
      {
        label: 'NER Pulse（週次増減）',
        value: `${latest.change >= 0 ? '+' : ''}${latest.change.toLocaleString()}`,
        color: latest.change >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative,
      },
    ]
  }

  return (
    <div id="ner-pulse">
      <ChartContainer
        title="ADP雇用者数（NER Pulse）"
        showPeriodSelector={false}
        dataSource="ADP Media Center"
        sourceUrl="https://mediacenter.adp.com/labor-market-data"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latest?.week_ending}
          nextRelease={nextRelease}
        />

        {/* 週次増減グラフ */}
        <ResponsiveContainer width="100%" height={350}>
          <ComposedChart data={sortedData} margin={CHART_MARGIN}>
            <CartesianGrid {...CARTESIAN_GRID_PROPS} />
            <XAxis
              dataKey="week_ending"
              tickFormatter={formatWeekEnding}
              tick={AXIS_STYLE.tick}
              interval={0}
            />
            <YAxis
              tick={AXIS_STYLE.tick}
              tickFormatter={(v) => `${v >= 0 ? '+' : ''}${(v / 1000).toFixed(0)}k`}
              label={{
                value: '増減',
                angle: -90,
                position: 'insideLeft',
                dy: 20,
                style: { fontSize: 11, fill: '#666' }
              }}
            />
            <Tooltip content={<ChangeTooltip />} />
            <Legend />
            <ReferenceLine y={0} stroke="#000" strokeWidth={1} />

            <Bar
              dataKey="change"
              fill={CHART_COLOR}
              name="週次増減"
            />
          </ComposedChart>
        </ResponsiveContainer>

      </ChartContainer>
    </div>
  )
}
