import { useState, useMemo } from 'react'
import { Tooltip, Button } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
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

const COLOR_HDD = '#f97316'  // Orange - heating degree days
const COLOR_CDD = '#06b6d4'  // Cyan - cooling degree days

// 天然ガス需要感応度の高い地域マッピング
// 最優先: East North Central (IL, IN, OH, MI, WI) — 最大の天気感応型ガス需要地帯
// 次点: Northeast / Mid-Atlantic — 人口密度が高く寒波時の暖房需要大
// 次点: South Atlantic — 寒気流入時の需要反応
// 補助: Texas — 冬は暖房より夏CDD・凍結イベント
type GasPriority = 'critical' | 'high' | 'medium' | 'low'

const GAS_DEMAND_REGIONS: Record<string, { priority: GasPriority; region: string }> = {
  // 最優先: East North Central
  'ILLINOIS': { priority: 'critical', region: 'East N. Central' },
  'INDIANA': { priority: 'critical', region: 'East N. Central' },
  'OHIO': { priority: 'critical', region: 'East N. Central' },
  'MICHIGAN': { priority: 'critical', region: 'East N. Central' },
  'WISCONSIN': { priority: 'critical', region: 'East N. Central' },
  // 次点: Northeast / Mid-Atlantic
  'NEW YORK': { priority: 'high', region: 'Northeast' },
  'PENN': { priority: 'high', region: 'Mid-Atlantic' },
  'NEW JERSEY': { priority: 'high', region: 'Mid-Atlantic' },
  'VERMONT': { priority: 'high', region: 'New England' },
  'NEW HAMP': { priority: 'high', region: 'New England' },
  'MAINE': { priority: 'high', region: 'New England' },
  'MASS': { priority: 'high', region: 'New England' },
  'CONN': { priority: 'high', region: 'New England' },
  'RHODE IS': { priority: 'high', region: 'New England' },
  'MARYLAND': { priority: 'high', region: 'Mid-Atlantic' },
  'DELAWARE': { priority: 'high', region: 'Mid-Atlantic' },
  'W VIRGINIA': { priority: 'high', region: 'Mid-Atlantic' },
  // 次点: South Atlantic
  'VIRGINIA': { priority: 'medium', region: 'South Atlantic' },
  'N CAROLINA': { priority: 'medium', region: 'South Atlantic' },
  'S CAROLINA': { priority: 'medium', region: 'South Atlantic' },
  'GEORGIA': { priority: 'medium', region: 'South Atlantic' },
  'FL PNHDL': { priority: 'medium', region: 'South Atlantic' },
  'FL PENIN': { priority: 'medium', region: 'South Atlantic' },
  // 補助: Texas
  'N TEXAS': { priority: 'low', region: 'Texas' },
  'S TEXAS': { priority: 'low', region: 'Texas' },
  'W TEXAS': { priority: 'low', region: 'Texas' },
}

const PRIORITY_STYLES: Record<GasPriority, { borderColor: string; indicator: string; label: string }> = {
  critical: { borderColor: '#f59e0b', indicator: '🔥', label: '最優先' },
  high: { borderColor: '#fb923c', indicator: '⚡', label: '次点' },
  medium: { borderColor: '#94a3b8', indicator: '', label: '' },
  low: { borderColor: '#94a3b8', indicator: '', label: '' },
}

interface HddCddItem {
  date: string
  hdd: number | null
  cdd: number | null
  forecast?: boolean
}

interface OutlookState {
  state: string
  temp: string
  precip: string
}

interface OutlookPeriod {
  date_range: string
  states: OutlookState[]
}

interface Week34Outlook {
  date_range: string
  forecaster: string
  temp_summary: string
  precip_summary: string
}

