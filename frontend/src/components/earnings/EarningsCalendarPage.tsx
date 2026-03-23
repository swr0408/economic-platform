/**
 * EarningsCalendarPage
 *
 * countryCode === 'all'  → 全国統一カレンダー
 * countryCode === <code> → 特定国カレンダー
 *
 * 画面上部: 国タブ切り替え
 * カレンダー: 月2ヶ月表示、日付セルに件数 + ホバーで企業リスト
 * テーブル: 全企業一覧（日付未定は末尾）
 */
import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Table, Typography, Alert, Spin, Tag, Space, Select } from 'antd'
import { CalendarOutlined, ClockCircleOutlined, GlobalOutlined, LeftOutlined, RightOutlined } from '@ant-design/icons'
import { EARNINGS_COUNTRIES, getEarningsCountry } from '../../constants/earningsData'
import type { EarningsCompany } from '../../constants/earningsData'

const { Title, Text } = Typography

const colors = {
  bgPrimary:    '#0f172a',
  bgSecondary:  '#1e293b',
  bgTertiary:   '#334155',
  textPrimary:  '#f1f5f9',
  textSecondary:'#94a3b8',
  accent:       '#10b981',
  border:       '#334155',
}

// -----------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------
interface CalendarEntry {
  symbol: string
  name: string
  tier?: string
  date: string | null
  time: string | null
  eps_estimate: number | null
  eps_actual:   number | null
  revenue_estimate: number | null
  revenue_actual:   number | null
  country_code?: string
}

interface CalendarApiResponse {
  country: string
  country_name: string
  items: CalendarEntry[]
  next_7d_count:  number
  next_30d_count: number
  last_updated: string | null
  cached: boolean
  status: string
  message?: string
}

type EnrichedEntry = CalendarEntry & { tier?: string }

// -----------------------------------------------------------------------
// Tier badge
// -----------------------------------------------------------------------
const TIER_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  S: { bg: '#fef9c320', border: '#fde04780', text: '#fde047' },
  A: { bg: '#e0f2fe20', border: '#7dd3fc80', text: '#7dd3fc' },
  B: { bg: '#f1f5f920', border: '#94a3b880', text: '#94a3b8' },
}

function TierBadge({ tier }: { tier: string }) {
  const style = TIER_COLORS[tier] ?? TIER_COLORS['B']
  return (
    <span style={{
      display: 'inline-block', padding: '0 5px', borderRadius: 4,
      fontSize: 10, fontWeight: 700,
      background: style.bg, border: `1px solid ${style.border}`, color: style.text, lineHeight: '17px',
    }}>
      {tier}
    </span>
  )
}

// -----------------------------------------------------------------------
// Mini calendar
// -----------------------------------------------------------------------
const DAY_LABELS = ['日', '月', '火', '水', '木', '金', '土']

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate()
}
function getFirstDayOfWeek(year: number, month: number) {
  return new Date(year, month, 1).getDay()
}

interface DayEntry {
  name: string
  tier?: string
  symbol: string
  flag?: string
}

