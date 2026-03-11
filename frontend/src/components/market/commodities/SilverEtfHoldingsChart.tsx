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
import { formatDayLabel } from '../../../utils/dateFormatters'
import { useHiddenSeries } from '../../country/usa/common/useChartData'
import { useMarketBatchData } from '../../../hooks/useMarketData'

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

const COLOR_HOLDINGS = '#94a3b8'   // 銀ETF残高 - silver gray
const COLOR_SILVER_PRICE = '#f59e0b' // 銀価格 - amber/gold (dashed)

interface SilverEtfItem {
  date: string
  silver_tons: number | null
  shares_outstanding: number | null
}

interface SilverEtfResponse {
  data: SilverEtfItem[]
  latest: SilverEtfItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

interface MergedItem {
  date: string
  silver_tons: number | null
  silver_price: number | null
}

type SeriesKey = 'silver_tons' | 'silver_price'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ChartTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))
  const dp = payload[0]?.payload as MergedItem | undefined
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
      {!hiddenSeries.has('silver_tons') && dp.silver_tons != null && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
          <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: DARK_THEME.textPrimary }}>
            <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: COLOR_HOLDINGS, marginRight: 6 }} />
            銀ETF残高
          </span>
          <span style={{ fontWeight: 500, color: COLOR_HOLDINGS }}>
            {dp.silver_tons.toLocaleString(undefined, { maximumFractionDigits: 1 })} トン
          </span>
        </div>
      )}
      {!hiddenSeries.has('silver_price') && dp.silver_price != null && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
          <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: DARK_THEME.textPrimary }}>
            <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: COLOR_SILVER_PRICE, marginRight: 6 }} />
            銀価格
          </span>
          <span style={{ fontWeight: 500, color: COLOR_SILVER_PRICE }}>
            ${dp.silver_price.toLocaleString(undefined, { maximumFractionDigits: 2 })} /oz
          </span>
        </div>
      )}
    </div>
  )
}


