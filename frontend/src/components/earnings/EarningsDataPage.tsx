/**
 * EarningsDataPage
 * 各国の決算データ:
 *   - 企業一覧 (左パネル)
 *   - 選択企業の財務詳細: IS/CF/BS merged 8四半期 + IRリンク (右パネル)
 */
import { useEffect, useState } from 'react'
import { Typography, Alert, Spin, Tag, Select } from 'antd'
import {
  BarChartOutlined,
  LinkOutlined,
  BankOutlined,
  ExperimentOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { getEarningsCountry } from '../../constants/earningsData'
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
interface FinancialPeriod {
  date: string
  period: string
  fiscal_year: string
  reported_currency: string
  // IS
  revenue: number | null
  gross_profit: number | null
  operating_income: number | null
  net_income: number | null
  eps_diluted: number | null
  gross_margin: number | null
  operating_margin: number | null
  net_margin: number | null
  // CF
  operating_cf: number | null
  fcf: number | null
  capex: number | null
  buyback: number | null
  dividends_paid: number | null
  fcf_margin: number | null
  depreciation_amortization: number | null
  // YoY
  revenue_yoy: number | null
  eps_yoy: number | null
  // Bank
  net_interest_income?: number | null
  interest_income?: number | null
  interest_expense?: number | null
  total_assets?: number | null
  total_equity?: number | null
  // Tech
  rd_expenses?: number | null
  stock_based_comp?: number | null
  // Energy
  total_debt?: number | null
  cash_equivalents?: number | null
}

interface FinancialsResponse {
  ticker: string
  name: string
  tier: string
  sector: string
  country_code: string
  country_name: string
  reported_currency: string
  periods: FinancialPeriod[]
  ir_home: string
  ir_results: string
  ir_tdnet: string
  ir_notes: string
  last_updated: string | null
  cached: boolean
  status: string
}

// -----------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------
const TIER_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  S: { bg: '#fef9c320', border: '#fde04780', text: '#fde047' },
  A: { bg: '#e0f2fe20', border: '#7dd3fc80', text: '#7dd3fc' },
  B: { bg: '#f1f5f920', border: '#94a3b880', text: '#94a3b8' },
}
function TierBadge({ tier }: { tier: string }) {
  const s = TIER_COLORS[tier] ?? TIER_COLORS['B']
  return (
    <span style={{
      display: 'inline-block', padding: '0 5px', borderRadius: 4,
      fontSize: 10, fontWeight: 700,
      background: s.bg, border: `1px solid ${s.border}`, color: s.text, lineHeight: '17px',
    }}>
      {tier}
    </span>
  )
}

function fmt(v: number | null | undefined, decimals = 2): string {
  if (v == null) return '—'
  return v.toFixed(decimals)
}
function fmtB(v: number | null | undefined): string {
  if (v == null) return '—'
  const abs = Math.abs(v)
  if (abs >= 1e12) return `${(v / 1e12).toFixed(2)}T`
  if (abs >= 1e9)  return `${(v / 1e9).toFixed(2)}B`
  if (abs >= 1e6)  return `${(v / 1e6).toFixed(1)}M`
  return v.toFixed(0)
}
function fmtPct(v: number | null | undefined): string {
  if (v == null) return '—'
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
}
function colorYoy(v: number | null | undefined): string {
  if (v == null) return colors.textSecondary
  return v > 0 ? '#10b981' : v < 0 ? '#ef4444' : colors.textSecondary
}
function colorMargin(v: number | null | undefined): string {
  if (v == null) return colors.textSecondary
  return v > 0 ? colors.textPrimary : '#ef4444'
}

const SECTOR_LABELS: Record<string, { label: string; icon: React.ReactNode }> = {
  bank:    { label: '銀行・保険',      icon: <BankOutlined /> },
  tech:    { label: '半導体・テック',   icon: <ExperimentOutlined /> },
  energy:  { label: '資源・エネルギー', icon: <ThunderboltOutlined /> },
  default: { label: '一般',            icon: <BarChartOutlined /> },
}

