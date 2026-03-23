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
import { formatMonthLabel } from '../../../utils/dateFormatters'
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

const COLOR_BALANCE = '#22c55e'
const COLOR_BALANCE_3MA = '#f59e0b'
const COLOR_NIKKEI_YOY = '#ef4444'
const COLOR_NIKKEI = '#3b82f6'

interface ElecBalanceItem {
  date: string
  balance: number | null
  balance_3ma: number | null
  nikkei_yoy: number | null
  nikkei: number | null
  preliminary?: boolean
}

interface ElecBalanceResponse {
  data: ElecBalanceItem[]
  latest: ElecBalanceItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

function useElecBalanceData() {
  return useQuery({
    queryKey: ['market', 'electronic-components-balance'],
    queryFn: async () => {
      const { data } = await axios.get<ElecBalanceResponse>('/api/market/electronic-components-balance')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

type SeriesKey = 'balance' | 'balance_3ma' | 'nikkei_yoy' | 'nikkei'

const SERIES_CONFIG: { key: SeriesKey; label: string; color: string }[] = [
  { key: 'balance', label: '出荷在庫バランス', color: COLOR_BALANCE },
  { key: 'balance_3ma', label: '3ヶ月移動平均', color: COLOR_BALANCE_3MA },
  { key: 'nikkei_yoy', label: '日経平均(前年比)', color: COLOR_NIKKEI_YOY },
  { key: 'nikkei', label: '日経平均', color: COLOR_NIKKEI },
]

function CustomTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null

  const formattedLabel = formatMonthLabel(String(label))

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

      {SERIES_CONFIG.map(({ key, label: seriesLabel, color }) => {
        if (hiddenSeries.has(key)) return null
        const item = payload.find((p: { dataKey: string }) => p.dataKey === key)
        if (!item || typeof item.value !== 'number') return null

        const isPercent = key !== 'nikkei'
        const formatted = isPercent
          ? `${item.value.toFixed(2)}%`
          : item.value.toLocaleString(undefined, { maximumFractionDigits: 0 })

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

export default function ElectronicComponentsBalanceChart() {
  const { data: apiData, isLoading, error } = useElecBalanceData()
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(10)
  const { hiddenSeries, handleLegendClick, isHidden } = useHiddenSeries<SeriesKey>(['nikkei'])

  const chartData = useMemo(() => {
    if (!apiData?.data) return []
    return apiData.data
      .map((d) => ({
        date: d.date,
        balance: d.balance,
        balance_3ma: d.balance_3ma,
        nikkei_yoy: d.nikkei_yoy,
        nikkei: d.nikkei,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [apiData])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    if (selectedPeriod === 'default') {
      const cutoff = new Date()
      cutoff.setFullYear(cutoff.getFullYear() - 5)
      const cutoffStr = cutoff.toISOString().slice(0, 10)
      return chartData.filter((d) => d.date >= cutoffStr)
    }
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 5
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  if (isLoading) {
    return (
      <ChartContainer title="電子部品・デバイス工業 出荷在庫バランス" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (error || !apiData || chartData.length === 0) {
    return (
      <ChartContainer title="電子部品・デバイス工業 出荷在庫バランス" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = apiData.latest

  return (
    <ChartContainer
      title="電子部品・デバイス工業 出荷在庫バランス"
      dataSource="経済産業省 / yfinance"
      sourceUrl="https://www.meti.go.jp/statistics/tyo/iip/index.html"
      showPeriodSelector={false}
      handbookId="nikkei-225"
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
          {SERIES_CONFIG.map(({ key, label, color }) => {
            const val = latest[key]
            if (val == null) return null
            const isPercent = key !== 'nikkei'
            const formatted = isPercent
              ? `${val.toFixed(2)}%`
              : val.toLocaleString(undefined, { maximumFractionDigits: 0 })

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
            ({latest.date}){latest.preliminary && <span style={{ color: '#f59e0b', marginLeft: 4 }}>速報</span>}
          </Text>
        </div>
      )}

      {/* データ比較ボタン */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            size="small"
            onClick={() => window.open('/compare?s=electronic_components_balance', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 期間選択 */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* チャート */}
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart
          data={filteredData}
          margin={{ top: 16, right: 16, bottom: 0, left: 0 }}
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

          {/* 左Y軸: バランス (%) */}
          <YAxis
            yAxisId="left"
            tickFormatter={(v: number) => `${v.toFixed(0)}%`}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            tickMargin={8}
          />

          {/* 右Y軸①: 日経平均 前年比 (%) */}
          <YAxis
            yAxisId="right1"
            orientation="right"
            tickFormatter={(v: number) => `${v.toFixed(0)}%`}
            axisLine={{ stroke: COLOR_NIKKEI_YOY }}
            tickLine={{ stroke: COLOR_NIKKEI_YOY }}
            tick={{ fill: COLOR_NIKKEI_YOY, fontSize: 11 }}
            tickMargin={4}
            width={45}
          />

          {/* 右Y軸②: 日経平均 (水準) */}
          <YAxis
            yAxisId="right2"
            orientation="right"
            domain={['dataMin - 2000', 'dataMax + 2000']}
            tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}K` : `${v}`}
            axisLine={{ stroke: COLOR_NIKKEI }}
            tickLine={{ stroke: COLOR_NIKKEI }}
            tick={{ fill: COLOR_NIKKEI, fontSize: 11 }}
            tickMargin={4}
            width={45}
          />

          <ReferenceLine yAxisId="left" y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />

          <RechartsTooltip content={<CustomTooltip hiddenSeries={hiddenSeries} />} />

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
            dataKey="balance"
            stroke={COLOR_BALANCE}
            strokeWidth={1.5}
            dot={false}
            name="出荷在庫バランス"
            yAxisId="left"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('balance')}
          />
          <Line
            type="monotone"
            dataKey="balance_3ma"
            stroke={COLOR_BALANCE_3MA}
            strokeWidth={2}
            dot={false}
            name="3ヶ月移動平均"
            yAxisId="left"
            strokeDasharray="6 3"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('balance_3ma')}
          />
          <Line
            type="monotone"
            dataKey="nikkei_yoy"
            stroke={COLOR_NIKKEI_YOY}
            strokeWidth={1.5}
            dot={false}
            name="日経平均(前年比%)"
            yAxisId="right1"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('nikkei_yoy')}
          />
          <Line
            type="monotone"
            dataKey="nikkei"
            stroke={COLOR_NIKKEI}
            strokeWidth={1.5}
            dot={false}
            name="日経平均"
            yAxisId="right2"
            connectNulls
            isAnimationActive={false}
            hide={isHidden('nikkei')}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
