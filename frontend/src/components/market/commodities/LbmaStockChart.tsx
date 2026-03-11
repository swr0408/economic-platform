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
} from 'recharts'
import ChartContainer from '../../common/ChartContainer'
import PeriodSelector, { type PeriodValue } from '../../common/PeriodSelector'
import { formatMonthLabel } from '../../../utils/dateFormatters'
import { useHiddenSeries } from '../../country/usa/common/useChartData'
import { ViewModeButtonGroup } from '../../country/usa/common/ChartComponents'
import { useMarketBatchData } from '../../../hooks/useMarketData'
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../../country/usa/common/chartConstants'

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

const COLOR_GOLD_STOCK = '#f59e0b'
const COLOR_SILVER_STOCK = '#94a3b8'
const COLOR_GOLD_PRICE = '#d97706'
const COLOR_SILVER_PRICE = '#64748b'

interface LbmaItem {
  date: string
  gold_thousands_oz: number | null
  silver_thousands_oz: number | null
}

interface LbmaResponse {
  data: LbmaItem[]
  latest: LbmaItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

interface MergedItem {
  date: string
  gold_thousands_oz: number | null
  silver_thousands_oz: number | null
  gold_price: number | null
  silver_price: number | null
}

type ViewMode = 'gold' | 'silver'
const VIEW_MODE_OPTIONS = [
  { mode: 'gold' as ViewMode, label: '金' },
  { mode: 'silver' as ViewMode, label: '銀' },
]

type SeriesKey = 'gold_thousands_oz' | 'silver_thousands_oz' | 'gold_price' | 'silver_price'

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
  const dp = payload[0]?.payload as MergedItem | undefined
  if (!dp) return null

  const stockKey = viewMode === 'gold' ? 'gold_thousands_oz' : 'silver_thousands_oz'
  const priceKey = viewMode === 'gold' ? 'gold_price' : 'silver_price'
  const stockColor = viewMode === 'gold' ? COLOR_GOLD_STOCK : COLOR_SILVER_STOCK
  const priceColor = viewMode === 'gold' ? COLOR_GOLD_PRICE : COLOR_SILVER_PRICE
  const label1 = viewMode === 'gold' ? '金在庫' : '銀在庫'
  const label2 = viewMode === 'gold' ? '金価格' : '銀価格'

