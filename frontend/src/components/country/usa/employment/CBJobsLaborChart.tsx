/**
 * CB雇用機会業況判断チャートコンポーネント
 *
 * Conference Board消費者信頼感調査から
 * - Differential（差分）を上下反転して表示
 *
 * 差分 = Jobs Plentiful - Jobs Hard to Get
 * - 正の値: 労働市場が強い（チャートでは下に表示）
 * - 負の値: 労働市場が弱い（チャートでは上に表示）
 *
 * Y軸反転により、失業率と同じ方向性（上が悪化、下が改善）で表示
 *
 * 共通モジュールを使用
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip as AntTooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
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
  ReferenceLine,
} from 'recharts'

import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { CBJobsLaborData, UnemploymentRateData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  TOOLTIP_STYLE,
  LATEST_VALUE_BOX_STYLE,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabel,
  formatDateLabelJP,
  useHiddenSeries,
  type PeriodType,
} from '../common/useChartData'
import {
  NoDataMessage,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface CBJobsLaborChartProps {
  data: CBJobsLaborData | null
  unemploymentData?: UnemploymentRateData | null  // オプショナル：失業率データ
}

// カラー設定
const COLORS = {
  plentiful: CHART_COLORS.positive,    // 緑（豊富）
  hard: CHART_COLORS.negative,         // 赤（困難）
  differential: CHART_COLORS.primary,  // 青（差分）
  unemployment: CHART_COLORS.orange,    // オレンジ（失業率）
} as const

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

  const nameMap: Record<string, string> = {
    invertedDiff: '差分 (反転)',
    differential: '差分',
    unemployment: '失業率',
  }

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, padding: '8px 12px' }}>
        {formatDateLabelJP(label || '')}
      </div>
      {payload.map((item, index) => {
        // 反転した差分は元の値を表示
        const displayValue = item.dataKey === 'invertedDiff' ? -item.value : item.value
        const displayName = item.dataKey === 'invertedDiff' ? 'CB雇用機会業況判断' : (nameMap[item.dataKey] || item.name)

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
              {displayName}
            </span>
            <span style={{
              fontWeight: 500,
              color: item.color
            }}>
              {item.dataKey === 'invertedDiff'
                ? `${displayValue >= 0 ? '+' : ''}${displayValue.toFixed(1)}`
                : displayValue.toFixed(1)}%
            </span>
          </div>
        )
      })}
    </div>
  )
}

// =============================================================================
// 最新値表示コンポーネント
// =============================================================================

interface LatestValueDisplayProps {
  latest: CBJobsLaborData['latest']
  nextRelease: CBJobsLaborData['next_release']
  latestUnemployment?: number | null
}

function LatestValueDisplay({ latest, nextRelease, latestUnemployment }: LatestValueDisplayProps) {
  const diffColor = latest?.differential && latest.differential >= 0
    ? CHART_COLORS.positive
    : CHART_COLORS.negative

  return (
    <div style={LATEST_VALUE_BOX_STYLE}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap' }}>
        {/* 差分（メイン表示） */}
        <div>
          <span style={{ fontSize: 12, color: '#666' }}>CB雇用機会業況判断: </span>
          <span style={{ fontSize: 24, fontWeight: 'bold', color: diffColor }}>
            {latest?.differential !== undefined
              ? `${latest.differential >= 0 ? '+' : ''}${latest.differential.toFixed(1)}`
              : 'N/A'}
          </span>
        </div>

        {/* 豊富/困難（サブ表示） */}
        <div style={{ display: 'flex', gap: 16 }}>
          <div>
            <span style={{ fontSize: 11, color: '#888' }}>豊富: </span>
            <span style={{ fontSize: 14, fontWeight: 'bold', color: COLORS.plentiful }}>
              {latest?.plentiful?.toFixed(1) ?? 'N/A'}%
            </span>
          </div>
          <div>
            <span style={{ fontSize: 11, color: '#888' }}>困難: </span>
            <span style={{ fontSize: 14, fontWeight: 'bold', color: COLORS.hard }}>
              {latest?.hard?.toFixed(1) ?? 'N/A'}%
            </span>
          </div>
        </div>

        {/* 失業率（あれば表示） */}
        {latestUnemployment !== undefined && latestUnemployment !== null && (
          <div>
            <span style={{ fontSize: 11, color: '#888' }}>失業率: </span>
            <span style={{ fontSize: 14, fontWeight: 'bold', color: COLORS.unemployment }}>
              {latestUnemployment.toFixed(1)}%
            </span>
          </div>
        )}

        {/* 日付 */}
        {latest?.date && (
          <span style={{ fontSize: 12, color: '#999' }}>
            ({formatDateLabelJP(latest.date)})
          </span>
        )}
      </div>

      {/* 次回発表 */}
      {nextRelease && (
        <div style={{ fontSize: 11, color: '#888', textAlign: 'right' }}>
          <div>次回発表: {nextRelease.date}</div>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CBJobsLaborChart({ data, unemploymentData }: CBJobsLaborChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { handleLegendClick, isHidden } = useHiddenSeries<'invertedDiff' | 'unemployment'>()

  // CB雇用機会業況判断データをソート
  const sortedCBData = useSortedData(data?.data)

  // 失業率データをソート
  const sortedUnemploymentData = useSortedData(unemploymentData?.data)

  // データをマージ（差分を反転）
  const mergedData = useMemo(() => {
    if (sortedCBData.length === 0) return []

    // 失業率を月でインデックス化（YYYY-MM形式に変換）
    const unemploymentMap = new Map<string, number>()
    sortedUnemploymentData.forEach(item => {
      // YYYY-MM-DD → YYYY-MM
      const yearMonth = item.date.substring(0, 7)
      unemploymentMap.set(yearMonth, item.unrate)
    })

    return sortedCBData.map(item => ({
      date: item.date,
      differential: item.differential,
      invertedDiff: -item.differential, // 上下反転
      plentiful: item.plentiful,
      hard: item.hard,
      unemployment: unemploymentMap.get(item.date) ?? null,
    }))
  }, [sortedCBData, sortedUnemploymentData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(mergedData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  const hasData = sortedCBData.length > 0

  if (data === null) {
    return <LoadingChart title="CB雇用機会業況判断" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="CB雇用機会業況判断" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const hasUnemployment = sortedUnemploymentData.length > 0
  const latestUnemployment = unemploymentData?.latest?.unrate

  return (
    <div id="cb-jobs-labor">
      <ChartContainer
        title="CB雇用機会業況判断 / 失業率"
        showPeriodSelector={false}
        dataSource="ConferenceBoard"
        sourceUrl="https://www.conference-board.org/topics/consumer-confidence/"
      >
        {/* 最新値表示 */}
        <LatestValueDisplay
          latest={latest}
          nextRelease={data.next_release}
          latestUnemployment={latestUnemployment}
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
                  {/* 期間セレクタ + 比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
                    <AntTooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=unemployment_rate', '_blank')}
                      >
                        データ比較
                      </Button>
                    </AntTooltip>
                  </div>

                  <ResponsiveContainer width="100%" height={450}>
                    <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                      <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                      <XAxis
                        dataKey="date"
                        tickFormatter={formatDateLabel}
                        tick={AXIS_STYLE.tick}
                        interval={AXIS_STYLE.interval}
                      />
                      {/* 左Y軸: 差分（反転）*/}
                      <YAxis
                        yAxisId="left"
                        domain={['auto', 'auto']}
                        tick={AXIS_STYLE.tick}
                        tickFormatter={(v) => `${-v}`}  // 表示時は元の値に戻す
                        label={{
                          value: 'CB雇用機会業況判断',
                          angle: -90,
                          position: 'insideLeft',
                          style: { fontSize: 11, fill: '#666' }
                        }}
                      />
                      {/* 右Y軸: 失業率（あれば） */}
                      {hasUnemployment && (
                        <YAxis
                          yAxisId="right"
                          orientation="right"
                          domain={['auto', 'auto']}
                          tick={AXIS_STYLE.tick}
                          tickFormatter={(v) => `${v}%`}
                          label={{
                            value: '失業率',
                            angle: 90,
                            position: 'insideRight',
                            style: { fontSize: 11, fill: '#666' }
                          }}
                        />
                      )}
                      <Tooltip content={<CustomTooltip />} />
                      <Legend
                        onClick={(e) => handleLegendClick(e.dataKey as string)}
                        wrapperStyle={{ cursor: 'pointer' }}
                      />

                      {/* ゼロライン */}
                      <ReferenceLine yAxisId="left" y={0} stroke="#000" strokeWidth={1} />

                      {/* 差分ライン（反転） */}
                      <Line
                        yAxisId="left"
                        type="monotone"
                        dataKey="invertedDiff"
                        stroke={COLORS.differential}
                        strokeWidth={2}
                        dot={false}
                        name="CB雇用機会業況判断"
                        hide={isHidden('invertedDiff')}
                        isAnimationActive={false}
                        connectNulls={true}
                      />

                      {/* 失業率（あれば） */}
                      {hasUnemployment && (
                        <Line
                          yAxisId="right"
                          type="monotone"
                          dataKey="unemployment"
                          stroke={COLORS.unemployment}
                          strokeWidth={2}
                          dot={false}
                          name="失業率"
                          hide={isHidden('unemployment')}
                          isAnimationActive={false}
                          connectNulls={true}
                        />
                      )}
                    </ComposedChart>
                  </ResponsiveContainer>
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