export default function SilverEtfHoldingsChart() {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(2)
  const { hiddenSeries, handleLegendClick, isHidden } = useHiddenSeries<SeriesKey>()

  const { data: response, isLoading } = useQuery<SilverEtfResponse>({
    queryKey: ['market', 'silver-etf-holdings'],
    queryFn: async () => {
      const res = await axios.get('/api/market/silver-etf-holdings')
      return res.data
    },
    staleTime: 1000 * 60 * 30,
    refetchOnMount: false,
  })

  // 銀価格（yfinance日足）
  const { data: marketData } = useMarketBatchData(['silver'])

  const mergedData = useMemo(() => {
    if (!response?.data) return []

    // 銀価格を日付でマップ
    const silverPriceMap = new Map<string, number>()
    if (marketData?.silver?.data) {
      for (const d of marketData.silver.data) {
        silverPriceMap.set(d.date, d.close)
      }
    }

    return response.data.map(item => ({
      date: item.date,
      silver_tons: item.silver_tons,
      silver_price: silverPriceMap.get(item.date) ?? null,
    }))
  }, [response, marketData])

  const filteredData = useMemo(() => {
    if (!mergedData.length) return []
    if (selectedPeriod === 'all') return mergedData
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 2
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return mergedData.filter(d => d.date >= cutoffStr)
  }, [mergedData, selectedPeriod])

  const latest = response?.latest ?? null

  // 銀価格最新値（yfinance日足の最新）
  const silverPriceDisplay = useMemo(() => {
    if (marketData?.silver?.data?.length) {
      const lastItem = marketData.silver.data[marketData.silver.data.length - 1]
      return { value: lastItem.close, date: lastItem.date }
    }
    return null
  }, [marketData])

  if (isLoading) {
    return (
      <ChartContainer title="銀ETF残高保有量" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (!response?.data?.length) {
    return (
      <ChartContainer title="銀ETF残高保有量" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  return (
    <ChartContainer
      title="銀ETF残高保有量"
      dataSource="BlackRock (iShares Silver Trust)"
      showPeriodSelector={false}
      sourceUrl="https://www.blackrock.com/jp/individual/ja/products/239855/ishares-silver-trust-fund"
    >
      {/* 1. Latest values */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        marginBottom: 12,
        padding: '10px 14px',
        background: DARK_THEME.bgTertiary,
        borderRadius: 8,
        flexWrap: 'wrap',
      }}>
        {latest?.silver_tons != null && (
          <div
            style={{ display: 'flex', alignItems: 'baseline', gap: 6, opacity: isHidden('silver_tons') ? 0.3 : 1, cursor: 'pointer' }}
            onClick={() => handleLegendClick('silver_tons')}
          >
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>銀ETF残高</Text>
            <Text style={{ color: COLOR_HOLDINGS, fontSize: 15, fontWeight: 700 }} className="tabular-nums">
              {latest.silver_tons.toLocaleString(undefined, { maximumFractionDigits: 1 })} トン
            </Text>
          </div>
        )}
        {silverPriceDisplay && (
          <div
            style={{ display: 'flex', alignItems: 'baseline', gap: 6, opacity: isHidden('silver_price') ? 0.3 : 1, cursor: 'pointer' }}
            onClick={() => handleLegendClick('silver_price')}
          >
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>銀価格</Text>
            <Text style={{ color: COLOR_SILVER_PRICE, fontSize: 15, fontWeight: 700 }} className="tabular-nums">
              ${silverPriceDisplay.value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </Text>
            {silverPriceDisplay.date !== latest?.date && (
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 10 }}>({silverPriceDisplay.date})</Text>
            )}
          </div>
        )}
        {latest?.date && (
          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>({latest.date})</Text>
        )}
      </div>

      {/* 2. Compare button */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            size="small"
            onClick={() => window.open('/compare?s=silver_etf_holdings', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 3. Period selector */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* 4. Chart */}
      <ResponsiveContainer width="100%" height={420}>
        <ComposedChart
          data={filteredData}
          margin={{ top: 16, right: 60, bottom: 0, left: 0 }}
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

          {/* Left Y: トン */}
          <YAxis
            yAxisId="left"
            domain={['dataMin - 100', 'dataMax + 100']}
            tickFormatter={(v: number) => `${v.toLocaleString()}`}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            tickMargin={8}
            label={{ value: 'トン', position: 'top', offset: 8, style: { fill: DARK_THEME.textSecondary, fontSize: 10 } }}
          />

          {/* Right Y: USD/oz */}
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={['dataMin * 0.9', 'dataMax * 1.05']}
            tickFormatter={(v: number) => `$${v.toFixed(0)}`}
            axisLine={{ stroke: COLOR_SILVER_PRICE }}
            tickLine={{ stroke: COLOR_SILVER_PRICE }}
            tick={{ fill: COLOR_SILVER_PRICE, fontSize: 11 }}
            tickMargin={4}
            width={55}
          />

          <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} />} />

          <Legend
            wrapperStyle={{ paddingTop: 8 }}
            onClick={(e) => handleLegendClick(e.dataKey as string)}
            formatter={(value: string, entry) => (
              <span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : DARK_THEME.textPrimary }}>
                {value}
              </span>
            )}
          />

          {/* Silver ETF Holdings line */}
          <Line
            type="monotone"
            dataKey="silver_tons"
            stroke={COLOR_HOLDINGS}
            strokeWidth={2}
            dot={false}
            name="銀ETF残高 (トン)"
            yAxisId="left"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('silver_tons')}
          />

          {/* Silver Price line */}
          <Line
            type="monotone"
            dataKey="silver_price"
            stroke={COLOR_SILVER_PRICE}
            strokeWidth={1.5}
            strokeDasharray="6 3"
            dot={false}
            name="銀価格 (USD/oz)"
            yAxisId="right"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('silver_price')}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
