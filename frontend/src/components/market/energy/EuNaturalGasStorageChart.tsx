import { useState, useMemo } from 'react'
import { Tooltip, Button } from 'antd'
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
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS, CHART_MARGIN } from '../../country/usa/common/chartConstants'

const DARK_THEME = {
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  gridLine: '#475569',
  axisLine: '#64748b',
  tooltipBg: '#334155',
  tooltipBorder: '#475569',
  chartBg: '#1e293b',
}

const COLOR_STORAGE = '#22c55e'     // Green - gas in storage
const COLOR_FILL_RATE = '#3b82f6'   // Blue - fill rate
const COLOR_INJECTION = '#f59e0b'   // Amber - injection
const COLOR_WITHDRAWAL = '#ef4444'  // Red - withdrawal

interface StorageItem {
  date: string
  gas_in_storage: number | null
  fill_rate: number | null
  injection: number | null
  withdrawal: number | null
  working_gas_volume: number | null
  yoy: number | null
}

interface StorageResponse {
  data: StorageItem[]
  latest: StorageItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

type ViewMode = 'raw' | 'yoy'
const VIEW_MODE_OPTIONS = [
  { mode: 'raw' as ViewMode, label: '水準' },
  { mode: 'yoy' as ViewMode, label: '前年比' },
]

type SeriesKey = 'gas_in_storage' | 'fill_rate' | 'yoy'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ChartTooltip({ active, payload, label, hiddenSeries, viewMode }: {
  active?: boolean
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
  viewMode: ViewMode
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))
  const dp = payload[0]?.payload as StorageItem | undefined
  if (!dp) return null

