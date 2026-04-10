import { useState, useMemo } from 'react'
import { Typography, Tooltip, Button } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import ChartContainer from '../../common/ChartContainer'
import PeriodSelector, { type PeriodValue } from '../../common/PeriodSelector'
import { formatMonthLabel, formatDayLabel } from '../../../utils/dateFormatters'
import { useHiddenSeries } from '../../country/usa/common/useChartData'

const { Text } = Typography

const DARK_THEME = {
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  bgTertiary: '#334155',
  gridLine: '#475569',
  axisLine: '#64748b',
  tooltipBg: '#334155',
  tooltipBorder: '#475569',
  chartBg: '#1e293b',
}

const COLOR_RATIO = '#f59e0b'     // amber - NT倍率
const COLOR_MA = '#ffffff'         // white - 移動平均
const COLOR_NIKKEI = '#ef4444'    // red - 日経平均
const COLOR_TOPIX = '#3b82f6'     // blue - TOPIX

interface NtMagnificationItem {
  date: string
  nikkei225: number | null
  topix: number | null
  ratio: number | null
}

interface NtMagnificationResponse {
  data: NtMagnificationItem[]
  latest: NtMagnificationItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

function useNtMagnificationData() {
  return useQuery({
    queryKey: ['market', 'nt-magnification'],
    queryFn: async () => {
      const { data } = await axios.get<NtMagnificationResponse>('/api/market/nt-magnification')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

type SeriesKey = 'ratio' | 'ma' | 'nikkei225' | 'topix_normalized'

function computeMA(data: { ratio: number | null }[], window: number): (number | null)[] {
  if (window <= 0) return data.map(() => null)
  const result: (number | null)[] = []
  for (let i = 0; i < data.length; i++) {
    if (i < window - 1) { result.push(null); continue }
    let sum = 0; let count = 0
    for (let j = i - window + 1; j <= i; j++) {
      if (data[j].ratio != null) { sum += data[j].ratio!; count++ }
    }
    result.push(count === window ? sum / count : null)
  }
  return result
}

const MA_WINDOW = 20

function NtTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))

  const tooltipSeries: { key: string; label: string; color: string; fmt: (v: number) => string }[] = [
    { key: 'ratio', label: 'NT倍率', color: COLOR_RATIO, fmt: (v: number) => v.toFixed(2) },
    { key: 'ma', label: `${MA_WINDOW}MA`, color: COLOR_MA, fmt: (v: number) => v.toFixed(2) },
    { key: 'nikkei225', label: '日経平均', color: COLOR_NIKKEI, fmt: (v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 0 }) },
    { key: '_topix_raw', label: 'TOPIX', color: COLOR_TOPIX, fmt: (v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 2 }) },
  ]

  return (
    <div style={{ backgroundColor: DARK_THEME.tooltipBg, border: `1px solid ${DARK_THEME.tooltipBorder}`, borderRadius: 8, padding: '12px 16px', boxShadow: '0 4px 16px rgba(0,0,0,0.3)' }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: '#f1f5f9' }}>{formattedLabel}</div>
      {tooltipSeries.map(({ key, label: seriesLabel, color, fmt }) => {
        if (key === '_topix_raw' && hiddenSeries.has('topix_normalized')) return null
        if (key !== '_topix_raw' && hiddenSeries.has(key)) return null
        const item = payload.find((p: { dataKey: string }) => p.dataKey === key)
        if (!item || typeof item.value !== 'number') return null
        return (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: color, marginRight: 6 }} />
              {seriesLabel}
            </span>
            <span style={{ fontWeight: 500, color }}>{fmt(item.value)}</span>
          </div>
        )
      })}
    </div>
  )
}