function MiniCalendar({
  year, month, dayMap, showPrev, showNext, onPrev, onNext,
}: {
  year: number
  month: number
  dayMap: Record<string, DayEntry[]>
  showPrev: boolean
  showNext: boolean
  onPrev: () => void
  onNext: () => void
}) {
  const [hoveredDate, setHoveredDate] = useState<string | null>(null)
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 })
  const today = new Date()
  const todayStr = today.toISOString().slice(0, 10)

  const daysInMonth = getDaysInMonth(year, month)
  const firstDow = getFirstDayOfWeek(year, month)

  const cells: (number | null)[] = []
  for (let i = 0; i < firstDow; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)
  while (cells.length % 7 !== 0) cells.push(null)

  const weeks: (number | null)[][] = []
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7))

  return (
    <div style={{ position: 'relative', flex: '1 1 0', minWidth: 0 }}>
      {/* ヘッダー */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <button onClick={onPrev} style={{ ...navBtnStyle, visibility: showPrev ? 'visible' : 'hidden' }}>
          <LeftOutlined />
        </button>
        <Text style={{ color: colors.textPrimary, fontWeight: 600, fontSize: 14 }}>
          {year}年{month + 1}月
        </Text>
        <button onClick={onNext} style={{ ...navBtnStyle, visibility: showNext ? 'visible' : 'hidden' }}>
          <RightOutlined />
        </button>
      </div>

      {/* 曜日ヘッダー */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)',
        borderTop: `1px solid ${colors.border}`,
        borderLeft: `1px solid ${colors.border}`,
      }}>
        {DAY_LABELS.map((d, i) => (
          <div key={d} style={{
            textAlign: 'center', fontSize: 11, fontWeight: 700, padding: '6px 0',
            color: i === 0 ? '#ef4444' : i === 6 ? '#60a5fa' : colors.textSecondary,
            background: '#0f172a',
            borderRight: `1px solid ${colors.border}`,
            borderBottom: `1px solid ${colors.border}`,
          }}>
            {d}
          </div>
        ))}
      </div>

      {/* 日付グリッド */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)',
        borderLeft: `1px solid ${colors.border}`,
        borderBottom: `1px solid ${colors.border}`,
        borderRadius: '0 0 6px 6px',
        overflow: 'hidden',
      }}>
        {weeks.flat().map((day, idx) => {
          if (!day) return (
            <div key={idx} style={{
              minHeight: 52,
              background: '#0a1220',
              borderRight: `1px solid ${colors.border}`,
              borderBottom: `1px solid ${colors.border}`,
            }} />
          )
          const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
          const entries = dayMap[dateStr] ?? []
          const count = entries.length
          const isToday = dateStr === todayStr
          const dow = (firstDow + day - 1) % 7
          const isSun = dow === 0
          const isSat = dow === 6

          return (
            <div
              key={idx}
              style={{
                minHeight: 52,
                padding: '5px 6px',
                background: isToday
                  ? '#10b98110'
                  : count > 0
                  ? '#1a3a5c'
                  : isSat || isSun ? '#0d1b2a' : '#111827',
                borderRight: `1px solid ${colors.border}`,
                borderBottom: `1px solid ${colors.border}`,
                cursor: count > 0 ? 'pointer' : 'default',
                transition: 'background 0.1s',
                outline: isToday ? `2px solid ${colors.accent}` : count > 0 ? '1px solid #2563eb60' : 'none',
                outlineOffset: '-1px',
              }}
              onMouseEnter={(e) => {
                if (count > 0) {
                  setHoveredDate(dateStr)
                  const rect = e.currentTarget.getBoundingClientRect()
                  setTooltipPos({ x: rect.left, y: rect.bottom + 4 })
                }
                if (count === 0) {
                  (e.currentTarget as HTMLDivElement).style.background = '#1e293b'
                }
              }}
              onMouseLeave={(e) => {
                setHoveredDate(null)
                if (count === 0) {
                  (e.currentTarget as HTMLDivElement).style.background =
                    isToday ? '#10b98110' : isSat || isSun ? '#0d1b2a' : '#111827'
                }
              }}
            >
              <div style={{
                fontSize: 12, fontWeight: isToday ? 700 : 400,
                color: isToday ? colors.accent : isSun ? '#ef4444' : isSat ? '#60a5fa' : colors.textPrimary,
                lineHeight: '16px',
              }}>
                {day}
              </div>
              {count > 0 && (
                <div style={{
                  display: 'inline-block',
                  marginTop: 3,
                  fontSize: 10, fontWeight: 700,
                  color: '#bfdbfe',
                  background: '#1d4ed860',
                  border: '1px solid #3b82f640',
                  borderRadius: 3,
                  padding: '0 4px',
                  lineHeight: '16px',
                }}>
                  {count}件
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* ツールチップ */}
      {hoveredDate && dayMap[hoveredDate] && (
        <div style={{
          position: 'fixed',
          left: Math.min(tooltipPos.x, window.innerWidth - 240),
          top: tooltipPos.y,
          background: '#0f172a',
          border: `1px solid ${colors.border}`,
          borderRadius: 8,
          padding: '8px 12px',
          zIndex: 9999,
          minWidth: 200,
          maxHeight: 300,
          overflowY: 'auto',
          boxShadow: '0 4px 16px rgba(0,0,0,0.5)',
          pointerEvents: 'none',
        }}>
          <Text style={{ color: colors.accent, fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 4 }}>
            {hoveredDate}
          </Text>
          {dayMap[hoveredDate].map((e, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 2 }}>
              {e.flag && <span style={{ fontSize: 12 }}>{e.flag}</span>}
              {e.tier && <TierBadge tier={e.tier} />}
              <Text style={{ color: colors.textPrimary, fontSize: 12 }}>{e.name}</Text>
              <Text style={{ color: colors.textSecondary, fontSize: 10 }}>({e.symbol})</Text>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const navBtnStyle: React.CSSProperties = {
  background: 'transparent',
  border: `1px solid ${colors.border}`,
  borderRadius: 4,
  color: colors.textSecondary,
  cursor: 'pointer',
  padding: '3px 8px',
  fontSize: 11,
}

// -----------------------------------------------------------------------
// Two-month calendar view
// -----------------------------------------------------------------------
function TwoMonthCalendar({ items }: { items: EnrichedEntry[] }) {
  const now = new Date()
  const [baseYear, setBaseYear] = useState(now.getFullYear())
  const [baseMonth, setBaseMonth] = useState(now.getMonth())

  const dayMap = useMemo(() => {
    const m: Record<string, DayEntry[]> = {}
    items.forEach((item) => {
      if (!item.date) return
      const country = item.country_code ? getEarningsCountry(item.country_code) : undefined
      if (!m[item.date]) m[item.date] = []
      m[item.date].push({
        name: item.name,
        tier: item.tier,
        symbol: item.symbol,
        flag: country?.flag,
      })
    })
    return m
  }, [items])

  const nextYear  = baseMonth === 11 ? baseYear + 1 : baseYear
  const nextMonth = baseMonth === 11 ? 0 : baseMonth + 1

  const goPrev = () => {
    if (baseMonth === 0) { setBaseYear(y => y - 1); setBaseMonth(11) }
    else setBaseMonth(m => m - 1)
  }
  const goNext = () => {
    if (baseMonth === 11) { setBaseYear(y => y + 1); setBaseMonth(0) }
    else setBaseMonth(m => m + 1)
  }

  return (
    <div style={{
      background: colors.bgSecondary,
      border: `1px solid ${colors.border}`,
      borderRadius: 10,
      padding: '16px 24px 20px',
      marginBottom: 20,
      display: 'grid',
      gridTemplateColumns: '1fr 1px 1fr',
      gap: '0 28px',
    }}>
      <MiniCalendar
        year={baseYear} month={baseMonth} dayMap={dayMap}
        showPrev onPrev={goPrev}
        showNext={false} onNext={() => {}}
      />
      {/* 区切り線 */}
      <div style={{ background: colors.border, margin: '0 0' }} />
      <MiniCalendar
        year={nextYear} month={nextMonth} dayMap={dayMap}
        showPrev={false} onPrev={() => {}}
        showNext onNext={goNext}
      />
    </div>
  )
}

// -----------------------------------------------------------------------
// Table columns
// -----------------------------------------------------------------------
function buildColumns(showCountry: boolean) {
  return [
    ...(showCountry
      ? [{
          title: '国',
          dataIndex: 'country_code',
          key: 'country',
          width: 50,
          render: (code: string) => {
            const c = getEarningsCountry(code)
            return <span style={{ fontSize: 18 }}>{c?.flag ?? ''}</span>
          },
        }]
      : []),
    {
      title: '企業名',
      key: 'name',
      render: (_: unknown, record: EnrichedEntry) => (
        <div>
          <Space size={4}>
            {record.tier && <TierBadge tier={record.tier} />}
            <Text style={{ color: colors.textPrimary, fontWeight: 500 }}>{record.name}</Text>
          </Space>
          <br />
          <Text style={{ color: colors.textSecondary, fontSize: 11 }}>{record.symbol}</Text>
        </div>
      ),
    },
    {
      title: '発表日',
      dataIndex: 'date',
      key: 'date',
      sorter: (a: EnrichedEntry, b: EnrichedEntry) => {
        if (!a.date && !b.date) return 0
        if (!a.date) return 1
        if (!b.date) return -1
        return a.date.localeCompare(b.date)
      },
      render: (d: string | null) =>
        d ? (
          <Text style={{ color: colors.textPrimary }}>{d}</Text>
        ) : (
          <Tag style={{ background: '#33415520', border: '1px solid #475569', color: '#94a3b8', fontSize: 11 }}>
            未定
          </Tag>
        ),
    },
    {
      title: '時刻',
      dataIndex: 'time',
      key: 'time',
      width: 70,
      render: (time: string | null) => {
        if (!time || time === '--') return <Text style={{ color: colors.textSecondary }}>—</Text>
        const label = time === 'BMO' ? '寄前' : time === 'AMC' ? '引後' : time
        const color = time === 'BMO' ? 'blue' : time === 'AMC' ? 'orange' : 'default'
        return <Tag color={color} style={{ fontSize: 11 }}>{label}</Tag>
      },
    },
    {
      title: 'EPS予想',
      dataIndex: 'eps_estimate',
      key: 'eps_estimate',
      align: 'right' as const,
      render: (val: number | null) => (
        <Text style={{ color: colors.textSecondary, fontSize: 12 }}>{val != null ? val.toFixed(2) : '—'}</Text>
      ),
    },
    {
      title: 'EPS実績',
      dataIndex: 'eps_actual',
      key: 'eps_actual',
      align: 'right' as const,
      render: (val: number | null, record: EnrichedEntry) => {
        if (val == null) return <Text style={{ color: colors.textSecondary, fontSize: 12 }}>—</Text>
        const beat = record.eps_estimate != null && val > record.eps_estimate
        const miss = record.eps_estimate != null && val < record.eps_estimate
        return (
          <Text style={{ color: beat ? '#10b981' : miss ? '#ef4444' : colors.textPrimary, fontWeight: 600, fontSize: 12 }}>
            {val.toFixed(2)}
          </Text>
        )
      },
    },
    {
      title: '売上予想',
      dataIndex: 'revenue_estimate',
      key: 'revenue_estimate',
      align: 'right' as const,
      render: (val: number | null) => (
        <Text style={{ color: colors.textSecondary, fontSize: 12 }}>
          {val != null ? `$${(val / 1e9).toFixed(2)}B` : '—'}
        </Text>
      ),
    },
    {
      title: '売上実績',
      dataIndex: 'revenue_actual',
      key: 'revenue_actual',
      align: 'right' as const,
      render: (val: number | null, record: EnrichedEntry) => {
        if (val == null) return <Text style={{ color: colors.textSecondary, fontSize: 12 }}>—</Text>
        const beat = record.revenue_estimate != null && val > record.revenue_estimate
        const miss = record.revenue_estimate != null && val < record.revenue_estimate
        return (
          <Text style={{ color: beat ? '#10b981' : miss ? '#ef4444' : colors.textPrimary, fontWeight: 600, fontSize: 12 }}>
            ${(val / 1e9).toFixed(2)}B
          </Text>
        )
      },
    },
  ]
}

// -----------------------------------------------------------------------
// Country tab bar
// -----------------------------------------------------------------------
function CountryTabBar({ current, onSelect }: { current: string; onSelect: (code: string) => void }) {
  const tabs = [
    { code: 'all', label: '全体', flag: '' },
    ...EARNINGS_COUNTRIES.map((c) => ({ code: c.code, label: c.nameJa, flag: c.flag })),
  ]
  return (
    <div style={{
      display: 'flex', gap: 4, flexWrap: 'wrap',
      marginBottom: 20, padding: '8px 0', borderBottom: `1px solid ${colors.border}`,
    }}>
      {tabs.map((tab) => {
        const isActive = tab.code === current
        return (
          <button key={tab.code} onClick={() => onSelect(tab.code)} style={{
            padding: '4px 10px', borderRadius: 6,
            border: `1px solid ${isActive ? colors.accent : colors.border}`,
            background: isActive ? `${colors.accent}20` : 'transparent',
            color: isActive ? colors.accent : colors.textSecondary,
            cursor: 'pointer', fontSize: 12, fontWeight: isActive ? 600 : 400,
            transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: 4,
          }}>
            {tab.flag ? <span>{tab.flag}</span> : <GlobalOutlined style={{ fontSize: 11 }} />}
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}

// -----------------------------------------------------------------------
// Main
// -----------------------------------------------------------------------
interface Props {
  countryCode: string
}

export default function EarningsCalendarPage({ countryCode }: Props) {
  const navigate = useNavigate()
  const [data, setData] = useState<CalendarApiResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pageSize, setPageSize] = useState(30)

  const targetCountries = countryCode === 'all'
    ? EARNINGS_COUNTRIES.map((c) => c.code)
    : [countryCode]

  useEffect(() => {
    setLoading(true)
    setError(null)
    const url = countryCode === 'all'
      ? '/api/earnings/calendar/all'
      : `/api/earnings/${countryCode}/calendar`

    fetch(url)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then((json: CalendarApiResponse) => {
        const items = json.items.map((item) => ({
          ...item,
          country_code: item.country_code ?? countryCode,
        }))
        setData({ ...json, items })
        setLoading(false)
      })
      .catch((err) => { setError(err.message); setLoading(false) })
  }, [countryCode])

  // tier map
  const tierMap: Record<string, string> = {}
  targetCountries.forEach((cc) => {
    const country = EARNINGS_COUNTRIES.find((c) => c.code === cc)
    country?.companies.forEach((comp: EarningsCompany) => { tierMap[comp.ticker] = comp.tier })
  })

  const enriched: EnrichedEntry[] = (data?.items ?? []).map((item) => ({
    ...item,
    tier: item.tier ?? tierMap[item.symbol],
  }))

  const isAll = countryCode === 'all'
  const columns = buildColumns(isAll)

  return (
    <div>
      <CountryTabBar current={countryCode} onSelect={(code) => navigate(`/earnings/calendar/${code}`)} />

      {loading && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
          <Spin size="large" />
        </div>
      )}

      {!loading && error && (
        <Alert type="error" message="データの取得に失敗しました" description={error} showIcon />
      )}

      {!loading && !error && (!data || (data.status === 'error' && data.items.length === 0)) && (
        <Alert type="warning" message="データ取得エラー"
          description="FMP APIからのデータ取得に失敗しました。" showIcon icon={<CalendarOutlined />} />
      )}

      {!loading && !error && data && !(data.status === 'error' && data.items.length === 0) && (
        <>
          {/* サマリー */}
          <div style={{ display: 'flex', gap: 16, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
            <SummaryBox icon={<ClockCircleOutlined style={{ color: colors.accent, fontSize: 18 }} />}
              label="直近7日間" value={`${data.next_7d_count} 件`} />
            <SummaryBox icon={<CalendarOutlined style={{ color: '#3b82f6', fontSize: 18 }} />}
              label="直近30日間" value={`${data.next_30d_count} 件`} />
            {data.last_updated && (
              <div style={{ marginLeft: 'auto' }}>
                <Text style={{ color: colors.textSecondary, fontSize: 12 }}>
                  更新: {new Date(data.last_updated).toLocaleString('ja-JP')}
                  {data.cached && <Tag color="green" style={{ marginLeft: 8 }}>キャッシュ</Tag>}
                </Text>
              </div>
            )}
          </div>

          {/* ミニカレンダー */}
          <TwoMonthCalendar items={enriched} />

          {/* テーブル */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <Title level={5} style={{ margin: 0, color: colors.textPrimary }}>
              決算カレンダー {isAll ? '— 全体' : `— ${getEarningsCountry(countryCode)?.flag} ${getEarningsCountry(countryCode)?.nameJa}`}
              <Text style={{ color: colors.textSecondary, fontSize: 12, marginLeft: 8 }}>
                ({enriched.length} 社)
              </Text>
            </Title>
            {/* 独立した件数セレクター（ページネーション内蔵のものを使わない） */}
            <Space size={6} align="center">
              <Text style={{ color: colors.textSecondary, fontSize: 12 }}>表示件数:</Text>
              <Select
                value={pageSize}
                onChange={(v) => setPageSize(v)}
                size="small"
                style={{ width: 80 }}
                options={[
                  { value: 20,  label: '20件' },
                  { value: 30,  label: '30件' },
                  { value: 50,  label: '50件' },
                  { value: 100, label: '100件' },
                  { value: 9999,label: '全件' },
                ]}
              />
            </Space>
          </div>

          <Table
            dataSource={enriched}
            columns={columns}
            rowKey={(r) => `${r.symbol}-${r.date ?? 'tbd'}`}
            size="small"
            pagination={{
              pageSize,
              total: enriched.length,
              showTotal: (total, range) => (
                <Text style={{ color: colors.textSecondary, fontSize: 12 }}>
                  {range[0]}–{range[1]} / {total} 社
                </Text>
              ),
              showSizeChanger: false,   // 上の Select で代替
            }}
            style={{ background: colors.bgSecondary }}
          />
        </>
      )}
    </div>
  )
}

function SummaryBox({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div style={{
      background: colors.bgSecondary, border: `1px solid ${colors.border}`,
      borderRadius: 8, padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 10,
    }}>
      {icon}
      <div>
        <Text style={{ color: colors.textSecondary, fontSize: 12 }}>{label}</Text>
        <br />
        <Text style={{ color: colors.textPrimary, fontSize: 18, fontWeight: 600 }}>{value}</Text>
      </div>
    </div>
  )
}