interface NoaaHddCddResponse {
  data: HddCddItem[]
  latest: HddCddItem | null
  outlook: {
    '6_10'?: OutlookPeriod
    '8_14'?: OutlookPeriod
    '3_4'?: Week34Outlook
  } | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

type ViewMode = 'timeseries' | 'outlook'
const VIEW_MODE_OPTIONS = [
  { mode: 'timeseries' as ViewMode, label: 'HDD/CDD時系列' },
  { mode: 'outlook' as ViewMode, label: '気温見通し' },
]

type OutlookPeriodKey = '6_10' | '8_14' | '3_4'
const OUTLOOK_PERIOD_OPTIONS = [
  { mode: '6_10' as OutlookPeriodKey, label: '6-10日' },
  { mode: '8_14' as OutlookPeriodKey, label: '8-14日' },
  { mode: '3_4' as OutlookPeriodKey, label: 'Week 3-4' },
]

type SeriesKey = 'hdd' | 'cdd'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ChartTooltip({ active, payload, label, hiddenSeries }: {
  active?: boolean
  payload?: any[]
  label?: string
  hiddenSeries: Set<string>
}) {
  if (!active || !payload || payload.length === 0) return null
  const formattedLabel = formatDayLabel(String(label))
  const dp = payload[0]?.payload as HddCddItem | undefined
  if (!dp) return null

  return (
    <div style={{
      backgroundColor: DARK_THEME.tooltipBg,
      border: `1px solid ${DARK_THEME.tooltipBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
        {formattedLabel}{dp.forecast ? ' (予測)' : ''}
      </div>
      {!hiddenSeries.has('hdd') && dp.hdd != null && (
        <div style={{ color: COLOR_HDD, fontSize: 13, marginBottom: 3 }}>
          HDD (暖房): {dp.hdd}
        </div>
      )}
      {!hiddenSeries.has('cdd') && dp.cdd != null && (
        <div style={{ color: COLOR_CDD, fontSize: 13, marginBottom: 3 }}>
          CDD (冷房): {dp.cdd}
        </div>
      )}
    </div>
  )
}

// 気温見通しの色
function getTempColor(val: string) {
  switch (val) {
    case 'A': return { bg: 'rgba(239,68,68,0.15)', border: '#ef444444', text: '#ef4444', label: '暖' }
    case 'B': return { bg: 'rgba(59,130,246,0.15)', border: '#3b82f644', text: '#60a5fa', label: '寒' }
    default: return { bg: 'rgba(148,163,184,0.1)', border: '#64748b44', text: '#94a3b8', label: '平年' }
  }
}

function getPrecipColor(val: string) {
  switch (val) {
    case 'A': return { text: '#22c55e', label: '多雨' }
    case 'B': return { text: '#f59e0b', label: '少雨' }
    default: return { text: '#94a3b8', label: '平年' }
  }
}

// 天然ガス需要重要地域を先頭にソート
function sortStatesByGasPriority(states: OutlookState[]): OutlookState[] {
  const priorityOrder: Record<GasPriority, number> = { critical: 0, high: 1, medium: 2, low: 3 }
  return [...states].sort((a, b) => {
    const pa = GAS_DEMAND_REGIONS[a.state]?.priority
    const pb = GAS_DEMAND_REGIONS[b.state]?.priority
    const oa = pa != null ? priorityOrder[pa] : 9
    const ob = pb != null ? priorityOrder[pb] : 9
    return oa - ob
  })
}


export default function NoaaHddCddChart() {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(1)
  const [viewMode, setViewMode] = useState<ViewMode>('timeseries')
  const [outlookPeriod, setOutlookPeriod] = useState<OutlookPeriodKey>('6_10')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<SeriesKey>()

  const { data: response } = useQuery<NoaaHddCddResponse>({
    queryKey: ['noaa-hdd-cdd'],
    queryFn: async () => {
      const res = await axios.get('/api/market/noaa-hdd-cdd')
      return res.data
    },
    staleTime: 1000 * 60 * 30,
  })

  const filteredData = useMemo(() => {
    if (!response?.data?.length) return []
    if (currentPeriod === 'all') return response.data
    const years = typeof currentPeriod === 'number' ? currentPeriod : 1
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return response.data.filter(d => d.date >= cutoffStr)
  }, [response, currentPeriod])

  // 予測開始日を特定
  const forecastStartDate = useMemo(() => {
    if (!response?.data?.length) return null
    const first = response.data.find(d => d.forecast)
    return first?.date ?? null
  }, [response])

  const latest = response?.latest

  return (
    <ChartContainer
      title="HDD/CDD & 気温見通し"
      dataSource="NOAA CPC"
      sourceUrl="https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/cdus/degree_days/"
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
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>HDD: </span>
            <span style={{ fontSize: 20, fontWeight: 'bold', color: COLOR_HDD }}>
              {latest?.hdd ?? '—'}
            </span>
          </div>
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>CDD: </span>
            <span style={{ fontSize: 20, fontWeight: 'bold', color: COLOR_CDD }}>
              {latest?.cdd ?? '—'}
            </span>
          </div>
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
            onClick={() => window.open('/compare?s=noaa_hdd&s=noaa_cdd', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 時系列モード */}
      {viewMode === 'timeseries' && (
        <>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

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
                domain={[0, 'dataMax * 1.1']}
                tickFormatter={(v: number) => `${v.toFixed(0)}`}
                stroke={DARK_THEME.axisLine}
                tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
                width={40}
              />
              <RechartsTooltip content={<ChartTooltip hiddenSeries={hiddenSeries} />} />
              <Legend
                onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)}
                wrapperStyle={{ cursor: 'pointer' }}
                formatter={(value: string, entry: any) => (
                  <span style={{ color: hiddenSeries.has(entry.dataKey as SeriesKey) ? '#64748b' : entry.color, fontSize: 12 }}>{value}</span>
                )}
              />
              {forecastStartDate && (
                <ReferenceLine
                  yAxisId="left"
                  x={forecastStartDate}
                  stroke="#fbbf24"
                  strokeDasharray="4 4"
                  label={{ value: '予測', position: 'top', fill: '#fbbf24', fontSize: 10 }}
                />
              )}
              <Bar
                yAxisId="left"
                dataKey="hdd"
                name="HDD (暖房度日)"
                stackId="dd"
                hide={hiddenSeries.has('hdd')}
                isAnimationActive={false}
              >
                {filteredData.map((entry, index) => (
                  <Cell
                    key={`hdd-${index}`}
                    fill={COLOR_HDD}
                    fillOpacity={entry.forecast ? 0.4 : 0.7}
                  />
                ))}
              </Bar>
              <Bar
                yAxisId="left"
                dataKey="cdd"
                name="CDD (冷房度日)"
                stackId="dd"
                hide={hiddenSeries.has('cdd')}
                isAnimationActive={false}
              >
                {filteredData.map((entry, index) => (
                  <Cell
                    key={`cdd-${index}`}
                    fill={COLOR_CDD}
                    fillOpacity={entry.forecast ? 0.4 : 0.7}
                  />
                ))}
              </Bar>
            </ComposedChart>
          </ResponsiveContainer>
        </>
      )}

      {/* 気温見通しモード */}
      {viewMode === 'outlook' && response?.outlook && (
        <div>
          {/* 期間切替ボタン */}
          <div style={{ marginBottom: 12 }}>
            <ViewModeButtonGroup
              options={OUTLOOK_PERIOD_OPTIONS}
              currentMode={outlookPeriod}
              onChange={(m) => setOutlookPeriod(m as OutlookPeriodKey)}
            />
          </div>

          {/* 6-10日 / 8-14日 テーブル表示 */}
          {(outlookPeriod === '6_10' || outlookPeriod === '8_14') && (() => {
            const data = response.outlook?.[outlookPeriod]
            if (!data) return null
            const sorted = sortStatesByGasPriority(data.states)
            return (
              <>
                {/* 天然ガス需要重要地域の凡例 */}
                <div style={{
                  display: 'flex', gap: 12, marginBottom: 12, padding: '8px 12px',
                  backgroundColor: 'rgba(245,158,11,0.08)', borderRadius: 6,
                  border: '1px solid rgba(245,158,11,0.2)', flexWrap: 'wrap', alignItems: 'center',
                }}>
                  <span style={{ fontSize: 11, color: '#f59e0b', fontWeight: 600 }}>天然ガス需要重要地域:</span>
                  <span style={{ fontSize: 11, color: DARK_THEME.textSecondary }}>
                    <span style={{ color: '#f59e0b' }}>&#9608;&#9608;</span> 最優先 (East N. Central: IL,IN,OH,MI,WI)
                  </span>
                  <span style={{ fontSize: 11, color: DARK_THEME.textSecondary }}>
                    <span style={{ color: '#fb923c' }}>&#9608;&#9608;</span> 次点 (Northeast/Mid-Atlantic)
                  </span>
                </div>

                <div style={{ fontSize: 14, color: DARK_THEME.textPrimary, fontWeight: 'bold', marginBottom: 8 }}>
                  {outlookPeriod === '6_10' ? '6-10日' : '8-14日'}気温見通し ({data.date_range})
                </div>
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                  gap: 4,
                }}>
                  {sorted.map(s => {
                    const tc = getTempColor(s.temp)
                    const pc = getPrecipColor(s.precip)
                    const gasInfo = GAS_DEMAND_REGIONS[s.state]
                    const pStyle = gasInfo ? PRIORITY_STYLES[gasInfo.priority] : null
                    const isCriticalOrHigh = gasInfo?.priority === 'critical' || gasInfo?.priority === 'high'

                    return (
                      <div key={`${outlookPeriod}-${s.state}`} style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '4px 8px',
                        borderRadius: 4,
                        backgroundColor: tc.bg,
                        border: `1px solid ${isCriticalOrHigh ? pStyle!.borderColor : tc.border}`,
                        borderWidth: isCriticalOrHigh ? 2 : 1,
                        boxShadow: isCriticalOrHigh ? `0 0 4px ${pStyle!.borderColor}40` : undefined,
                      }}>
                        <span style={{
                          fontSize: 11,
                          color: isCriticalOrHigh ? '#f1f5f9' : DARK_THEME.textPrimary,
                          fontWeight: isCriticalOrHigh ? 600 : 400,
                        }}>
                          {pStyle?.indicator ? `${pStyle.indicator} ` : ''}{s.state}
                          {gasInfo?.priority === 'critical' && (
                            <span style={{ fontSize: 9, color: '#f59e0b', marginLeft: 4 }}>ガス最優先</span>
                          )}
                          {gasInfo?.priority === 'high' && (
                            <span style={{ fontSize: 9, color: '#fb923c', marginLeft: 4 }}>ガス次点</span>
                          )}
                        </span>
                        <div style={{ display: 'flex', gap: 8 }}>
                          <span style={{ fontSize: 12, fontWeight: 'bold', color: tc.text }}>
                            {tc.label}
                          </span>
                          <span style={{ fontSize: 12, color: pc.text }}>
                            {pc.label}
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>

                {/* 凡例 */}
                <div style={{ display: 'flex', gap: 16, marginTop: 12, fontSize: 11, color: DARK_THEME.textSecondary, flexWrap: 'wrap' }}>
                  <span>
                    気温: <span style={{ color: '#ef4444' }}>暖=平年以上</span> / <span style={{ color: '#94a3b8' }}>平年=平年並</span> / <span style={{ color: '#60a5fa' }}>寒=平年以下</span>
                  </span>
                  <span>
                    降水: <span style={{ color: '#22c55e' }}>多雨=平年以上</span> / <span style={{ color: '#94a3b8' }}>平年=平年並</span> / <span style={{ color: '#f59e0b' }}>少雨=平年以下</span>
                  </span>
                </div>
              </>
            )
          })()}

          {/* Week 3-4 見通し */}
          {outlookPeriod === '3_4' && (() => {
            const w34 = response.outlook?.['3_4'] as Week34Outlook | undefined
            if (!w34) return (
              <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
                Week 3-4 見通しデータがありません
              </div>
            )
            return (
              <div>
                <div style={{ fontSize: 14, color: DARK_THEME.textPrimary, fontWeight: 'bold', marginBottom: 8 }}>
                  Week 3-4 見通し ({w34.date_range})
                </div>
                <div style={{
                  padding: '12px 16px',
                  backgroundColor: 'rgba(30,41,59,0.8)',
                  borderRadius: 8,
                  border: `1px solid ${DARK_THEME.gridLine}`,
                }}>
                  {w34.temp_summary && (
                    <div style={{ marginBottom: 10 }}>
                      <div style={{ fontSize: 12, color: '#ef4444', fontWeight: 600, marginBottom: 4 }}>
                        気温見通し
                      </div>
                      <div style={{ fontSize: 12, color: DARK_THEME.textPrimary, lineHeight: 1.6 }}>
                        {w34.temp_summary}
                      </div>
                    </div>
                  )}
                  {w34.precip_summary && (
                    <div style={{ marginBottom: 6 }}>
                      <div style={{ fontSize: 12, color: '#3b82f6', fontWeight: 600, marginBottom: 4 }}>
                        降水見通し
                      </div>
                      <div style={{ fontSize: 12, color: DARK_THEME.textPrimary, lineHeight: 1.6 }}>
                        {w34.precip_summary}
                      </div>
                    </div>
                  )}
                  {w34.forecaster && (
                    <div style={{ fontSize: 10, color: DARK_THEME.textSecondary, marginTop: 8, textAlign: 'right' }}>
                      Forecaster: {w34.forecaster}
                    </div>
                  )}
                </div>
              </div>
            )
          })()}
        </div>
      )}
    </ChartContainer>
  )
}
