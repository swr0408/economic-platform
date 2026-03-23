import { useState, useMemo } from 'react'
import { Tabs, Tooltip, Button } from 'antd'
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
import { useMarketBatchData } from '../../../hooks/useMarketData'
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS, CHART_MARGIN } from '../../country/usa/common/chartConstants'
import MarketImpactTab from '../../indicator/MarketImpactTab'

const DARK_THEME = {
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  gridLine: '#475569',
  axisLine: '#64748b',
  tooltipBg: '#334155',
  tooltipBorder: '#475569',
  chartBg: '#1e293b',
}

const COLOR_MAIN = '#f59e0b'     // Amber
const COLOR_OIL = '#ef4444'      // Red (inverted)

interface RigItem {
  date: string
  value: number | null
}

interface RigResponse {
  data: RigItem[]
  latest: RigItem | null
  next_release: { date: string; label?: string; time_jst?: string } | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

interface MergedItem extends RigItem {
  oil_price: number | null
}

type ActiveTab = 'timeseries' | 'market_impact'

type SeriesKey = 'value' | 'oil_price'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ChartTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatMonthLabel(String(label))
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
      {!hiddenSeries.has('value') && dp.value != null && (
        <div style={{ color: COLOR_MAIN, fontSize: 13, marginBottom: 3 }}>
          リグ稼働数: {dp.value.toLocaleString()} 基
        </div>
      )}
      {!hiddenSeries.has('oil_price') && dp.oil_price != null && (
        <div style={{ color: COLOR_OIL, fontSize: 13, marginBottom: 3 }}>
          WTI原油: ${dp.oil_price.toLocaleString(undefined, { maximumFractionDigits: 2 })} /bbl
        </div>
      )}
    </div>
  )
}


export default function NorthAmericaRigCountChart() {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)
  const [activeTab, setActiveTab] = useState<ActiveTab>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<SeriesKey>()

  const { data: response } = useQuery<RigResponse>({
    queryKey: ['rig-count'],
    queryFn: async () => {
      const res = await axios.get('/api/market/rig-count')
      return res.data
    },
    staleTime: 1000 * 60 * 30,
  })

  // WTI oil price
  const { data: marketData } = useMarketBatchData(['crude_oil'])

  const mergedData = useMemo(() => {
    if (!response?.data) return []

    const oilMap = new Map<string, number>()
    if (marketData?.crude_oil?.data) {
      for (const d of marketData.crude_oil.data) {
        if (d.close != null) oilMap.set(d.date, d.close)
      }
    }

    return response.data.map(item => {
      let oilPrice: number | null = null
      if (oilMap.has(item.date)) {
        oilPrice = oilMap.get(item.date)!
      } else {
        const d = new Date(item.date)
        for (let offset = 1; offset <= 5; offset++) {
          const before = new Date(d)
          before.setDate(before.getDate() - offset)
          const beforeStr = before.toISOString().slice(0, 10)
          if (oilMap.has(beforeStr)) {
            oilPrice = oilMap.get(beforeStr)!
            break
          }
          const after = new Date(d)
          after.setDate(after.getDate() + offset)
          const afterStr = after.toISOString().slice(0, 10)
          if (oilMap.has(afterStr)) {
            oilPrice = oilMap.get(afterStr)!
            break
          }
        }
      }

      return { ...item, oil_price: oilPrice }
    })
  }, [response, marketData])

  const filteredData = useMemo(() => {
    if (!mergedData.length) return []
    if (currentPeriod === 'all') return mergedData
    const years = typeof currentPeriod === 'number' ? currentPeriod : 5
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return mergedData.filter(d => d.date >= cutoffStr)
  }, [mergedData, currentPeriod])

  const latest = response?.latest
  const nextRelease = response?.next_release
  const latestOil = marketData?.crude_oil?.latest

  return (
    <ChartContainer
      title="米石油採掘装置（リグ）稼働数"
      dataSource="EIA / Baker Hughes"
      sourceUrl="https://www.eia.gov/dnav/ng/ng_enr_drill_s1_m.htm"
      showPeriodSelector={false}
      handbookId="shale-oil-rig-count"
    >
      {/* Latest value box */}
      <div style={LATEST_VALUE_BOX_STYLE}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          {latest?.date && (
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
              {latest.date.slice(0, 7).replace('-', '/')}
            </span>
          )}
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>リグ稼働数: </span>
            <span style={{ fontSize: 20, fontWeight: 'bold', color: COLOR_MAIN }}>
              {latest?.value != null ? `${latest.value.toLocaleString()} 基` : '—'}
            </span>
          </div>
          {latestOil?.close != null && (
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>WTI: </span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLOR_OIL }}>
                ${latestOil.close.toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </span>
            </div>
          )}
        </div>
        {nextRelease && (
          <span style={{ fontSize: 11, color: TEXT_COLORS.secondary, whiteSpace: 'nowrap' }}>
            次回: {nextRelease.date}{nextRelease.time_jst && ` ${nextRelease.time_jst} JST`}
          </span>
        )}
      </div>

      {/* タブ切替 */}
      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as ActiveTab)}
        style={{ marginTop: 8 }}
        items={[
          {
            key: 'timeseries',
            label: '時系列',
            children: (
              <>
                {/* データ比較ボタン */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
                  <Tooltip title="比較ページを開く">
                    <Button
                      icon={<AreaChartOutlined />}
                      onClick={() => window.open('/compare?s=north_america_rig_count', '_blank')}
                    >
                      データ比較
                    </Button>
                  </Tooltip>
                </div>

                <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                <ResponsiveContainer width="100%" height={400}>
                  <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                    <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
                    <XAxis dataKey="date" tickFormatter={(v) => formatMonthLabel(v)} stroke={DARK_THEME.axisLine} tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }} minTickGap={40} />
                    <YAxis yAxisId="left" domain={['dataMin * 0.9', 'dataMax * 1.1']} tickFormatter={(v: number) => `${v.toLocaleString()}`} stroke={COLOR_MAIN} tick={{ fill: COLOR_MAIN, fontSize: 11 }} width={55} />
                    <YAxis yAxisId="oil" orientation="right" reversed domain={['dataMin * 0.9', 'dataMax * 1.1']} tickFormatter={(v: number) => `$${v.toFixed(0)}`} stroke={COLOR_OIL} tick={{ fill: COLOR_OIL, fontSize: 10 }} width={50} axisLine={{ stroke: COLOR_OIL, strokeDasharray: '4 3' }} />
                    <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} />} />
                    <Legend onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)} wrapperStyle={{ cursor: 'pointer' }} formatter={(value: string, entry: any) => (<span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>)} />
                    <Line yAxisId="left" type="monotone" dataKey="value" name="リグ稼働数 (基)" stroke={COLOR_MAIN} strokeWidth={2} dot={false} hide={hiddenSeries.has('value')} connectNulls isAnimationActive={false} />
                    <Line yAxisId="oil" type="monotone" dataKey="oil_price" name="WTI原油 (USD/bbl, 反転)" stroke={COLOR_OIL} strokeWidth={1.5} strokeDasharray="4 3" dot={false} hide={hiddenSeries.has('oil_price')} connectNulls isAnimationActive={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </>
            ),
          },
          {
            key: 'market_impact',
            label: 'マーケットインパクト',
            children: (
              <MarketImpactTab indicatorId="north_america_rig_count" />
            ),
          },
        ]}
      />
    </ChartContainer>
  )
}