export default function NtMagnificationChart() {
  const { data: apiData, isLoading, error } = useNtMagnificationData()
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(2)
  const hiddenSeries = useHiddenSeries<SeriesKey>()

  const chartData = useMemo(() => {
    if (!apiData?.data) return []
    return apiData.data.sort((a, b) => a.date.localeCompare(b.date))
  }, [apiData])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 2
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  const viewData = useMemo(() => {
    const fullRatioData = chartData.map((d) => ({ ratio: d.ratio ?? null }))
    const maValues = computeMA(fullRatioData, MA_WINDOW)
    const startIdx = chartData.length - filteredData.length

    // TOPIXを日経平均のスケールに正規化
    // 表示期間の初日を基準に、TOPIX初日値→日経平均初日値に合わせる
    let scaleFactor = 1
    const firstItem = filteredData[0]
    if (firstItem && firstItem.nikkei225 != null && firstItem.topix != null && firstItem.topix > 0) {
      scaleFactor = firstItem.nikkei225 / firstItem.topix
    }

    return filteredData.map((d, i) => ({
      date: d.date,
      ratio: d.ratio ?? null,
      ma: maValues[startIdx + i] ?? null,
      nikkei225: d.nikkei225 ?? null,
      topix_normalized: d.topix != null ? Math.round(d.topix * scaleFactor) : null,
      _topix_raw: d.topix ?? null,
    }))
  }, [chartData, filteredData])

  if (isLoading) {
    return (
      <ChartContainer title="NT倍率" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (error || !apiData || chartData.length === 0) {
    return (
      <ChartContainer title="NT倍率" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = apiData.latest

  return (
    <ChartContainer
      title="NT倍率"
      dataSource="Stooq"
      sourceUrl="https://stooq.com/"
      handbookId="nt-magnification"
      showPeriodSelector={false}
    >
      {/* 最新値 */}
      {latest && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            marginBottom: 12,
            padding: '10px 14px',
            background: DARK_THEME.bgTertiary,
            borderRadius: 8,
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>NT倍率</Text>
            <Text style={{ color: COLOR_RATIO, fontSize: 16, fontWeight: 700 }} className="tabular-nums">
              {(latest.ratio ?? 0).toFixed(2)}
            </Text>
          </div>

          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>日経平均</Text>
            <Text style={{ color: COLOR_NIKKEI, fontSize: 13, fontWeight: 600 }} className="tabular-nums">
              {(latest.nikkei225 ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </Text>
          </div>

          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>TOPIX</Text>
            <Text style={{ color: COLOR_TOPIX, fontSize: 13, fontWeight: 600 }} className="tabular-nums">
              {(latest.topix ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </Text>
          </div>

          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>
            ({latest.date})
          </Text>
        </div>
      )}

      {/* データ比較ボタン */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            size="small"
            onClick={() => window.open('/compare?s=nt_magnification', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 期間選択 */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* 注釈 */}
      <div style={{ marginBottom: 8, padding: '6px 10px', background: 'rgba(245,158,11,0.08)', borderRadius: 6, fontSize: 11, color: DARK_THEME.textSecondary }}>
        日経平均 / TOPIX — NT倍率上昇 = 値がさ株（半導体等）優位, 下降 = 内需・バリュー株優位
      </div>

      {/* チャート */}
      <ResponsiveContainer width="100%" height={450}>
        <ComposedChart
          data={viewData}
          margin={{ top: 16, right: 8, bottom: 0, left: 0 }}
          style={{ backgroundColor: DARK_THEME.chartBg }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />

          <XAxis
            type="category"
            dataKey="date"
            tickFormatter={formatMonthLabel}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            tickMargin={16}
            height={60}
            interval="preserveStartEnd"
          />

          {/* 左Y軸: NT倍率 */}
          <YAxis
            yAxisId="left"
            domain={['dataMin - 0.5', 'dataMax + 0.5']}
            tickFormatter={(v: number) => v.toFixed(1)}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: COLOR_RATIO, fontSize: 11 }}
            tickMargin={8}
            label={{ value: 'NT倍率', angle: -90, position: 'insideLeft', offset: -8, fill: COLOR_RATIO, fontSize: 11 }}
          />

          {/* 右Y軸: 日経平均 + TOPIX（正規化済み） */}
          <YAxis
            yAxisId="price"
            orientation="right"
            domain={['dataMin * 0.95', 'dataMax * 1.05']}
            tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}K` : `${v}`}
            axisLine={{ stroke: DARK_THEME.axisLine, strokeDasharray: '4 3' }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 10 }}
            tickMargin={8}
            width={50}
          />

          <RechartsTooltip content={<NtTooltip hiddenSeries={hiddenSeries.hiddenSeries} />} />

          <Legend
            wrapperStyle={{ paddingTop: 8 }}
            onClick={(e) => hiddenSeries.handleLegendClick(e.dataKey as string)}
            formatter={(value: string, entry) => (
              <span style={{ color: hiddenSeries.hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : DARK_THEME.textPrimary, fontSize: 11 }}>
                {value}
              </span>
            )}
          />

          {/* NT倍率 */}
          <Line type="monotone" dataKey="ratio" stroke={COLOR_RATIO} strokeWidth={2} dot={false} name="NT倍率" yAxisId="left" connectNulls isAnimationActive={false} hide={hiddenSeries.isHidden('ratio')} />

          {/* MA線 */}
          <Line type="monotone" dataKey="ma" stroke={COLOR_MA} strokeWidth={1.5} strokeDasharray="4 2" dot={false} name={`${MA_WINDOW}MA`} yAxisId="left" connectNulls isAnimationActive={false} hide={hiddenSeries.isHidden('ma')} />

          {/* 日経平均（右Y軸） */}
          <Line type="monotone" dataKey="nikkei225" stroke={COLOR_NIKKEI} strokeWidth={1} strokeOpacity={0.6} dot={false} name="日経平均" yAxisId="price" connectNulls isAnimationActive={false} hide={hiddenSeries.isHidden('nikkei225')} />

          {/* TOPIX（正規化して右Y軸に重ねる） */}
          <Line type="monotone" dataKey="topix_normalized" stroke={COLOR_TOPIX} strokeWidth={1} strokeOpacity={0.6} dot={false} name="TOPIX" yAxisId="price" connectNulls isAnimationActive={false} hide={hiddenSeries.isHidden('topix_normalized')} />

          {/* 実際のTOPIX値（ツールチップ用、非表示） */}
          <Line type="monotone" dataKey="_topix_raw" stroke="transparent" strokeWidth={0} dot={false} yAxisId="price" connectNulls isAnimationActive={false} legendType="none" />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