// -----------------------------------------------------------------------
// Cell helpers
// -----------------------------------------------------------------------
function Cell({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return (
    <td style={{
      padding: '6px 10px',
      borderBottom: `1px solid ${colors.border}`,
      textAlign: right ? 'right' : 'left',
      fontSize: 12,
      color: colors.textSecondary,
      whiteSpace: 'nowrap',
    }}>
      {children}
    </td>
  )
}
function HeaderCell({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return (
    <th style={{
      padding: '7px 10px',
      borderBottom: `1px solid ${colors.border}`,
      textAlign: right ? 'right' : 'left',
      fontSize: 11,
      fontWeight: 700,
      color: colors.textSecondary,
      background: '#0f172a',
      whiteSpace: 'nowrap',
      position: 'sticky',
      top: 0,
      zIndex: 2,
    }}>
      {children}
    </th>
  )
}

// -----------------------------------------------------------------------
// Period label
// -----------------------------------------------------------------------
function periodLabel(p: FinancialPeriod): string {
  if (!p.period) return p.date.slice(0, 7)
  return `${p.fiscal_year || p.date.slice(0, 4)} ${p.period}`
}

// -----------------------------------------------------------------------
// Financial table
// -----------------------------------------------------------------------
function FinancialTable({ periods, sector, currency }: {
  periods: FinancialPeriod[]
  sector: string
  currency: string
}) {
  const cur = currency || 'USD'

  type RowDef = {
    label: string
    render: (p: FinancialPeriod) => React.ReactNode
    section?: boolean
  }

  const rows: RowDef[] = [
    { label: '── 損益計算書 ──', render: () => null, section: true },
    {
      label: `売上高 (${cur})`,
      render: (p) => (
        <span style={{ color: colors.textPrimary, fontWeight: 500 }}>{fmtB(p.revenue)}</span>
      ),
    },
    {
      label: '売上YoY',
      render: (p) => <span style={{ color: colorYoy(p.revenue_yoy) }}>{fmtPct(p.revenue_yoy)}</span>,
    },
    {
      label: `粗利益 (${cur})`,
      render: (p) => <span style={{ color: colors.textPrimary }}>{fmtB(p.gross_profit)}</span>,
    },
    {
      label: '粗利率',
      render: (p) => <span style={{ color: colorMargin(p.gross_margin) }}>{fmt(p.gross_margin, 1)}%</span>,
    },
    {
      label: `営業利益 (${cur})`,
      render: (p) => <span style={{ color: colors.textPrimary }}>{fmtB(p.operating_income)}</span>,
    },
    {
      label: '営業利益率',
      render: (p) => <span style={{ color: colorMargin(p.operating_margin) }}>{fmt(p.operating_margin, 1)}%</span>,
    },
    {
      label: `純利益 (${cur})`,
      render: (p) => <span style={{ color: colors.textPrimary }}>{fmtB(p.net_income)}</span>,
    },
    {
      label: '純利益率',
      render: (p) => <span style={{ color: colorMargin(p.net_margin) }}>{fmt(p.net_margin, 1)}%</span>,
    },
    {
      label: 'EPS (希薄化後)',
      render: (p) => <span style={{ color: colors.textPrimary, fontWeight: 500 }}>{fmt(p.eps_diluted)}</span>,
    },
    {
      label: 'EPS YoY',
      render: (p) => <span style={{ color: colorYoy(p.eps_yoy) }}>{fmtPct(p.eps_yoy)}</span>,
    },
    { label: '── キャッシュフロー ──', render: () => null, section: true },
    {
      label: `営業CF (${cur})`,
      render: (p) => <span style={{ color: p.operating_cf != null && p.operating_cf > 0 ? '#10b981' : '#ef4444' }}>{fmtB(p.operating_cf)}</span>,
    },
    {
      label: `FCF (${cur})`,
      render: (p) => <span style={{ color: p.fcf != null && p.fcf > 0 ? '#10b981' : '#ef4444' }}>{fmtB(p.fcf)}</span>,
    },
    {
      label: 'FCF マージン',
      render: (p) => <span style={{ color: colorMargin(p.fcf_margin) }}>{fmt(p.fcf_margin, 1)}%</span>,
    },
    {
      label: `CapEx (${cur})`,
      render: (p) => <span style={{ color: colors.textSecondary }}>{fmtB(p.capex)}</span>,
    },
    {
      label: `自社株買い (${cur})`,
      render: (p) => {
        const v = p.buyback
        if (v == null) return <span style={{ color: colors.textSecondary }}>—</span>
        const abs = Math.abs(v)
        return <span style={{ color: '#a78bfa' }}>{fmtB(abs)}</span>
      },
    },
    {
      label: `配当支払 (${cur})`,
      render: (p) => {
        const v = p.dividends_paid
        if (v == null) return <span style={{ color: colors.textSecondary }}>—</span>
        return <span style={{ color: '#f59e0b' }}>{fmtB(Math.abs(v))}</span>
      },
    },
    {
      label: `D&A (${cur})`,
      render: (p) => <span style={{ color: colors.textSecondary }}>{fmtB(p.depreciation_amortization)}</span>,
    },
  ]

  // Sector-specific rows
  if (sector === 'bank') {
    rows.push(
      { label: '── 銀行指標 ──', render: () => null, section: true },
      { label: `純金利収益 (${cur})`, render: (p) => <span style={{ color: colors.textPrimary }}>{fmtB(p.net_interest_income)}</span> },
      { label: `受取利息 (${cur})`,  render: (p) => <span style={{ color: colors.textSecondary }}>{fmtB(p.interest_income)}</span> },
      { label: `支払利息 (${cur})`,  render: (p) => <span style={{ color: '#ef4444' }}>{fmtB(p.interest_expense)}</span> },
      { label: `総資産 (${cur})`,    render: (p) => <span style={{ color: colors.textPrimary }}>{fmtB(p.total_assets)}</span> },
      { label: `自己資本 (${cur})`,  render: (p) => <span style={{ color: colors.textPrimary }}>{fmtB(p.total_equity)}</span> },
    )
  } else if (sector === 'tech') {
    rows.push(
      { label: '── テック指標 ──', render: () => null, section: true },
      { label: `R&D費用 (${cur})`,   render: (p) => <span style={{ color: '#60a5fa' }}>{fmtB(p.rd_expenses)}</span> },
      { label: `株式報酬 (${cur})`,  render: (p) => <span style={{ color: colors.textSecondary }}>{fmtB(p.stock_based_comp)}</span> },
    )
  } else if (sector === 'energy') {
    rows.push(
      { label: '── 資源・エネルギー指標 ──', render: () => null, section: true },
      { label: `有利子負債 (${cur})`, render: (p) => <span style={{ color: '#f87171' }}>{fmtB(p.total_debt)}</span> },
      { label: `現金・同等物 (${cur})`, render: (p) => <span style={{ color: '#34d399' }}>{fmtB(p.cash_equivalents)}</span> },
    )
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr>
            <HeaderCell>指標</HeaderCell>
            {periods.map((p) => (
              <HeaderCell key={p.date} right>
                {periodLabel(p)}
              </HeaderCell>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            row.section ? (
              <tr key={i}>
                <td colSpan={periods.length + 1} style={{
                  padding: '8px 10px 4px',
                  fontSize: 10,
                  fontWeight: 700,
                  color: colors.accent,
                  background: '#0f172a',
                  letterSpacing: '0.05em',
                }}>
                  {row.label}
                </td>
              </tr>
            ) : (
              <tr key={i} style={{ background: i % 2 === 0 ? '#1e293b' : '#111827' }}>
                <Cell>{row.label}</Cell>
                {periods.map((p) => (
                  <Cell key={p.date} right>{row.render(p)}</Cell>
                ))}
              </tr>
            )
          ))}
        </tbody>
      </table>
    </div>
  )
}

// -----------------------------------------------------------------------
// IR Links panel
// -----------------------------------------------------------------------
function IRLinks({ data }: { data: FinancialsResponse }) {
  const links = [
    { label: 'IR ホーム', url: data.ir_home },
    { label: '決算資料', url: data.ir_results },
    { label: 'TDnet',    url: data.ir_tdnet },
  ].filter((l) => l.url)

  if (links.length === 0) return null

  return (
    <div style={{
      display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center',
      padding: '10px 16px',
      background: colors.bgSecondary,
      border: `1px solid ${colors.border}`,
      borderRadius: 8,
      marginBottom: 16,
    }}>
      <LinkOutlined style={{ color: colors.accent, fontSize: 13 }} />
      <Text style={{ color: colors.textSecondary, fontSize: 12 }}>IR:</Text>
      {links.map((l) => (
        <a
          key={l.label}
          href={l.url}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            color: '#60a5fa',
            fontSize: 12,
            textDecoration: 'none',
            border: `1px solid #3b82f640`,
            borderRadius: 4,
            padding: '2px 8px',
          }}
        >
          {l.label} ↗
        </a>
      ))}
      {data.ir_notes && (
        <Text style={{ color: colors.textSecondary, fontSize: 11, marginLeft: 4 }}>
          ({data.ir_notes})
        </Text>
      )}
    </div>
  )
}

