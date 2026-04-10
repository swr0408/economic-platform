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
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts'
import ChartContainer from '../../common/ChartContainer'
import PeriodSelector, { type PeriodValue } from '../../common/PeriodSelector'
import { ViewModeButtonGroup } from '../../country/usa/common/ChartComponents'
import { formatDayLabel } from '../../../utils/dateFormatters'
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

// Colors
const COLOR_VOL_PCR = '#f59e0b'   // 取引高PCR - amber
const COLOR_OI_PCR = '#a855f7'    // 建玉PCR - purple
const COLOR_NIKKEI = '#ef4444'    // 日経平均 - red
const COLOR_TOPIX = '#3b82f6'     // TOPIX - blue

interface JpxPcrItem {
  date: string
  nk225_vol_pcr: number | null
  nk225_oi_pcr: number | null
  nk225mini_vol_pcr: number | null
  nk225mini_oi_pcr: number | null
  topix_vol_pcr: number | null
  topix_oi_pcr: number | null
  nikkei225: number | null
  topix_idx: number | null
}

interface JpxPcrResponse {
  data: JpxPcrItem[]
  latest: JpxPcrItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

function useJpxPcrData() {
  return useQuery({
    queryKey: ['market', 'jpx-pcr'],
    queryFn: async () => {
      const { data } = await axios.get<JpxPcrResponse>('/api/market/jpx-pcr')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

type ProductView = 'nk225' | 'nk225mini' | 'topix'

const PRODUCT_OPTIONS: { mode: ProductView; label: string }[] = [
  { mode: 'nk225', label: '日経225' },
  { mode: 'nk225mini', label: '日経225ミニ' },
  { mode: 'topix', label: 'TOPIX' },
]

interface OiReferenceLine {
  value: number
  label: string
}

interface ProductConfig {
  label: string
  volKey: keyof JpxPcrItem
  oiKey: keyof JpxPcrItem
  indexKey: keyof JpxPcrItem
  indexLabel: string
  indexColor: string
  oiRefLines?: OiReferenceLine[]
}

const PRODUCT_CONFIGS: Record<ProductView, ProductConfig> = {
  nk225: {
    label: '日経225オプション',
    volKey: 'nk225_vol_pcr',
    oiKey: 'nk225_oi_pcr',
    indexKey: 'nikkei225',
    indexLabel: '日経平均',
    indexColor: COLOR_NIKKEI,
    oiRefLines: [
      { value: 1.5, label: '1.5' },
      { value: 2.0, label: '2.0' },
    ],
  },
  nk225mini: {
    label: '日経225ミニオプション',
    volKey: 'nk225mini_vol_pcr',
    oiKey: 'nk225mini_oi_pcr',
    indexKey: 'nikkei225',
    indexLabel: '日経平均',
    indexColor: COLOR_NIKKEI,
    oiRefLines: [
      { value: 0.8, label: '0.8' },
      { value: 1.7, label: '1.7' },
      { value: 1.9, label: '1.9' },
    ],
  },
  topix: {
    label: 'TOPIXオプション',
    volKey: 'topix_vol_pcr',
    oiKey: 'topix_oi_pcr',
    indexKey: 'topix_idx',
    indexLabel: 'TOPIX',
    indexColor: COLOR_TOPIX,
  },
}

type SeriesKey = 'vol_pcr' | 'oi_pcr' | 'index'

function getSeriesConfig(config: ProductConfig): { key: SeriesKey; label: string; color: string }[] {
  return [
    { key: 'vol_pcr', label: '取引高PCR', color: COLOR_VOL_PCR },
    { key: 'oi_pcr', label: '建玉PCR', color: COLOR_OI_PCR },
    { key: 'index', label: `${config.indexLabel}`, color: config.indexColor },
  ]
}

function CustomTooltip({ active, payload, label, hiddenSeries, config }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
  config: ProductConfig
}) {
  if (!active || !payload || payload.length === 0) return null

  const seriesConfig = getSeriesConfig(config)
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

        const formatted = key === 'index'
          ? item.value.toLocaleString(undefined, { maximumFractionDigits: 0 })
          : item.value.toFixed(2)

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


function ProductChart({
  data,
  config,
  selectedPeriod,
}: {
  data: JpxPcrItem[]
  config: ProductConfig
  selectedPeriod: PeriodValue
}) {
  const { hiddenSeries, handleLegendClick, isHidden } = useHiddenSeries<SeriesKey>()

  const chartData = useMemo(() => {
    const mapped = data.map((d) => ({
      date: d.date,
      vol_pcr: d[config.volKey] as number | null,
      oi_pcr: d[config.oiKey] as number | null,
      index: d[config.indexKey] as number | null,
    }))
    return mapped
  }, [data, config])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 2
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  // Latest values
  const latest = useMemo(() => {
    const withData = filteredData.filter((d) => d.vol_pcr != null)
    return withData.length > 0 ? withData[withData.length - 1] : null
  }, [filteredData])

  const seriesConfig = getSeriesConfig(config)

  return (
    <div>
      {/* Latest values */}
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
            const val = latest[key]
            if (val == null) return null
            const formatted = key === 'index'
              ? val.toLocaleString(undefined, { maximumFractionDigits: 0 })
              : val.toFixed(2)

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
                <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>{label}</Text>
                <Text
                  style={{ color, fontSize: 16, fontWeight: 700 }}
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

      {/* Chart - 3 Y-axes */}
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart
          data={filteredData}
          margin={{ top: 16, right: 60, bottom: 0, left: 0 }}
          style={{ backgroundColor: DARK_THEME.chartBg }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} horizontal={false} />

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

          {/* Left Y-axis: 取引高PCR */}
          <YAxis
            yAxisId="left"
            domain={['dataMin - 0.05', 'dataMax + 0.05']}
            tickFormatter={(v: number) => v.toFixed(1)}
            axisLine={{ stroke: COLOR_VOL_PCR }}
            tickLine={{ stroke: COLOR_VOL_PCR }}
            tick={{ fill: COLOR_VOL_PCR, fontSize: 11 }}
            tickMargin={8}
          />

          {/* Right Y-axis 1: 建玉PCR */}
          <YAxis
            yAxisId="right1"
            orientation="right"
            domain={['dataMin - 0.05', 'dataMax + 0.05']}
            tickFormatter={(v: number) => v.toFixed(1)}
            axisLine={{ stroke: COLOR_OI_PCR }}
            tickLine={{ stroke: COLOR_OI_PCR }}
            tick={{ fill: COLOR_OI_PCR, fontSize: 11 }}
            tickMargin={4}
            width={40}
          />

          {/* Right Y-axis 2: 株価指数 */}
          <YAxis
            yAxisId="right2"
            orientation="right"
            domain={['dataMin - 500', 'dataMax + 500']}
            tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}K` : `${v}`}
            axisLine={{ stroke: config.indexColor }}
            tickLine={{ stroke: config.indexColor }}
            tick={{ fill: config.indexColor, fontSize: 11 }}
            tickMargin={4}
            width={50}
          />

          <RechartsTooltip content={<CustomTooltip hiddenSeries={hiddenSeries} config={config} />} />

          <Legend
            wrapperStyle={{ paddingTop: 8 }}
            onClick={(e) => handleLegendClick(e.dataKey as string)}
            formatter={(value: string, entry) => (
              <span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : DARK_THEME.textPrimary }}>
                {value}
              </span>
            )}
          />

          <Line
            type="monotone"
            dataKey="vol_pcr"
            stroke={COLOR_VOL_PCR}
            strokeWidth={1.5}
            dot={false}
            name="取引高PCR"
            yAxisId="left"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('vol_pcr')}
          />
          <Line
            type="monotone"
            dataKey="oi_pcr"
            stroke={COLOR_OI_PCR}
            strokeWidth={1.5}
            dot={false}
            name="建玉PCR"
            yAxisId="right1"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('oi_pcr')}
          />
          <Line
            type="monotone"
            dataKey="index"
            stroke={config.indexColor}
            strokeWidth={1.5}
            dot={false}
            name={`${config.indexLabel}`}
            yAxisId="right2"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('index')}
          />

          {config.oiRefLines?.map(({ value, label }) => (
            <ReferenceLine
              key={`oi-ref-${value}`}
              yAxisId="right1"
              y={value}
              stroke="#c084fc"
              strokeDasharray="8 4"
              strokeWidth={1.5}
              strokeOpacity={0.8}
              label={{
                value: label,
                position: 'right',
                fill: '#c084fc',
                fontSize: 12,
                fontWeight: 600,
              }}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}


export default function JpxPcrChart() {
  const { data: apiData, isLoading, error } = useJpxPcrData()
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(1)
  const [productView, setProductView] = useState<ProductView>('nk225')

  const chartData = useMemo(() => {
    if (!apiData?.data) return []
    return [...apiData.data].sort((a, b) => a.date.localeCompare(b.date))
  }, [apiData])

  if (isLoading) {
    return (
      <ChartContainer title="日本株指数 Put/Call Ratio" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (error || !apiData || chartData.length === 0) {
    return (
      <ChartContainer title="日本株指数 Put/Call Ratio" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  return (
    <ChartContainer
      title="日本株指数 Put/Call Ratio"
      dataSource="JPX"
      sourceUrl="https://www.jpx.co.jp/markets/derivatives/trading-volume/index.html"
      showPeriodSelector={false}
      handbookId="jpx-pcr"
    >
      {/* ViewModeButtonGroup + データ比較ボタン (same row) */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <ViewModeButtonGroup options={PRODUCT_OPTIONS} currentMode={productView} onChange={setProductView} />
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            size="small"
            onClick={() => window.open('/compare?s=jpx_put_call_ratios', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* Period selector (standalone row) */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* Chart */}
      <ProductChart
        data={chartData}
        config={PRODUCT_CONFIGS[productView]}
        selectedPeriod={selectedPeriod}
      />
    </ChartContainer>
  )
}
