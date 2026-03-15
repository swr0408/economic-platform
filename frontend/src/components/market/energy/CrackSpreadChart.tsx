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
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../common/ChartContainer'
import PeriodSelector, { type PeriodValue } from '../../common/PeriodSelector'
import { formatDayLabel } from '../../../utils/dateFormatters'
import { useHiddenSeries } from '../../country/usa/common/useChartData'
import { ViewModeButtonGroup } from '../../country/usa/common/ChartComponents'

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

// WTI系列の色
const WTI_COLORS = {
  crack_321: '#f59e0b',    // アンバー (3:2:1)
  rbob: '#ef4444',          // 赤 (RBOB)
  ulsd: '#3b82f6',          // 青 (ULSD)
  price: '#94a3b8',         // グレー (原油価格)
}

// Brent系列の色
const BRENT_COLORS = {
  crack_321: '#10b981',    // エメラルド (3:2:1)
  rbob: '#f97316',          // オレンジ (RBOB)
  ulsd: '#8b5cf6',          // パープル (ULSD)
  price: '#94a3b8',         // グレー (原油価格)
}

interface CrackSpreadItem {
  date: string
  wti: number | null
  brent?: number | null
  rbob_crack_wti: number | null
  ulsd_crack_wti: number | null
  crack_321_wti: number | null
  rbob_crack_brent?: number | null
  ulsd_crack_brent?: number | null
  crack_321_brent?: number | null
}

