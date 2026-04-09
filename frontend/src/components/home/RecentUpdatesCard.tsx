/**
 * ホーム画面 - 直近更新された指標カード
 *
 * /api/dashboard/recent-updates から取得し、国別タブで切り替え表示する。
 * Phase 1 では最終更新時刻のみ表示。値・前回比差分は Phase 2+ で
 * 指標ごとに個別パーサーを追加していく方針。
 */
import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Card, Typography, Segmented, Spin, Empty, Alert } from 'antd'
import {
  ReloadOutlined,
  BankOutlined,
  DollarOutlined,
  ShoppingOutlined,
  TeamOutlined,
  RiseOutlined,
  HomeOutlined,
  FundOutlined,
  CalendarOutlined,
  AreaChartOutlined,
  SmileOutlined,
} from '@ant-design/icons'
import axios from 'axios'

const { Text } = Typography

const colors = {
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  accent: '#10b981',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textTertiary: '#64748b',
  border: '#334155',
}

// カテゴリ → アイコン + カラー
// countryData.tsx の定義を踏襲しつつ、不足分を補完
const CATEGORY_STYLE: Record<string, { icon: ReactNode; color: string }> = {
  policy: { icon: <BankOutlined />, color: '#1890ff' },
  monetary_policy: { icon: <BankOutlined />, color: '#1890ff' },
  economy: { icon: <DollarOutlined />, color: '#52c41a' },
  economic_outlook: { icon: <FundOutlined />, color: '#52c41a' },
  inflation: { icon: <RiseOutlined />, color: '#ff4d4f' },
  price: { icon: <RiseOutlined />, color: '#ff4d4f' },
  employment: { icon: <TeamOutlined />, color: '#faad14' },
  consumer: { icon: <ShoppingOutlined />, color: '#13c2c2' },
  consumption: { icon: <ShoppingOutlined />, color: '#13c2c2' },
  consumer_sentiment: { icon: <SmileOutlined />, color: '#13c2c2' },
  housing: { icon: <HomeOutlined />, color: '#722ed1' },
  fiscal: { icon: <AreaChartOutlined />, color: '#eb2f96' },
  derivatives: { icon: <FundOutlined />, color: '#fa8c16' },
  economy_watcher: { icon: <SmileOutlined />, color: '#52c41a' },
  calendar: { icon: <CalendarOutlined />, color: '#94a3b8' },
}

const DEFAULT_CATEGORY_STYLE = { icon: <FundOutlined />, color: '#94a3b8' }

interface UpdateEntry {
  country: string
  country_label: string
  country_iso: string
  category: string
  category_label: string
  indicator_id: string
  indicator_label: string
  last_updated: string // ISO8601
  route?: string
  anchor?: string
  // 値・前回比は現状 UI では非表示 (バックエンドは返しているが使わない)
  // 将来必要になれば個別パーサーを充実させた上で再表示する
  value?: number | null
  previous?: number | null
  change?: number | null
  change_pct?: number | null
  yoy?: number | null
  mom?: number | null
}

interface RecentUpdatesResponse {
  updates: UpdateEntry[]
  counts_by_country: Record<string, number>
  generated_at: string
}

type CountryFilter =
  | 'all'
  | 'usa'
  | 'japan'
  | 'eurozone'
  | 'uk'
  | 'china'
  | 'canada'
  | 'australia'
  | 'newzealand'
  | 'switzerland'

const COUNTRY_ORDER: { value: CountryFilter; label: string }[] = [
  { value: 'all', label: 'すべて' },
  { value: 'usa', label: '米国' },
  { value: 'japan', label: '日本' },
  { value: 'eurozone', label: 'ユーロ圏' },
  { value: 'uk', label: '英国' },
  { value: 'china', label: '中国' },
  { value: 'canada', label: 'カナダ' },
  { value: 'australia', label: '豪州' },
  { value: 'newzealand', label: 'NZ' },
  { value: 'switzerland', label: 'スイス' },
]

const MAX_DISPLAY = 30

function formatRelativeTime(iso: string): string {
  try {
    const diffMs = Date.now() - new Date(iso).getTime()
    const sec = Math.floor(diffMs / 1000)
    if (sec < 60) return 'たった今'
    const min = Math.floor(sec / 60)
    if (min < 60) return `${min}分前`
    const hr = Math.floor(min / 60)
    if (hr < 24) return `${hr}時間前`
    const day = Math.floor(hr / 24)
    if (day < 30) return `${day}日前`
    const month = Math.floor(day / 30)
    if (month < 12) return `${month}ヶ月前`
    return `${Math.floor(month / 12)}年前`
  } catch {
    return '-'
  }
}

