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
import { formatMonthLabel } from '../../../utils/dateFormatters'
import { useHiddenSeries } from '../../country/usa/common/useChartData'
import { ViewModeButtonGroup } from '../../country/usa/common/ChartComponents'
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS, CHART_MARGIN } from '../../country/usa/common/chartConstants'

const DARK_THEME = {
  textSecondary: '#94a3b8',
  gridLine: '#475569',
  axisLine: '#64748b',
  tooltipBg: '#334155',
  tooltipBorder: '#475569',
  chartBg: '#1e293b',
  textPrimary: '#f1f5f9',
}

const COLOR_PRODUCTION = '#8b5cf6' // Purple - production volume

interface ProductionItem {
  date: string
  value: number | null
  yoy: number | null
}

interface ProductionResponse {
  data: ProductionItem[]
  latest: ProductionItem | null
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

type SeriesKey = 'value' | 'yoy'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ChartTooltip({ active, payload, label, hiddenSeries, viewMode }: {
  active?: boolean
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
  viewMode: ViewMode
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatMonthLabel(String(label))
  const dp = payload[0]?.payload as ProductionItem | undefined
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
          {!hiddenSeries.has('value') && dp.value != null && (
            <div style={{ color: COLOR_PRODUCTION, fontSize: 13, marginBottom: 3 }}>
              生産量: {dp.value.toLocaleString(undefined, { maximumFractionDigits: 3 })} 百万m³
            </div>
          )}
        </>
      ) : (
        <>
          {!hiddenSeries.has('yoy') && dp.yoy != null && (
            <div style={{ color: COLOR_PRODUCTION, fontSize: 13, marginBottom: 3 }}>
              生産量 YoY: {dp.yoy >= 0 ? '+' : ''}{dp.yoy.toFixed(2)}%
            </div>
          )}
        </>
      )}
    </div>
  )
}


export default function EuNaturalGasProductionChart() {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)
  const [viewMode, setViewMode] = useState<ViewMode>('raw')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<SeriesKey>()

  const { data: response } = useQuery<ProductionResponse>({
    queryKey: ['eu-natural-gas-production'],
    queryFn: async () => {
      const res = await axios.get('/api/market/eu-natural-gas-production')
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
      title="EU天然ガス生産"
      dataSource="Eurostat"
      sourceUrl="https://ec.europa.eu/eurostat/statistics-explained/index.php?oldid=562286&title=Natural_gas_supply_statistics"
      showPeriodSelector={false}
    >
      {/* Latest value box */}
      <div style={LATEST_VALUE_BOX_STYLE}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          {latest?.date && (
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
              {latest.date.replace(/-/g, '/').replace(/\/01$/, '')}
            </span>
          )}
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>生産量: </span>
            <span style={{ fontSize: 20, fontWeight: 'bold', color: COLOR_PRODUCTION }}>
              {latest?.value != null
                ? `${latest.value.toLocaleString(undefined, { maximumFractionDigits: 3 })} 百万m³`
                : '—'}
            </span>
          </div>
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
            onClick={() => window.open('/compare?s=eu_natural_gas_production', '_blank')}
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
              tickFormatter={(v) => formatMonthLabel(v)}
              stroke={DARK_THEME.axisLine}
              tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
              minTickGap={40}
            />
            <YAxis
              yAxisId="left"
              domain={['dataMin * 0.85', 'dataMax * 1.05']}
              tickFormatter={(v: number) => `${v.toFixed(0)}`}
              stroke={COLOR_PRODUCTION}
              tick={{ fill: COLOR_PRODUCTION, fontSize: 11 }}
              width={55}
              // label={{ value: '百万m³', position: 'insideTopLeft', fill: COLOR_PRODUCTION, fontSize: 10, offset: -5 }}
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
              dataKey="value"
              name="生産量 (百万m³)"
              stroke={COLOR_PRODUCTION}
              strokeWidth={2}
              dot={false}
              hide={hiddenSeries.has('value')}
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
              tickFormatter={(v) => formatMonthLabel(v)}
              stroke={DARK_THEME.axisLine}
              tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
              minTickGap={40}
            />
            <YAxis
              yAxisId="left"
              domain={['dataMin - 2', 'dataMax + 2']}
              tickFormatter={(v: number) => `${v.toFixed(1)}%`}
              stroke={COLOR_PRODUCTION}
              tick={{ fill: COLOR_PRODUCTION, fontSize: 11 }}
              width={55}
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
              name="生産量 YoY %"
              stroke={COLOR_PRODUCTION}
              strokeWidth={2}
              dot={false}
              hide={hiddenSeries.has('yoy')}
              connectNulls
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </ChartContainer>
  )
}