interface CrackSpreadResponse {
  data: CrackSpreadItem[]
  latest: CrackSpreadItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

function useCrackSpreadData() {
  return useQuery({
    queryKey: ['market', 'crack-spread'],
    queryFn: async () => {
      const { data } = await axios.get<CrackSpreadResponse>('/api/market/crack-spread')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

type BaseMode = 'wti' | 'brent'

type WtiSeriesKey = 'crack_321_wti' | 'rbob_crack_wti' | 'ulsd_crack_wti' | 'wti'
type BrentSeriesKey = 'crack_321_brent' | 'rbob_crack_brent' | 'ulsd_crack_brent' | 'brent'
type SeriesKey = WtiSeriesKey | BrentSeriesKey

interface SeriesConfigItem {
  key: SeriesKey
  label: string
  color: string
  yAxisId: string
  isDashed?: boolean
}

const WTI_SERIES: SeriesConfigItem[] = [
  { key: 'crack_321_wti', label: '3:2:1 Crack', color: WTI_COLORS.crack_321, yAxisId: 'left' },
  { key: 'rbob_crack_wti', label: 'RBOB Crack', color: WTI_COLORS.rbob, yAxisId: 'left' },
  { key: 'ulsd_crack_wti', label: 'ULSD Crack', color: WTI_COLORS.ulsd, yAxisId: 'left' },
  { key: 'wti', label: 'WTI', color: WTI_COLORS.price, yAxisId: 'right', isDashed: true },
]

const BRENT_SERIES: SeriesConfigItem[] = [
  { key: 'crack_321_brent', label: '3:2:1 Crack', color: BRENT_COLORS.crack_321, yAxisId: 'left' },
  { key: 'rbob_crack_brent', label: 'RBOB Crack', color: BRENT_COLORS.rbob, yAxisId: 'left' },
  { key: 'ulsd_crack_brent', label: 'ULSD Crack', color: BRENT_COLORS.ulsd, yAxisId: 'left' },
  { key: 'brent', label: 'Brent', color: BRENT_COLORS.price, yAxisId: 'right', isDashed: true },
]

function CustomTooltip({ active, payload, label, hiddenSeries, seriesConfig }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
  seriesConfig: SeriesConfigItem[]
}) {
  if (!active || !payload || payload.length === 0) return null

  const formattedLabel = formatDayLabel(String(label))

  return (
    <div
      style={{
        backgroundColor: DARK_THEME.tooltipBg,
        border: `1px solid ${DARK_THEME.tooltipBorder}`,
        borderRadius: 8,
        padding: '12px 16px',
        boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
      }}
    >
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: '#f1f5f9' }}>
        {formattedLabel}
      </div>

      {seriesConfig.map(({ key, label: seriesLabel, color }) => {
        if (hiddenSeries.has(key)) return null
        const item = payload.find((p: { dataKey: string }) => p.dataKey === key)
        if (!item || typeof item.value !== 'number') return null

        const isPrice = key === 'wti' || key === 'brent'
        const formatted = isPrice
          ? `$${item.value.toFixed(2)}`
          : `$${item.value.toFixed(2)}/bbl`

        return (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: color, marginRight: 6 }} />
              {seriesLabel}
            </span>
            <span style={{ fontWeight: 500, color }}>
              {formatted}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export default function CrackSpreadChart() {
  const { data: apiData, isLoading, error } = useCrackSpreadData()
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(2)
  const [baseMode, setBaseMode] = useState<BaseMode>('wti')
  const { hiddenSeries, handleLegendClick, isHidden } = useHiddenSeries<SeriesKey>()

  const seriesConfig = baseMode === 'wti' ? WTI_SERIES : BRENT_SERIES
  const mainColor = baseMode === 'wti' ? WTI_COLORS.crack_321 : BRENT_COLORS.crack_321

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

  if (isLoading) {
    return (
      <ChartContainer title="クラックスプレッド" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (error || !apiData || chartData.length === 0) {
    return (
      <ChartContainer title="クラックスプレッド" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = apiData.latest
  const titleSuffix = baseMode === 'wti' ? '（WTIベース）' : '（Brentベース）'

  return (
    <ChartContainer
      title={`クラックスプレッド${titleSuffix}`}
      dataSource="yfinance (CL=F, BZ=F, RB=F, HO=F)"
      sourceUrl="https://finance.yahoo.com/quote/CL=F/"
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
          {seriesConfig.map(({ key, label, color }) => {
            const val = latest[key as keyof CrackSpreadItem]
            if (val == null) return null
            const formatted = `$${(val as number).toFixed(2)}`

            return (
              <div
                key={key}
                style={{
                  display: 'flex',
                  alignItems: 'baseline',
                  gap: 6,
                  opacity: isHidden(key) ? 0.3 : 1,
                  cursor: 'pointer',
                }}
                onClick={() => handleLegendClick(key)}
              >
                <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>{label}</Text>
                <Text
                  style={{ color, fontSize: 14, fontWeight: 700 }}
                  className="tabular-nums"
                >
                  {formatted}
                </Text>
              </div>
            )
          })}

          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>
            ({latest.date})
          </Text>
        </div>
      )}

      {/* WTI/Brent切替 + データ比較ボタン */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <ViewModeButtonGroup
          options={[
            { mode: 'wti' as BaseMode, label: 'WTI' },
            { mode: 'brent' as BaseMode, label: 'Brent' },
          ]}
          currentMode={baseMode}
          onChange={(m) => setBaseMode(m as BaseMode)}
        />
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            size="small"
            onClick={() => window.open('/compare?s=crack_spread', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 期間選択 */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* チャート */}
      <ResponsiveContainer width="100%" height={450}>
        <ComposedChart
          data={filteredData}
          margin={{ top: 16, right: 8, bottom: 0, left: 4 }}
          style={{ backgroundColor: DARK_THEME.chartBg }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />

          <XAxis
            type="category"
            dataKey="date"
            tickFormatter={formatDayLabel}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            tickMargin={16}
            height={60}
            interval="preserveStartEnd"
          />

          {/* 左Y軸: クラックスプレッド (USD/bbl) */}
          <YAxis
            yAxisId="left"
            domain={['auto', 'auto']}
            tickFormatter={(v: number) => `$${v}`}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: mainColor, fontSize: 11 }}
            tickMargin={4}
            width={52}
          />

          {/* 右Y軸: 原油価格 (USD/bbl) */}
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={['dataMin', 'dataMax']}
            tickFormatter={(v: number) => `$${v}`}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: WTI_COLORS.price, fontSize: 11 }}
            tickMargin={4}
            width={52}
          />

          {/* 基準線: $0 */}
          <ReferenceLine yAxisId="left" y={0} stroke="#64748b" strokeDasharray="4 4" strokeWidth={1} />

          <RechartsTooltip content={<CustomTooltip hiddenSeries={hiddenSeries} seriesConfig={seriesConfig} />} />

          <Legend
            wrapperStyle={{ paddingTop: 8 }}
            onClick={(e) => handleLegendClick(e.dataKey as string)}
            formatter={(value: string, entry) => (
              <span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : DARK_THEME.textPrimary, fontSize: 11 }}>
                {value}
              </span>
            )}
          />

          {seriesConfig.map(({ key, label, color, yAxisId, isDashed }) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={color}
              strokeWidth={isDashed ? 1 : key.startsWith('crack_321') ? 2 : 1.5}
              dot={false}
              name={label}
              yAxisId={yAxisId}
              connectNulls
              isAnimationActive={false}
              hide={isHidden(key)}
              strokeDasharray={isDashed ? '4 2' : undefined}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
