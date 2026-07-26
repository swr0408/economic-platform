/**
 * シカゴ連銀失業率予測（Chicago Fed Real-Time Unemployment Rate Forecast）チャート
 *
 * データソース: Chicago Fed Labor Market Indicators Excel
 * - Sheet 1 (Rates): 採用率(hiring_rate_uw)、離職率(layoffs_other_seps)、
 *   フロー整合失業率(fcr)、CPS派生 s/f
 * - Sheet 2 (UR Forecast): forecast16/25/50/75/84 a(Advance)/f(Final)/r(Revised) + BLS official_u3
 * - Sheet 4 (UR Probabilities): 次回BLS発表値の確率分布 (-0.3pp〜+0.3ppの7バケット)
 *
 * 表示モード:
 * - 確率分布（probability）: 次回BLS発表値の確率分布バーチャート + Relative Odds
 * - 予測時系列（forecast）: 50パーセンタイル(Final) + 25/75 + BLS実績(official_u3)
 * - 雇用フローレート（rates）: モデルの入力フロー（採用率/離職率/FCR）
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip as AntTooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  LabelList,
  Cell,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type {
  ChicagoFedUnemploymentRateForecastData,
  ChicagoFedUnemploymentRateForecastProbabilityItem,
} from '../../../../hooks/useDashboardData'

import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabelJP,
  useHiddenSeries,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  StandardLineChart,
  ViewModeButtonGroup,
} from '../common/ChartComponents'
import {
  TEXT_COLORS,
  DARK_THEME,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
} from '../common/chartConstants'

// =============================================================================
// 型定義
// =============================================================================

interface ChicagoFedUnemploymentRateForecastChartProps {
  data: ChicagoFedUnemploymentRateForecastData | null
}

type ViewMode = 'probability' | 'forecast' | 'rates'

const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'probability', label: '確率分布' },
  { mode: 'forecast', label: '予測時系列' },
  { mode: 'rates', label: '雇用フローレート' },
]

// 失業率予測モードのカラー設定
const FORECAST_COLORS = {
  forecast50f: '#3b82f6',
  forecast50a: '#60a5fa',
  forecast25f: '#a78bfa',
  forecast75f: '#a78bfa',
  forecast16f: '#c4b5fd',
  forecast84f: '#c4b5fd',
  official_u3: '#ef4444',
}

// 雇用フローレートモードのカラー設定
const RATES_COLORS = {
  fcr: '#3b82f6',
  layoffs_other_seps: '#ef4444',
  hiring_rate_uw: '#10b981',
  s_cps: '#f59e0b',
  f_cps: '#8b5cf6',
}

const RATES_NAMES = {
  fcr: 'フロー整合失業率 (FCR, L)',
  layoffs_other_seps: 'レイオフ・その他離職率 (L)',
  hiring_rate_uw: '失業者採用率 [Chicago Fed] (R)',
  s_cps: 'CPS全離職率 [自発+非自発] (L)',
  f_cps: 'CPS就職率 (R)',
}

// 確率分布モードのバケット定義
const PROB_BUCKETS: {
  key: keyof ChicagoFedUnemploymentRateForecastProbabilityItem['buckets']
  label: string
  delta: number
  direction: 'decrease' | 'no_change' | 'increase'
}[] = [
  { key: 'bucket_neg_03_or_lower', label: '≤ -0.3 pp', delta: -0.3, direction: 'decrease' },
  { key: 'bucket_neg_02', label: '-0.2 pp', delta: -0.2, direction: 'decrease' },
  { key: 'bucket_neg_01', label: '-0.1 pp', delta: -0.1, direction: 'decrease' },
  { key: 'bucket_no_change', label: 'No change', delta: 0.0, direction: 'no_change' },
  { key: 'bucket_pos_01', label: '+0.1 pp', delta: 0.1, direction: 'increase' },
  { key: 'bucket_pos_02', label: '+0.2 pp', delta: 0.2, direction: 'increase' },
  { key: 'bucket_pos_03_or_higher', label: '≥ +0.3 pp', delta: 0.3, direction: 'increase' },
]

const BUCKET_COLOR = '#3b82f6'
const ODDS_INCREASE_COLOR = '#ef4444'
const ODDS_DECREASE_COLOR = '#10b981'

// =============================================================================
// 確率分布バーチャート (Sheet 4)
// =============================================================================

function ProbabilityDistributionChart({
  probability,
  forecastDate,
}: {
  probability: ChicagoFedUnemploymentRateForecastProbabilityItem
  forecastDate?: string
}) {
  const baseline = probability.baseline_ur ?? null
  const chartData = useMemo(
    () =>
      PROB_BUCKETS.map((b) => {
        const value = probability.buckets[b.key]
        const urLevel = baseline != null ? baseline + b.delta : null
        return {
          bucket: b.label,
          urLevel,
          urLevelLabel:
            urLevel != null ? `(${urLevel.toFixed(1)}%)` : '',
          value: value ?? 0,
          rawValue: value,
          direction: b.direction,
        }
      }),
    [probability, baseline],
  )

  const oddsIncrease = probability.relative_odds.increase
  const oddsDecrease = probability.relative_odds.decrease
  const oddsNet = probability.relative_odds.net

  const forecastMonthLabel = useMemo(() => {
    if (!forecastDate) return ''
    try {
      const d = new Date(forecastDate)
      return d.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
      })
    } catch {
      return forecastDate
    }
  }, [forecastDate])

  // X軸の2段組ティック (バケット名 + 推定 UR レベル)
  const renderXAxisTick = (props: {
    x?: number
    y?: number
    payload?: { value: string }
  }) => {
    const { x = 0, y = 0, payload } = props
    if (!payload) return <g />
    const item = chartData.find((d) => d.bucket === payload.value)
    return (
      <g transform={`translate(${x},${y})`}>
        <text
          x={0}
          y={0}
          dy={12}
          textAnchor="middle"
          fill={DARK_THEME.textSecondary}
          fontSize={11}
        >
          {payload.value}
        </text>
        {item?.urLevelLabel && (
          <text
            x={0}
            y={0}
            dy={28}
            textAnchor="middle"
            fill={DARK_THEME.textTertiary}
            fontSize={10}
          >
            {item.urLevelLabel}
          </text>
        )}
      </g>
    )
  }

  return (
    <>
      {/* タイトル + Relative Odds パネル */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 8,
          gap: 16,
          flexWrap: 'wrap',
        }}
      >
        <div>
          <div style={{ fontSize: 14, fontWeight: 'bold', color: TEXT_COLORS.primary }}>
            {forecastMonthLabel} BLS Unemployment Rate Probabilities
          </div>
          <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, marginTop: 2 }}>
            次回BLS失業率発表値の確率分布
            {baseline != null && (
              <>
                {' '}/ 現在値ベースライン: <b>{baseline.toFixed(2)}%</b>
              </>
            )}
            {' '}({probability.release})
          </div>
        </div>

        {/* Relative Odds テーブル */}
        <div
          style={{
            border: `1px solid ${DARK_THEME.border}`,
            borderRadius: 6,
            padding: '8px 12px',
            background: DARK_THEME.bgSecondary,
            minWidth: 180,
          }}
        >
          <div
            style={{
              fontSize: 11,
              fontWeight: 'bold',
              textAlign: 'center',
              color: TEXT_COLORS.secondary,
              marginBottom: 4,
              borderBottom: `1px solid ${DARK_THEME.border}`,
              paddingBottom: 4,
            }}
          >
            Relative Odds
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr auto',
              gap: '2px 12px',
              fontSize: 12,
            }}
          >
            <span style={{ color: ODDS_INCREASE_COLOR, fontWeight: 'bold' }}>Increase</span>
            <span style={{ color: TEXT_COLORS.primary, textAlign: 'right' }}>
              {oddsIncrease != null ? `${oddsIncrease.toFixed(0)}%` : 'N/A'}
            </span>
            <span style={{ color: ODDS_DECREASE_COLOR, fontWeight: 'bold' }}>Decrease</span>
            <span style={{ color: TEXT_COLORS.primary, textAlign: 'right' }}>
              {oddsDecrease != null ? `${oddsDecrease.toFixed(0)}%` : 'N/A'}
            </span>
            <span style={{ color: TEXT_COLORS.secondary, fontWeight: 'bold' }}>Net</span>
            <span
              style={{
                fontWeight: 'bold',
                textAlign: 'right',
                color:
                  oddsNet == null
                    ? TEXT_COLORS.primary
                    : oddsNet > 0
                    ? ODDS_INCREASE_COLOR
                    : ODDS_DECREASE_COLOR,
              }}
            >
              {oddsNet != null ? `${oddsNet > 0 ? '+' : ''}${oddsNet.toFixed(0)}` : 'N/A'}
            </span>
          </div>
        </div>
      </div>

      {/* バーチャート + 密度ライン */}
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart data={chartData} margin={{ ...CHART_MARGIN, bottom: 30 }}>
          <CartesianGrid {...CARTESIAN_GRID_PROPS} />
          <XAxis
            dataKey="bucket"
            tick={renderXAxisTick}
            interval={0}
            height={50}
          />
          <YAxis
            tick={AXIS_STYLE.tick}
            tickFormatter={(v: number) => `${v.toFixed(0)}%`}
            domain={[0, 'dataMax + 5']}
          />
          <RechartsTooltip
            content={({ active, payload }) => {
              if (!active || !payload || payload.length === 0) return null
              const item = payload[0].payload as (typeof chartData)[number]
              return (
                <div
                  style={{
                    backgroundColor: DARK_THEME.bgTertiary,
                    border: `1px solid ${DARK_THEME.borderLight}`,
                    borderRadius: 8,
                    padding: '10px 14px',
                    color: TEXT_COLORS.primary,
                  }}
                >
                  <div style={{ fontWeight: 'bold', marginBottom: 4 }}>{item.bucket}</div>
                  {item.urLevel != null && (
                    <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary }}>
                      推定 UR: {item.urLevel.toFixed(1)}%
                    </div>
                  )}
                  <div style={{ marginTop: 4, color: BUCKET_COLOR }}>
                    確率: {item.rawValue != null ? `${item.rawValue.toFixed(1)}%` : 'N/A'}
                  </div>
                </div>
              )
            }}
          />
          <Bar dataKey="value" name="確率" fill={BUCKET_COLOR} isAnimationActive={false}>
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={
                  entry.direction === 'increase'
                    ? ODDS_INCREASE_COLOR
                    : entry.direction === 'decrease'
                    ? ODDS_DECREASE_COLOR
                    : BUCKET_COLOR
                }
                fillOpacity={0.85}
              />
            ))}
            <LabelList
              dataKey="value"
              position="top"
              formatter={(v: number) => (v > 0 ? `${v.toFixed(1)}%` : '')}
              style={{ fill: TEXT_COLORS.secondary, fontSize: 11, fontWeight: 'bold' }}
            />
          </Bar>
          {/* 密度カーブ（バー頂点を結ぶ破線） */}
          <Line
            type="monotone"
            dataKey="value"
            stroke={DARK_THEME.textTertiary}
            strokeWidth={1.5}
            strokeDasharray="5 4"
            dot={false}
            isAnimationActive={false}
            legendType="none"
          />
        </ComposedChart>
      </ResponsiveContainer>

      <div style={{ marginTop: 8, fontSize: 11, color: TEXT_COLORS.tertiary }}>
        ※ 赤=上昇方向／緑=下落方向／青=変化なし。Increase / Decrease は方向別の合計確率。
        Net = Increase - Decrease。括弧内は推定UR水準（ベースライン+各バケットの変化幅）。
      </div>
    </>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function ChicagoFedUnemploymentRateForecastChart({
  data,
}: ChicagoFedUnemploymentRateForecastChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('probability')
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('all')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // 失業率予測モード用データ: forecast 系列が含まれる行のみ
  const forecastSortedAll = useSortedData(
    (data?.forecast_data ?? []).filter(
      (d) => d.forecast50f != null || d.forecast50a != null,
    ),
  )

  // 雇用フローレートモード用データ
  const ratesSortedAll = useSortedData(data?.rates_data ?? [])

  const sortedData = viewMode === 'forecast' ? forecastSortedAll : ratesSortedAll
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  // ローディング
  if (data === null) {
    return <LoadingChart title="シカゴ連銀失業率予測" />
  }

  const hasData = (data.data ?? []).length > 0

  if (!hasData) {
    return (
      <ChartContainer
        title="シカゴ連銀失業率予測"
        showPeriodSelector={false}
        showDataSource={false}
      >
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const latestRates = data.latest_rates
  const latestProbability = data.latest_probability
  const nextRelease = data.next_release

  // 最新月は Final 公表前だと forecast50f が未確定（advance のみ）。
  // その場合は Advance 値にフォールバックし、ラベルもそれに合わせる（N/A 回避）。
  const latestForecast50IsFinal = latest?.forecast50f != null
  const latestForecast50 =
    latest?.forecast50f ?? latest?.forecast50a ?? null
  const latestForecast50Label = latestForecast50IsFinal
    ? '失業率予測 (Final, 50%)'
    : '失業率予測 (Advance, 50%)'
  const latestForecast50Color = latestForecast50IsFinal
    ? FORECAST_COLORS.forecast50f
    : FORECAST_COLORS.forecast50a

  // 最新値ボックス
  const latestItems =
    viewMode === 'forecast'
      ? [
          {
            label: '失業率予測 (Final, 50%)',
            value: latest?.forecast50f ?? null,
            color: FORECAST_COLORS.forecast50f,
            format: 'percent' as const,
            decimals: 2,
          },
          {
            label: '失業率予測 (Advance, 50%)',
            value: latest?.forecast50a ?? null,
            color: FORECAST_COLORS.forecast50a,
            format: 'percent' as const,
            decimals: 2,
          },
          ...(latest?.official_u3 != null
            ? [
                {
                  label: 'BLS U-3 実績',
                  value: latest.official_u3,
                  color: FORECAST_COLORS.official_u3,
                  format: 'percent' as const,
                  decimals: 2,
                },
              ]
            : []),
        ]
      : viewMode === 'rates'
      ? [
          {
            label: 'FCR',
            value: latestRates?.fcr ?? null,
            color: RATES_COLORS.fcr,
            format: 'percent' as const,
            decimals: 2,
          },
          {
            label: '失業者採用率',
            value: latestRates?.hiring_rate_uw ?? null,
            color: RATES_COLORS.hiring_rate_uw,
            format: 'percent' as const,
            decimals: 2,
          },
          {
            label: 'レイオフ等離職率',
            value: latestRates?.layoffs_other_seps ?? null,
            color: RATES_COLORS.layoffs_other_seps,
            format: 'percent' as const,
            decimals: 2,
          },
        ]
      : [
          {
            label: latestForecast50Label,
            value: latestForecast50,
            color: latestForecast50Color,
            format: 'percent' as const,
            decimals: 2,
          },
          {
            label: 'Net (Inc - Dec)',
            value: latestProbability?.relative_odds.net ?? null,
            color:
              (latestProbability?.relative_odds.net ?? 0) > 0
                ? ODDS_INCREASE_COLOR
                : ODDS_DECREASE_COLOR,
            format: 'number' as const,
            decimals: 1,
            unit: '%pt',
          },
          {
            label: 'ベースラインUR',
            value: latestProbability?.baseline_ur ?? null,
            color: TEXT_COLORS.primary,
            format: 'percent' as const,
            decimals: 2,
          },
        ]

  const latestDate =
    viewMode === 'forecast'
      ? latest?.date
      : viewMode === 'rates'
      ? latestRates?.date
      : latestProbability?.date

  return (
    <div id="chicago-fed-ur-forecast">
      <ChartContainer
        title="シカゴ連銀失業率予測"
        showPeriodSelector={false}
        dataSource="Chicago Fed Labor Market Indicators"
        sourceUrl="https://www.chicagofed.org/research/data/chicago-fed-labor-market-indicators/latest-release"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={latestItems}
          date={latestDate ?? undefined}
          nextRelease={
            nextRelease
              ? {
                  date: nextRelease.date,
                  label: nextRelease.label,
                  time_jst: nextRelease.time_jst,
                }
              : null
          }
        />

        {/* ViewModeButtonGroup + データ比較ボタン */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 8,
          }}
        >
          <ViewModeButtonGroup
            options={VIEW_MODE_OPTIONS}
            currentMode={viewMode}
            onChange={setViewMode}
          />
          <AntTooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() =>
                window.open(
                  '/compare?s=chicago_fed_unemployment_rate_forecast',
                  '_blank',
                )
              }
            >
              データ比較
            </Button>
          </AntTooltip>
        </div>

        {/* 期間セレクター（時系列モードのみ） */}
        {viewMode !== 'probability' && (
          <PeriodSelector
            onPeriodChange={setSelectedPeriod}
            selectedPeriod={selectedPeriod}
          />
        )}

        {/* グラフ */}
        {viewMode === 'probability' ? (
          latestProbability ? (
            <ProbabilityDistributionChart
              probability={latestProbability}
              forecastDate={latestProbability.date}
            />
          ) : (
            <NoDataMessage />
          )
        ) : viewMode === 'forecast' ? (
          <StandardLineChart
            data={filteredData}
            lines={[
              {
                dataKey: 'forecast50f',
                color: FORECAST_COLORS.forecast50f,
                name: '予測中央値 (Final)',
                strokeWidth: 2,
                hide: hiddenSeries.has('forecast50f'),
              },
              {
                dataKey: 'forecast50a',
                color: FORECAST_COLORS.forecast50a,
                name: '予測中央値 (Advance)',
                strokeWidth: 2,
                strokeDasharray: '5 3',
                hide: hiddenSeries.has('forecast50a'),
              },
              {
                dataKey: 'forecast25f',
                color: FORECAST_COLORS.forecast25f,
                name: '25%タイル',
                strokeWidth: 1,
                strokeDasharray: '3 3',
                hide: hiddenSeries.has('forecast25f'),
              },
              {
                dataKey: 'forecast75f',
                color: FORECAST_COLORS.forecast75f,
                name: '75%タイル',
                strokeWidth: 1,
                strokeDasharray: '3 3',
                hide: hiddenSeries.has('forecast75f'),
              },
              {
                dataKey: 'forecast16f',
                color: FORECAST_COLORS.forecast16f,
                name: '16%タイル',
                strokeWidth: 1,
                strokeDasharray: '2 4',
                hide: hiddenSeries.has('forecast16f'),
              },
              {
                dataKey: 'forecast84f',
                color: FORECAST_COLORS.forecast84f,
                name: '84%タイル',
                strokeWidth: 1,
                strokeDasharray: '2 4',
                hide: hiddenSeries.has('forecast84f'),
              },
              {
                dataKey: 'official_u3',
                color: FORECAST_COLORS.official_u3,
                name: 'BLS U-3 実績',
                strokeWidth: 2,
                hide: hiddenSeries.has('official_u3'),
              },
            ]}
            yAxisFormatter={(v) => `${v.toFixed(1)}%`}
            yDomain={['dataMin - 0.2', 'dataMax + 0.2']}
            tooltipLabelFormatter={formatDateLabelJP}
            tooltipValueFormatter={(v) =>
              v != null ? `${v.toFixed(2)}%` : 'N/A'
            }
            showZeroLine={false}
            onLegendClick={handleLegendClick}
          />
        ) : (
          <StandardLineChart
            data={filteredData}
            lines={[
              {
                dataKey: 'fcr',
                color: RATES_COLORS.fcr,
                name: RATES_NAMES.fcr,
                strokeWidth: 2,
                hide: hiddenSeries.has('fcr'),
              },
              {
                dataKey: 'layoffs_other_seps',
                color: RATES_COLORS.layoffs_other_seps,
                name: RATES_NAMES.layoffs_other_seps,
                strokeWidth: 2,
                hide: hiddenSeries.has('layoffs_other_seps'),
              },
              {
                dataKey: 's_cps',
                color: RATES_COLORS.s_cps,
                name: RATES_NAMES.s_cps,
                strokeWidth: 1,
                strokeDasharray: '4 3',
                hide: hiddenSeries.has('s_cps'),
              },
              {
                dataKey: 'hiring_rate_uw',
                color: RATES_COLORS.hiring_rate_uw,
                name: RATES_NAMES.hiring_rate_uw,
                strokeWidth: 2,
                yAxisId: 'right',
                hide: hiddenSeries.has('hiring_rate_uw'),
              },
              {
                dataKey: 'f_cps',
                color: RATES_COLORS.f_cps,
                name: RATES_NAMES.f_cps,
                strokeWidth: 1,
                strokeDasharray: '4 3',
                yAxisId: 'right',
                hide: hiddenSeries.has('f_cps'),
              },
            ]}
            yAxisFormatter={(v) => `${v.toFixed(1)}%`}
            rightYAxisFormatter={(v) => `${v.toFixed(0)}%`}
            yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
            rightYDomain={['dataMin - 2', 'dataMax + 2']}
            tooltipLabelFormatter={formatDateLabelJP}
            tooltipValueFormatter={(v) =>
              v != null ? `${v.toFixed(2)}%` : 'N/A'
            }
            showZeroLine={false}
            onLegendClick={handleLegendClick}
          />
        )}

        {viewMode === 'forecast' && (
          <div style={{ marginTop: 8, fontSize: 11, color: TEXT_COLORS.tertiary }}>
            ※ 日付は BLS 参照週終点。Advance は雇用統計発表前、Final は発表後の予測値。
            16/25/50/75/84 は予測分布のパーセンタイル。
          </div>
        )}
        {viewMode === 'rates' && (
          <div style={{ marginTop: 8, fontSize: 11, color: TEXT_COLORS.tertiary }}>
            ※ モデルへの「入力」フロー。FCR (フロー整合失業率) は s/(s+f) で
            計算される定常状態の失業率 — 現在の離職率と就職率が続いた場合に
            失業率が収束する水準。実際の失業率より高ければ将来上昇圧力、
            低ければ下落圧力を示唆する先行指標。
            Chicago Fed の `layoffs_other_seps` は**レイオフ＋非自発的離職**主体
            （自発離職 quits は含まない）。CPS の `s` は**全離職**（自発含む）で範囲が異なる。
          </div>
        )}
      </ChartContainer>
    </div>
  )
}