// -----------------------------------------------------------------------
// Company list (left panel)
// -----------------------------------------------------------------------
function CompanyList({
  companies,
  selectedTicker,
  onSelect,
}: {
  companies: EarningsCompany[]
  selectedTicker: string | null
  onSelect: (ticker: string) => void
}) {
  return (
    <div style={{
      width: 200, flexShrink: 0,
      background: colors.bgSecondary,
      border: `1px solid ${colors.border}`,
      borderRadius: 8,
      overflow: 'hidden',
    }}>
      <div style={{
        padding: '10px 12px',
        borderBottom: `1px solid ${colors.border}`,
        background: '#0f172a',
      }}>
        <Text style={{ color: colors.textSecondary, fontSize: 11, fontWeight: 700, letterSpacing: '0.06em' }}>
          対象企業
        </Text>
      </div>
      <div style={{ overflowY: 'auto', maxHeight: 600 }}>
        {companies.map((comp) => {
          const isSelected = comp.ticker === selectedTicker
          return (
            <div
              key={comp.ticker}
              onClick={() => onSelect(comp.ticker)}
              style={{
                padding: '8px 12px',
                cursor: 'pointer',
                background: isSelected ? '#10b98120' : 'transparent',
                borderLeft: `3px solid ${isSelected ? colors.accent : 'transparent'}`,
                borderBottom: `1px solid ${colors.border}`,
                transition: 'background 0.1s',
              }}
              onMouseEnter={(e) => {
                if (!isSelected) (e.currentTarget as HTMLDivElement).style.background = '#1e293b'
              }}
              onMouseLeave={(e) => {
                if (!isSelected) (e.currentTarget as HTMLDivElement).style.background = 'transparent'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <TierBadge tier={comp.tier} />
                <Text style={{ color: isSelected ? colors.accent : colors.textPrimary, fontSize: 12, fontWeight: isSelected ? 600 : 400 }}>
                  {comp.name}
                </Text>
              </div>
              <Text style={{ color: colors.textSecondary, fontSize: 10 }}>{comp.ticker}</Text>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// -----------------------------------------------------------------------
// Detail panel (right)
// -----------------------------------------------------------------------
function DetailPanel({ countryCode, ticker }: { countryCode: string; ticker: string }) {
  const [data, setData] = useState<FinancialsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [periodCount, setPeriodCount] = useState<number>(8)

  useEffect(() => {
    setLoading(true)
    setError(null)
    setData(null)
    fetch(`/api/earnings/${countryCode}/${encodeURIComponent(ticker)}/financials`)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then((json: FinancialsResponse) => { setData(json); setLoading(false) })
      .catch((err) => { setError(err.message); setLoading(false) })
  }, [countryCode, ticker])

  if (loading) {
    return (
      <div style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
        <Spin size="large" />
      </div>
    )
  }
  if (error || !data) {
    return (
      <div style={{ flex: 1 }}>
        <Alert type="error" message="データ取得失敗" description={error ?? '不明なエラー'} showIcon />
      </div>
    )
  }

  const sectorInfo = SECTOR_LABELS[data.sector] ?? SECTOR_LABELS['default']
  const displayPeriods = data.periods.slice(0, periodCount)

  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      {/* ヘッダー */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        marginBottom: 12, flexWrap: 'wrap',
      }}>
        <TierBadge tier={data.tier} />
        <Title level={5} style={{ margin: 0, color: colors.textPrimary }}>
          {data.name}
        </Title>
        <Text style={{ color: colors.textSecondary, fontSize: 12 }}>({data.ticker})</Text>
        <Tag color="default" style={{ fontSize: 10, display: 'flex', alignItems: 'center', gap: 4 }}>
          {sectorInfo.icon} {sectorInfo.label}
        </Tag>
        {data.reported_currency && (
          <Tag color="blue" style={{ fontSize: 10 }}>{data.reported_currency}</Tag>
        )}
        {data.cached && <Tag color="green" style={{ fontSize: 10 }}>キャッシュ</Tag>}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
          <Text style={{ color: colors.textSecondary, fontSize: 11 }}>表示期間:</Text>
          <Select
            value={periodCount}
            onChange={setPeriodCount}
            size="small"
            style={{ width: 70 }}
            options={[
              { value: 4,  label: '4Q' },
              { value: 8,  label: '8Q' },
            ]}
          />
        </div>
      </div>

      {/* IRリンク */}
      <IRLinks data={data} />

      {/* 財務テーブル */}
      {displayPeriods.length === 0 ? (
        <Alert type="warning" message="財務データなし"
          description="FMP APIから財務データを取得できませんでした。ティッカーがFMPでサポートされていない可能性があります。" showIcon />
      ) : (
        <div style={{
          background: colors.bgSecondary,
          border: `1px solid ${colors.border}`,
          borderRadius: 8,
          overflow: 'hidden',
        }}>
          <FinancialTable periods={displayPeriods} sector={data.sector} currency={data.reported_currency} />
        </div>
      )}

      {data.last_updated && (
        <Text style={{ color: colors.textSecondary, fontSize: 11, display: 'block', marginTop: 8, textAlign: 'right' }}>
          更新: {new Date(data.last_updated).toLocaleString('ja-JP')}
        </Text>
      )}
    </div>
  )
}

// -----------------------------------------------------------------------
// Main
// -----------------------------------------------------------------------
interface Props {
  countryCode: string
}

export default function EarningsDataPage({ countryCode }: Props) {
  const country = getEarningsCountry(countryCode)
  const companies: EarningsCompany[] = country?.companies ?? []

  const [selectedTicker, setSelectedTicker] = useState<string | null>(
    companies.length > 0 ? companies[0].ticker : null
  )

  // countryCode が変わったら先頭銘柄をリセット
  useEffect(() => {
    setSelectedTicker(companies.length > 0 ? companies[0].ticker : null)
  }, [countryCode])

  if (!country) {
    return <Alert type="error" message={`国コード "${countryCode}" は未対応です`} showIcon />
  }

  return (
    <div>
      {/* ページヘッダー */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
        <span style={{ fontSize: 24 }}>{country.flag}</span>
        <Title level={4} style={{ margin: 0, color: colors.textPrimary }}>
          {country.nameJa} — 決算データ
        </Title>
        <Text style={{ color: colors.textSecondary, fontSize: 13 }}>
          ({companies.length} 社)
        </Text>
      </div>

      {/* 2-column layout */}
      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
        <CompanyList
          companies={companies}
          selectedTicker={selectedTicker}
          onSelect={setSelectedTicker}
        />
        {selectedTicker ? (
          <DetailPanel key={selectedTicker} countryCode={countryCode} ticker={selectedTicker} />
        ) : (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 200 }}>
            <Text style={{ color: colors.textSecondary }}>企業を選択してください</Text>
          </div>
        )}
      </div>
    </div>
  )
}