  return (
    <div style={{
      backgroundColor: DARK_THEME.tooltipBg,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>{formattedLabel}</div>
      {viewMode === 'raw' ? (
        <>
          {!hiddenSeries.has('gas_in_storage') && dp.gas_in_storage != null && (
            <div style={{ color: COLOR_STORAGE, fontSize: 13, marginBottom: 3 }}>
              在庫量: {dp.gas_in_storage.toLocaleString(undefined, { maximumFractionDigits: 2 })} TWh
            </div>
          )}
        </>
      ) : (
        <>
          {!hiddenSeries.has('yoy') && dp.yoy != null && (
            <div style={{ color: COLOR_STORAGE, fontSize: 13, marginBottom: 3 }}>
              在庫量 YoY: {dp.yoy >= 0 ? '+' : ''}{dp.yoy.toFixed(2)}%
            </div>
          )}
        </>
      )}
      {!hiddenSeries.has('fill_rate') && dp.fill_rate != null && (
        <div style={{ color: COLOR_FILL_RATE, fontSize: 13, marginBottom: 3 }}>
          充填率: {dp.fill_rate.toFixed(2)}%
        </div>
      )}
      {dp.injection != null && (
        <div style={{ color: COLOR_INJECTION, fontSize: 13, marginBottom: 3 }}>
          注入量: {dp.injection.toLocaleString(undefined, { maximumFractionDigits: 2 })} GWh/d
        </div>
      )}
      {dp.withdrawal != null && (
        <div style={{ color: COLOR_WITHDRAWAL, fontSize: 13, marginBottom: 3 }}>
          引出量: {dp.withdrawal.toLocaleString(undefined, { maximumFractionDigits: 2 })} GWh/d
        </div>
      )}
    </div>
  )
}


export default function EuNaturalGasStorageChart() {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(5)
  const [viewMode, setViewMode] = useState<ViewMode>('raw')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<SeriesKey>()

  const { data: response } = useQuery<StorageResponse>({
    queryKey: ['eu-natural-gas-storage'],
    queryFn: async () => {
      const res = await axios.get('/api/market/eu-natural-gas-storage')
      return res.data
    },
    staleTime: 1000 * 60 * 30,
  })

  const filteredData = useMemo(() => {
    if (!response?.data?.length) return []
    if (currentPeriod === 'all') return response.data
    const years = typeof currentPeriod === 'number' ? currentPeriod : 5
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return response.data.filter(d => d.date >= cutoffStr)
  }, [response, currentPeriod])

  const latest = response?.latest

  return (
    <ChartContainer
      title="EU天然ガス貯蔵量"
      dataSource="AGSI+"
      sourceUrl="https://agsi.gie.eu/"
      showPeriodSelector={false}
    >
      {/* Latest value box */}
      <div style={LATEST_VALUE_BOX_STYLE}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          {latest?.date && (
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
              {latest.date.replace(/-/g, '/')}
            </span>
          )}
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>在庫量: </span>
            <span style={{ fontSize: 20, fontWeight: 'bold', color: COLOR_STORAGE }}>
              {latest?.gas_in_storage != null
                ? `${latest.gas_in_storage.toLocaleString(undefined, { maximumFractionDigits: 2 })} TWh`
                : '—'}
            </span>
          </div>
          {latest?.fill_rate != null && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>充填率: </span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLOR_FILL_RATE }}>
                {latest.fill_rate.toFixed(2)}%
              </span>
            </div>
          )}
          {latest?.injection != null && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>注入: </span>
              <span style={{ fontSize: 14, fontWeight: 'bold', color: COLOR_INJECTION }}>
                {latest.injection.toLocaleString(undefined, { maximumFractionDigits: 1 })} GWh/d
              </span>
            </div>
          )}
          {latest?.withdrawal != null && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>引出: </span>
              <span style={{ fontSize: 14, fontWeight: 'bold', color: COLOR_WITHDRAWAL }}>
                {latest.withdrawal.toLocaleString(undefined, { maximumFractionDigits: 1 })} GWh/d
              </span>
            </div>
          )}
          {latest?.yoy != null && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>YoY: </span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: latest.yoy >= 0 ? '#22c55e' : '#ef4444' }}>
                {latest.yoy >= 0 ? '+' : ''}{latest.yoy.toFixed(2)}%
              </span>
            </div>
          )}
        </div>
      </div>

      {/* ViewMode + データ比較ボタン */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <ViewModeButtonGroup
          options={VIEW_MODE_OPTIONS}
          currentMode={viewMode}
          onChange={(m) => setViewMode(m as ViewMode)}
        />
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            onClick={() => window.open('/compare?s=eu_natural_gas_storage', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* PeriodSelector */}
      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

      {/* 水準チャート */}
      {viewMode === 'raw' && (
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis
              dataKey="date"
              tickFormatter={(v) => formatDayLabel(v)}
              stroke={DARK_THEME.axisLine}
              tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
              minTickGap={40}
            />
            <YAxis
              yAxisId="left"
              domain={['dataMin * 0.85', 'dataMax * 1.05']}
              tickFormatter={(v: number) => `${v.toFixed(0)}`}
              stroke={COLOR_STORAGE}
              tick={{ fill: COLOR_STORAGE, fontSize: 11 }}
              width={55}
              // label={{ value: 'TWh', position: 'insideTopLeft', fill: COLOR_STORAGE, fontSize: 10, offset: -5 }}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              domain={[0, 100]}
              tickFormatter={(v: number) => `${v.toFixed(0)}%`}
              stroke={COLOR_FILL_RATE}
              tick={{ fill: COLOR_FILL_RATE, fontSize: 10 }}
              width={50}
              axisLine={{ stroke: COLOR_FILL_RATE, strokeDasharray: '4 3' }}
            />
            <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} viewMode={viewMode} />} />
            <Legend
              onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)}
              wrapperStyle={{ cursor: 'pointer' }}
              formatter={(value: string, entry: any) => (
                <span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>
              )}
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="gas_in_storage"
              name="在庫量 (TWh)"
              stroke={COLOR_STORAGE}
              strokeWidth={2}
              dot={false}
              hide={hiddenSeries.has('gas_in_storage')}
              connectNulls
              isAnimationActive={false}
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="fill_rate"
              name="充填率 (%)"
              stroke={COLOR_FILL_RATE}
              strokeWidth={1.5}
              strokeDasharray="4 3"
              dot={false}
              hide={hiddenSeries.has('fill_rate')}
              connectNulls
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* 前年比チャート */}
      {viewMode === 'yoy' && (
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
            <XAxis
              dataKey="date"
              tickFormatter={(v) => formatDayLabel(v)}
              stroke={DARK_THEME.axisLine}
              tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
              minTickGap={40}
            />
            <YAxis
              yAxisId="left"
              domain={['auto', 'auto']}
              tickFormatter={(v: number) => `${v.toFixed(1)}%`}
              stroke={COLOR_STORAGE}
              tick={{ fill: COLOR_STORAGE, fontSize: 11 }}
              width={55}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              domain={[0, 100]}
              tickFormatter={(v: number) => `${v.toFixed(0)}%`}
              stroke={COLOR_FILL_RATE}
              tick={{ fill: COLOR_FILL_RATE, fontSize: 10 }}
              width={50}
              axisLine={{ stroke: COLOR_FILL_RATE, strokeDasharray: '4 3' }}
            />
            <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} viewMode={viewMode} />} />
            <ReferenceLine yAxisId="left" y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />
            <Legend
              onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)}
              wrapperStyle={{ cursor: 'pointer' }}
              formatter={(value: string, entry: any) => (
                <span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>
              )}
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="yoy"
              name="在庫量 YoY %"
              stroke={COLOR_STORAGE}
              strokeWidth={2}
              dot={false}
              hide={hiddenSeries.has('yoy')}
              connectNulls
              isAnimationActive={false}
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="fill_rate"
              name="充填率 (%)"
              stroke={COLOR_FILL_RATE}
              strokeWidth={1.5}
              strokeDasharray="4 3"
              dot={false}
              hide={hiddenSeries.has('fill_rate')}
              connectNulls
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </ChartContainer>
  )
}
