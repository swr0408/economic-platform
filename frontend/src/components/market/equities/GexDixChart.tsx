import { useState, useMemo } from 'react'
import { Typography, Tooltip, Button } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import {
  ComposedChart,
  Line,
  Bar,
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
import { formatMonthLabel, formatDayLabel } from '../../../utils/dateFormatters'

const { Text } = Typography

// ダークテーマ
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

// チャートカラー
const PRICE_COLOR = '#3b82f6'    // S&P 500 — 青（左Y軸）
const DIX_COLOR = '#10b981'      // DIX — 緑（右Y軸①）
const GEX_COLOR = '#f59e0b'      // GEX — 黄（棒グラフ）

// API レスポンス型
interface GexDixItem {
  date: string
  price: number
  dix: number
  gex: number
}

interface GexDixResponse {
  data: GexDixItem[]
  latest: GexDixItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

function useGexDixData() {
  return useQuery({
    queryKey: ['market', 'gex-dix'],
    queryFn: async () => {
      const { data } = await axios.get<GexDixResponse>('/api/market/gex-dix')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

// カスタムツールチップ
function CustomTooltip({ active, payload, label }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
}) {
  if (!active || !payload || payload.length === 0) return null

  const formattedLabel = formatDayLabel(String(label))
  const priceItem = payload.find((p: { dataKey: string }) => p.dataKey === 'price')
  const dixItem = payload.find((p: { dataKey: string }) => p.dataKey === 'dix')
  const gexItem = payload.find((p: { dataKey: string }) => p.dataKey === 'gex')

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

      {priceItem && typeof priceItem.value === 'number' && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
          <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
            <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: PRICE_COLOR, marginRight: 6 }} />
            S&P 500
          </span>
          <span style={{ fontWeight: 500, color: PRICE_COLOR }}>
            {priceItem.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </span>
        </div>
      )}

      {dixItem && typeof dixItem.value === 'number' && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
          <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
            <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: DIX_COLOR, marginRight: 6 }} />
            DIX
          </span>
          <span style={{ fontWeight: 500, color: DIX_COLOR }}>
            {dixItem.value.toFixed(1)}%
          </span>
        </div>
      )}

      {gexItem && typeof gexItem.value === 'number' && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
          <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
            <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: GEX_COLOR, marginRight: 6 }} />
            GEX
          </span>
          <span style={{ fontWeight: 500, color: GEX_COLOR }}>
            {gexItem.value.toFixed(2)}B
          </span>
        </div>
      )}
    </div>
  )
}

export default function GexDixChart() {
  const { data: apiData, isLoading } = useGexDixData()
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(2)

  const chartData = useMemo(() => {
    if (!apiData?.data) return []
    return apiData.data
      .map((d) => ({
        date: d.date,
        price: d.price,
        dix: d.dix,
        gex: d.gex,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [apiData])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    if (selectedPeriod === 'default') {
      // デフォルト: 1年
      const cutoff = new Date()
      cutoff.setFullYear(cutoff.getFullYear() - 1)
      const cutoffStr = cutoff.toISOString().slice(0, 10)
      return chartData.filter((d) => d.date >= cutoffStr)
    }
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 1
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  if (isLoading) {
    return (
      <ChartContainer title="GEX / DIX" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (!apiData || chartData.length === 0) {
    return (
      <ChartContainer title="GEX / DIX" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = apiData.latest

  return (
    <ChartContainer
      title="GEX / DIX"
      dataSource="SqueezeMetrics"
      sourceUrl="https://squeezemetrics.com/monitor"
      showPeriodSelector={false}
    >
      {/* 最新値表示 */}
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
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>S&P 500</Text>
            <Text
              style={{ color: PRICE_COLOR, fontSize: 18, fontWeight: 700 }}
              className="tabular-nums"
            >
              {latest.price.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </Text>
          </div>

          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>DIX</Text>
            <Text
              style={{ color: DIX_COLOR, fontSize: 18, fontWeight: 700 }}
              className="tabular-nums"
            >
              {latest.dix.toFixed(1)}%
            </Text>
          </div>

          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>GEX</Text>
            <Text
              style={{ color: GEX_COLOR, fontSize: 18, fontWeight: 700 }}
              className="tabular-nums"
            >
              {latest.gex.toFixed(2)}B
            </Text>
          </div>

          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>
            ({latest.date})
          </Text>
        </div>
      )}

      {/* データ比較ボタン */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            size="small"
            onClick={() => window.open('/compare?s=gex&s=dix', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 期間選択 */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* チャート — 3軸: price(左), DIX(右①), GEX(棒グラフ・右②) */}
      <ResponsiveContainer width="100%" height={450}>
        <ComposedChart
          data={filteredData}
          margin={{ top: 16, right: 45, bottom: 0, left: 0 }}
          style={{ backgroundColor: DARK_THEME.chartBg }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />

          {/* GEX=0の基準線 */}
          <ReferenceLine yAxisId="gex" y={0} stroke="#94a3b8" strokeDasharray="6 3" strokeWidth={0.8} />

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

          {/* 左Y軸: S&P 500 価格 */}
          <YAxis
            yAxisId="price"
            domain={['dataMin', 'dataMax']}
            tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}K` : `${v}`}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: PRICE_COLOR, fontSize: 11 }}
            tickMargin={8}
            label={{ value: 'S&P 500', angle: -90, position: 'insideLeft', offset: -8, fill: PRICE_COLOR, fontSize: 11 }}
          />

          {/* 右Y軸①: DIX (%) */}
          <YAxis
            yAxisId="dix"
            orientation="right"
            domain={['dataMin - 2', 'dataMax + 2']}
            tickFormatter={(v: number) => `${v.toFixed(0)}%`}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: DIX_COLOR, fontSize: 10 }}
            tickMargin={4}
            width={35}
          />

          {/* 右Y軸②: GEX (Bn USD) */}
          <YAxis
            yAxisId="gex"
            orientation="right"
            domain={['dataMin - 1', 'dataMax + 1']}
            tickFormatter={(v: number) => `${v.toFixed(0)}B`}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: GEX_COLOR, fontSize: 10 }}
            tickMargin={4}
            width={35}
          />

          <RechartsTooltip content={<CustomTooltip />} />

          <Legend wrapperStyle={{ paddingTop: 8 }} />

          {/* GEX: 棒グラフ（背景として描画） */}
          <Bar
            dataKey="gex"
            fill={GEX_COLOR}
            fillOpacity={0.3}
            stroke={GEX_COLOR}
            strokeOpacity={0.5}
            name="GEX (Bn)"
            yAxisId="gex"
            isAnimationActive={false}
          />

          {/* S&P 500: 線グラフ */}
          <Line
            type="monotone"
            dataKey="price"
            stroke={PRICE_COLOR}
            strokeWidth={1.5}
            dot={false}
            name="S&P 500"
            yAxisId="price"
            connectNulls
            isAnimationActive={false}
          />

          {/* DIX: 線グラフ */}
          <Line
            type="monotone"
            dataKey="dix"
            stroke={DIX_COLOR}
            strokeWidth={1.5}
            dot={false}
            name="DIX (%)"
            yAxisId="dix"
            connectNulls
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