function RecentUpdatesCard() {
  const [data, setData] = useState<RecentUpdatesResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [country, setCountry] = useState<CountryFilter>('all')
  const [showAll, setShowAll] = useState(false)

  useEffect(() => {
    let cancelled = false
    const fetchData = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await axios.get<RecentUpdatesResponse>('/api/dashboard/recent-updates', {
          params: { country, limit: 200 },
        })
        if (!cancelled) setData(res.data)
      } catch (e) {
        console.error('Failed to fetch recent updates:', e)
        if (!cancelled) setError('直近更新情報の取得に失敗しました')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchData()
    return () => {
      cancelled = true
    }
  }, [country])

  // 表示件数を制限
  const displayEntries = useMemo(() => {
    if (!data) return []
    return showAll ? data.updates : data.updates.slice(0, MAX_DISPLAY)
  }, [data, showAll])

  // 国別カウント (タブのバッジ用)
  const countryOptions = useMemo(() => {
    const counts = data?.counts_by_country ?? {}
    return COUNTRY_ORDER.map((opt) => {
      if (opt.value === 'all') {
        const total = Object.values(counts).reduce((a, b) => a + b, 0)
        return {
          value: opt.value,
          label: total > 0 ? `${opt.label} (${total})` : opt.label,
        }
      }
      const c = counts[opt.value] ?? 0
      return {
        value: opt.value,
        label: c > 0 ? `${opt.label} (${c})` : opt.label,
      }
    })
  }, [data])

  return (
    <Card
      style={{
        background: colors.bgSecondary,
        border: `1px solid ${colors.border}`,
      }}
      styles={{ body: { padding: 16 } }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 12,
          flexWrap: 'wrap',
          gap: 8,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ReloadOutlined style={{ color: colors.accent }} />
          <Text strong style={{ color: colors.textPrimary, fontSize: 14 }}>
            直近更新された指標
          </Text>
          <Text style={{ color: colors.textTertiary, fontSize: 11 }}>
            (最終更新時刻のみ・値の表示は段階的に追加予定)
          </Text>
        </div>
      </div>

      <div style={{ marginBottom: 12, overflowX: 'auto' }}>
        <Segmented
          value={country}
          onChange={(v) => {
            setCountry(v as CountryFilter)
            setShowAll(false)
          }}
          options={countryOptions}
          size="small"
        />
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: '32px 0' }}>
          <Spin />
        </div>
      )}

      {error && !loading && (
        <Alert type="error" showIcon message={error} style={{ marginBottom: 12 }} />
      )}

      {!loading && !error && data && displayEntries.length === 0 && (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <Text style={{ color: colors.textTertiary, fontSize: 12 }}>
              該当する更新情報がありません
            </Text>
          }
          style={{ margin: '16px 0' }}
        />
      )}

      {!loading && !error && displayEntries.length > 0 && (
        <>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
              gap: 6,
            }}
          >
            {displayEntries.map((entry) => {
              const catStyle = CATEGORY_STYLE[entry.category] ?? DEFAULT_CATEGORY_STYLE
              const to = entry.route
                ? `${entry.route}${entry.anchor ? `#${entry.anchor}` : ''}`
                : undefined
              const rowContent = (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '8px 12px',
                    background: colors.bgTertiary,
                    borderRadius: 6,
                    fontSize: 13,
                    cursor: to ? 'pointer' : 'default',
                    border: `1px solid transparent`,
                    transition: 'border-color 0.15s ease',
                  }}
                  title={`${entry.country_label} / ${entry.category_label} / ${entry.indicator_id}`}
                  onMouseEnter={(e) => {
                    if (to) e.currentTarget.style.borderColor = colors.accent
                  }}
                  onMouseLeave={(e) => {
                    if (to) e.currentTarget.style.borderColor = 'transparent'
                  }}
                >
                  {entry.country_iso && (
                    <span
                      className={`fi fi-${entry.country_iso}`}
                      style={{ fontSize: 14, borderRadius: 2, flexShrink: 0 }}
                    />
                  )}
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                      minWidth: 74,
                      flexShrink: 0,
                    }}
                  >
                    <span style={{ color: catStyle.color, fontSize: 13, display: 'inline-flex' }}>
                      {catStyle.icon}
                    </span>
                    <Text style={{ color: colors.textTertiary, fontSize: 11 }}>
                      {entry.category_label}
                    </Text>
                  </span>
                  <Text
                    style={{
                      color: colors.textPrimary,
                      fontSize: 13,
                      flex: 1,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {entry.indicator_label}
                  </Text>
                  <Text
                    style={{
                      color: colors.textTertiary,
                      fontSize: 11,
                      whiteSpace: 'nowrap',
                      flexShrink: 0,
                    }}
                  >
                    {formatRelativeTime(entry.last_updated)}
                  </Text>
                </div>
              )
              const rowKey = `${entry.country}-${entry.category}-${entry.indicator_id}`
              return to ? (
                <Link key={rowKey} to={to} style={{ textDecoration: 'none' }}>
                  {rowContent}
                </Link>
              ) : (
                <div key={rowKey}>{rowContent}</div>
              )
            })}
          </div>

          {data && data.updates.length > MAX_DISPLAY && (
            <div style={{ textAlign: 'center', marginTop: 12 }}>
              <a
                onClick={(e) => {
                  e.preventDefault()
                  setShowAll((v) => !v)
                }}
                style={{
                  color: colors.accent,
                  fontSize: 12,
                  cursor: 'pointer',
                }}
              >
                {showAll
                  ? '折りたたむ'
                  : `もっと見る (全 ${data.updates.length} 件)`}
              </a>
            </div>
          )}
        </>
      )}
    </Card>
  )
}

export default RecentUpdatesCard