  return (
    <div style={{
      backgroundColor: DARK_THEME.tooltipBg,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>{formattedLabel}</div>
      {!hiddenSeries.has(stockKey) && dp[stockKey] != null && (
        <div style={{ color: stockColor, fontSize: 13, marginBottom: 3 }}>
          {label1}: {dp[stockKey]!.toLocaleString()} 千oz
        </div>
      )}
      {!hiddenSeries.has(priceKey) && dp[priceKey] != null && (
        <div style={{ color: priceColor, fontSize: 13, marginBottom: 3 }}>
          {label2}: ${dp[priceKey]!.toLocaleString(undefined, { maximumFractionDigits: viewMode === 'silver' ? 2 : 0 })} /oz
        </div>
      )}
    </div>
  )
}

export default function LbmaStockChart() {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(5)
  const [viewMode, setViewMode] = useState<ViewMode>('gold')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<SeriesKey>()

  const { data: response } = useQuery<LbmaResponse>({
    queryKey: ['lbma-stock'],
    queryFn: async () => {
      const res = await axios.get('/api/market/lbma-stock')
      return res.data
    },
    staleTime: 1000 * 60 * 30,
  })

  const { data: marketData } = useMarketBatchData(['gold', 'silver'])

  const mergedData = useMemo(() => {
    if (!response?.data) return []

    const goldMonthMap = new Map<string, number>()
    const silverMonthMap = new Map<string, number>()
    if (marketData?.gold?.data) {
      for (const d of marketData.gold.data) {
        goldMonthMap.set(d.date.slice(0, 7), d.close)
      }
    }
    if (marketData?.silver?.data) {
      for (const d of marketData.silver.data) {
        silverMonthMap.set(d.date.slice(0, 7), d.close)
      }
    }

    return response.data.map(item => ({
      date: item.date,
      gold_thousands_oz: item.gold_thousands_oz,
      silver_thousands_oz: item.silver_thousands_oz,
      gold_price: goldMonthMap.get(item.date.slice(0, 7)) ?? null,
      silver_price: silverMonthMap.get(item.date.slice(0, 7)) ?? null,
    }))
  }, [response, marketData])

  const filteredData = useMemo(() => {
    if (!mergedData.length) return []
    if (currentPeriod === 'all') return mergedData
    const years = typeof currentPeriod === 'number' ? currentPeriod : 5
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 7)
    return mergedData.filter(d => d.date >= cutoffStr)
  }, [mergedData, currentPeriod])

  const latest = response?.latest

  // Current mode config
  const stockKey: SeriesKey = viewMode === 'gold' ? 'gold_thousands_oz' : 'silver_thousands_oz'
  const priceKey: SeriesKey = viewMode === 'gold' ? 'gold_price' : 'silver_price'
  const stockColor = viewMode === 'gold' ? COLOR_GOLD_STOCK : COLOR_SILVER_STOCK
  const priceColor = viewMode === 'gold' ? COLOR_GOLD_PRICE : COLOR_SILVER_PRICE
  const stockLabel = viewMode === 'gold' ? '金在庫 (千oz)' : '銀在庫 (千oz)'
  const priceLabel = viewMode === 'gold' ? '金価格 (USD/oz)' : '銀価格 (USD/oz)'
  const yAxisLabel = '千oz'
  const priceFormatter = viewMode === 'silver'
    ? (v: number) => `$${v.toFixed(0)}`
    : (v: number) => `$${v.toFixed(0)}`

  return (
    <ChartContainer
      title="LBMA在庫（ロンドン金庫）"
      dataSource="LBMA"
      sourceUrl="https://www.lbma.org.uk/prices-and-data/london-vault-data"
      showPeriodSelector={false}
    >
      {/* Latest value box */}
      <div style={LATEST_VALUE_BOX_STYLE}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          {latest?.date && (
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
              {latest.date}
            </span>
          )}
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>金: </span>
            <span style={{ fontSize: 20, fontWeight: 'bold', color: COLOR_GOLD_STOCK }}>
              {latest?.gold_thousands_oz != null ? `${latest.gold_thousands_oz.toLocaleString()} 千oz` : '—'}
            </span>
          </div>
          {latest?.silver_thousands_oz != null && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>銀: </span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLOR_SILVER_STOCK }}>
                {latest.silver_thousands_oz.toLocaleString()} 千oz
              </span>
            </div>
          )}
        </div>
        <Tooltip title="比較ページを開く">
          <Button
            size="small"
            icon={<AreaChartOutlined />}
            onClick={() => window.open('/compare?s=lbma_stock', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* ViewMode + Period selector */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <ViewModeButtonGroup
          options={VIEW_MODE_OPTIONS}
          currentMode={viewMode}
          onChange={(m) => setViewMode(m as ViewMode)}
        />
      </div>
      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

      {/* Chart */}
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart data={filteredData} margin={{ top: 10, right: 60, left: 10, bottom: 0 }}>
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
            domain={['dataMin * 0.95', 'dataMax * 1.05']}
            tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}M` : `${v.toFixed(0)}`}
            stroke={DARK_THEME.axisLine}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            width={55}
            label={{ value: yAxisLabel, angle: -90, position: 'insideLeft', fill: DARK_THEME.textSecondary, fontSize: 11 }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={['dataMin * 0.9', 'dataMax * 1.05']}
            tickFormatter={priceFormatter}
            stroke={priceColor}
            tick={{ fill: priceColor, fontSize: 10 }}
            width={55}
            axisLine={{ stroke: priceColor, strokeDasharray: '4 3' }}
          />
          <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} viewMode={viewMode} />} />
          <Legend
            onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)}
            wrapperStyle={{ cursor: 'pointer' }}
            formatter={(value: string, entry: any) => (
              <span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>
                {value}
              </span>
            )}
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey={stockKey}
            name={stockLabel}
            stroke={stockColor}
            strokeWidth={2}
            dot={false}
            hide={hiddenSeries.has(stockKey)}
            connectNulls
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey={priceKey}
            name={priceLabel}
            stroke={priceColor}
            strokeWidth={1.5}
            strokeDasharray="4 3"
            dot={false}
            hide={hiddenSeries.has(priceKey)}
            connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
