/**
 * Treasury Quarterly Refunding コンポーネント
 *
 * 米財務省四半期リファンディング関連文書を表示
 * - 概要: Policy Statement メトリクス + Auction Size Table
 * - 借入見込み: Financing Estimates
 * - 入札予定: Auction Schedule (テーブル)
 * - 買入予定: Buyback Schedule (テーブル)
 * - TBAC: Report / Minutes テキスト + 原文リンク
 *
 * standalone: 自前useQueryで /api/usa/quarterly-refunding から取得
 */

import { useMemo, useState } from 'react'
import { Tabs, Table, Card, Tag, Segmented, Typography, Collapse } from 'antd'
import { LinkOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import ChartContainer from '../../../common/ChartContainer'
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../../usa/common/chartConstants'

const { Text, Paragraph } = Typography

// =============================================================================
// 色定義
// =============================================================================
const COLORS = {
  blue: '#3b82f6',
  green: '#10b981',
  amber: '#f59e0b',
  red: '#ef4444',
  purple: '#8b5cf6',
  cyan: '#06b6d4',
  slate: '#94a3b8',
}

// =============================================================================
// 型定義
// =============================================================================
interface MetricItem {
  value: number | null
  unit: string | null
  label: string | null
}

interface EventData {
  published_at: string | null
  title: string | null
  source_url: string
  raw_text?: string
  metrics: Record<string, MetricItem>
  auction_size_table?: AuctionSizeRow[]
  bill_guidance?: string | null
  tips_guidance?: string | null
  buyback_guidance?: string | null
}

interface AuctionSizeRow {
  month: string
  '2y'?: number
  '3y'?: number
  '5y'?: number
  '7y'?: number
  '10y'?: number
  '20y'?: number
  '30y'?: number
  frn?: number
}

interface AuctionScheduleItem {
  security_term: string
  security_type: string
  reopening: boolean
  is_tips: boolean
  is_frn: boolean
  announcement_date: string | null
  auction_date: string | null
  settlement_date: string | null
  source_url: string | null
}

interface BuybackScheduleItem {
  purchase_bucket: string
  security_type: string
  operation_type: string
  min_amount: number | null
  max_amount: number | null
  maturity_range_start: string | null
  maturity_range_end: string | null
  announcement_date: string | null
  operation_date: string | null
  settlement_date: string | null
  source_url: string | null
}

interface QRResponse {
  quarter_label: string | null
  next_release: string | null
  events: Record<string, EventData>
  auction_schedule: AuctionScheduleItem[]
  buyback_schedule: BuybackScheduleItem[]
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

// =============================================================================
// データ取得フック
// =============================================================================
function useQuarterlyRefundingData() {
  return useQuery({
    queryKey: ['usa', 'quarterly-refunding'],
    queryFn: async () => {
      const { data } = await axios.get<QRResponse>('/api/usa/quarterly-refunding')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

// =============================================================================
// ヘルパー
// =============================================================================
function formatBillions(value: number | null | undefined): string {
  if (value == null) return '—'
  return `$${value}B`
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  } catch {
    return dateStr
  }
}

function formatMonthLabel(monthStr: string): string {
  // "2026-02" → "Feb-26"
  const [year, month] = monthStr.split('-')
  const months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  return `${months[parseInt(month)]}-${year.slice(2)}`
}

function metricValue(events: Record<string, EventData>, docType: string, key: string): number | null {
  return events?.[docType]?.metrics?.[key]?.value ?? null
}

// =============================================================================
// Overview タブ
// =============================================================================
function OverviewTab({ events }: { events: Record<string, EventData> }) {
  const ps = events?.policy_statement
  if (!ps) return <div style={{ color: TEXT_COLORS.secondary, padding: 40, textAlign: 'center' }}>Policy Statement データなし</div>

  const metrics = ps.metrics || {}

  // Auction Size Table
  const auctionSizeColumns = [
    { title: 'Month', dataIndex: 'month', key: 'month', render: (v: string) => formatMonthLabel(v), width: 80 },
    ...(['2y', '3y', '5y', '7y', '10y', '20y', '30y', 'frn'] as const).map((t) => ({
      title: t.toUpperCase(),
      dataIndex: t,
      key: t,
      width: 65,
      render: (v: number | undefined) => v != null ? `${v}` : '—',
    })),
  ]

  return (
    <div>
      {/* メトリクスカード群 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 16 }}>
        <MetricCard label="Total Offering" value={formatBillions(metrics.refunding_total?.value)} color={COLORS.blue} />
        <MetricCard label="New Cash Raised" value={formatBillions(metrics.new_cash_raised?.value)} color={COLORS.green} />
        <MetricCard label="Maturing Securities" value={formatBillions(metrics.maturing_securities?.value)} color={COLORS.slate} />
        <MetricCard label="3-Year Note" value={formatBillions(metrics.refunding_3y?.value)} color={COLORS.cyan} />
        <MetricCard label="10-Year Note" value={formatBillions(metrics.refunding_10y?.value)} color={COLORS.amber} />
        <MetricCard label="30-Year Bond" value={formatBillions(metrics.refunding_30y?.value)} color={COLORS.red} />
        <MetricCard label="Buyback (Liquidity)" value={formatBillions(metrics.buyback_liquidity_max?.value)} color={COLORS.purple} />
        <MetricCard label="Buyback (Cash Mgmt)" value={formatBillions(metrics.buyback_cash_mgmt_max?.value)} color={COLORS.purple} />
      </div>

      {/* Auction Size Table */}
      {ps.auction_size_table && ps.auction_size_table.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <Text strong style={{ color: TEXT_COLORS.primary, fontSize: 14, marginBottom: 8, display: 'block' }}>
            Auction Sizes ($B)
          </Text>
          <Table
            dataSource={ps.auction_size_table}
            columns={auctionSizeColumns}
            rowKey="month"
            pagination={false}
            size="small"
            bordered
            style={{ background: '#1e293b' }}
          />
        </div>
      )}

      {/* Guidance テキスト */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {ps.bill_guidance && (
          <GuidanceCard title="Bill Guidance" text={ps.bill_guidance} />
        )}
        {ps.tips_guidance && (
          <GuidanceCard title="TIPS Guidance" text={ps.tips_guidance} />
        )}
        {ps.buyback_guidance && (
          <GuidanceCard title="Buyback Guidance" text={ps.buyback_guidance} />
        )}
      </div>

      {/* 原文リンク */}
      <div style={{ marginTop: 12 }}>
        <a href={ps.source_url} target="_blank" rel="noopener noreferrer" style={{ color: COLORS.blue, fontSize: 13 }}>
          <LinkOutlined /> Policy Statement 原文
        </a>
      </div>
    </div>
  )
}

// =============================================================================
// Borrowing Estimates タブ
// =============================================================================
function BorrowingEstimatesTab({ events }: { events: Record<string, EventData> }) {
  const fe = events?.financing_estimates
  if (!fe) return <div style={{ color: TEXT_COLORS.secondary, padding: 40, textAlign: 'center' }}>Financing Estimates データなし</div>

  const m = fe.metrics || {}

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12, marginBottom: 16 }}>
        <MetricCard
          label="Current Qtr Borrowing"
          value={formatBillions(m.borrowing_estimate_current_qtr?.value)}
          color={COLORS.blue}
          sublabel={m.borrowing_estimate_current_qtr?.label || undefined}
        />
        <MetricCard
          label="Next Qtr Borrowing"
          value={formatBillions(m.borrowing_estimate_next_qtr?.value)}
          color={COLORS.cyan}
          sublabel={m.borrowing_estimate_next_qtr?.label || undefined}
        />
        <MetricCard
          label="Current Qtr End Cash"
          value={formatBillions(m.assumed_end_cash_balance_current_qtr?.value)}
          color={COLORS.green}
        />
        <MetricCard
          label="Next Qtr End Cash"
          value={formatBillions(m.assumed_end_cash_balance_next_qtr?.value)}
          color={COLORS.green}
        />
        <MetricCard
          label="Prev Qtr Actual"
          value={formatBillions(m.actual_borrowing_prev_qtr?.value)}
          color={COLORS.slate}
        />
        <MetricCard
          label="Previous Estimate"
          value={formatBillions(m.prev_estimate_current_qtr?.value)}
          color={COLORS.amber}
        />
      </div>

      {/* 差分表示 */}
      {m.borrowing_estimate_current_qtr?.value != null && m.prev_estimate_current_qtr?.value != null && (
        <div style={{ padding: '8px 12px', background: '#1e293b', borderRadius: 6, marginBottom: 12 }}>
          <Text style={{ color: TEXT_COLORS.secondary, fontSize: 13 }}>
            Current vs Previous Estimate: {' '}
            <span style={{ color: (m.borrowing_estimate_current_qtr.value! - m.prev_estimate_current_qtr.value!) < 0 ? COLORS.green : COLORS.red, fontWeight: 600 }}>
              {m.borrowing_estimate_current_qtr.value! - m.prev_estimate_current_qtr.value! > 0 ? '+' : ''}
              ${(m.borrowing_estimate_current_qtr.value! - m.prev_estimate_current_qtr.value!).toFixed(0)}B
            </span>
          </Text>
        </div>
      )}

      <a href={fe.source_url} target="_blank" rel="noopener noreferrer" style={{ color: COLORS.blue, fontSize: 13 }}>
        <LinkOutlined /> Financing Estimates 原文
      </a>
    </div>
  )
}

// =============================================================================
// Auction Schedule タブ
// =============================================================================
function AuctionScheduleTab({ data }: { data: AuctionScheduleItem[] }) {
  const [filter, setFilter] = useState<string>('ALL')

  const filtered = useMemo(() => {
    if (filter === 'ALL') return data
    return data.filter((d) => d.security_type === filter)
  }, [data, filter])

  const columns = [
    { title: 'Security', dataIndex: 'security_term', key: 'term', width: 100 },
    {
      title: 'Type', dataIndex: 'security_type', key: 'type', width: 70,
      render: (v: string, r: AuctionScheduleItem) => {
        let color = 'default'
        if (v === 'NOTE') color = 'blue'
        if (v === 'BOND') color = 'gold'
        if (v === 'BILL') color = 'green'
        return (
          <span>
            <Tag color={color}>{v}</Tag>
            {r.is_tips && <Tag color="purple">TIPS</Tag>}
            {r.is_frn && <Tag color="cyan">FRN</Tag>}
            {r.reopening && <Tag>Reopen</Tag>}
          </span>
        )
      },
    },
    { title: 'Announce', dataIndex: 'announcement_date', key: 'ann', width: 100, render: formatDate },
    { title: 'Auction', dataIndex: 'auction_date', key: 'auc', width: 100, render: formatDate },
    { title: 'Settlement', dataIndex: 'settlement_date', key: 'set', width: 100, render: formatDate },
  ]

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Segmented
          options={['ALL', 'BILL', 'NOTE', 'BOND']}
          value={filter}
          onChange={(v) => setFilter(v as string)}
          size="small"
        />
      </div>
      <Table
        dataSource={filtered}
        columns={columns}
        rowKey={(r) => `${r.security_term}-${r.auction_date}`}
        pagination={false}
        size="small"
        scroll={{ y: 500 }}
        bordered
      />
    </div>
  )
}

// =============================================================================
// Buyback Schedule タブ
// =============================================================================
function BuybackScheduleTab({ data }: { data: BuybackScheduleItem[] }) {
  const columns = [
    { title: 'Bucket', dataIndex: 'purchase_bucket', key: 'bucket', width: 100 },
    {
      title: 'Type', dataIndex: 'security_type', key: 'type', width: 120,
      render: (v: string) => <Tag color={v === 'TIPS' ? 'purple' : 'blue'}>{v}</Tag>,
    },
    {
      title: 'Operation', dataIndex: 'operation_type', key: 'op', width: 130,
      render: (v: string) => <Tag color={v?.includes('Liquidity') ? 'green' : 'orange'}>{v}</Tag>,
    },
    {
      title: 'Amount ($B)', key: 'amount', width: 120,
      render: (_: unknown, r: BuybackScheduleItem) => {
        if (r.min_amount == null && r.max_amount == null) return '—'
        const fmt = (v: number) => `$${(v / 1_000_000_000).toFixed(1)}B`
        if (r.min_amount != null && r.max_amount != null) return `${fmt(r.min_amount)} – ${fmt(r.max_amount)}`
        if (r.max_amount != null) return `up to ${fmt(r.max_amount)}`
        return fmt(r.min_amount!)
      },
    },
    { title: 'Operation Date', dataIndex: 'operation_date', key: 'opdate', width: 110, render: formatDate },
    { title: 'Settlement', dataIndex: 'settlement_date', key: 'set', width: 110, render: formatDate },
  ]

  return (
    <Table
      dataSource={data}
      columns={columns}
      rowKey={(r) => `${r.purchase_bucket}-${r.operation_date}`}
      pagination={false}
      size="small"
      scroll={{ y: 500 }}
      bordered
    />
  )
}

// =============================================================================
// TBAC タブ
// =============================================================================
function TBACTab({ events }: { events: Record<string, EventData> }) {
  const report = events?.tbac_report
  const minutes = events?.tbac_minutes

  const items = []
  if (report) {
    items.push({
      key: 'report',
      label: 'TBAC Report',
      children: (
        <div>
          {report.raw_text ? (
            <Paragraph style={{ color: TEXT_COLORS.secondary, fontSize: 13, whiteSpace: 'pre-wrap', maxHeight: 400, overflow: 'auto' }}>
              {report.raw_text}
            </Paragraph>
          ) : (
            <Text style={{ color: TEXT_COLORS.secondary }}>テキスト未取得</Text>
          )}
          <a href={report.source_url} target="_blank" rel="noopener noreferrer" style={{ color: COLORS.blue, fontSize: 13 }}>
            <LinkOutlined /> TBAC Report 原文
          </a>
        </div>
      ),
    })
  }
  if (minutes) {
    items.push({
      key: 'minutes',
      label: 'TBAC Minutes',
      children: (
        <div>
          {minutes.raw_text ? (
            <Paragraph style={{ color: TEXT_COLORS.secondary, fontSize: 13, whiteSpace: 'pre-wrap', maxHeight: 400, overflow: 'auto' }}>
              {minutes.raw_text}
            </Paragraph>
          ) : (
            <Text style={{ color: TEXT_COLORS.secondary }}>テキスト未取得</Text>
          )}
          <a href={minutes.source_url} target="_blank" rel="noopener noreferrer" style={{ color: COLORS.blue, fontSize: 13 }}>
            <LinkOutlined /> TBAC Minutes 原文
          </a>
        </div>
      ),
    })
  }

  if (items.length === 0) {
    return <div style={{ color: TEXT_COLORS.secondary, padding: 40, textAlign: 'center' }}>TBAC データなし</div>
  }

  return <Collapse items={items} defaultActiveKey={['report']} />
}

// =============================================================================
// 共通コンポーネント
// =============================================================================
function MetricCard({ label, value, color, sublabel }: { label: string; value: string; color: string; sublabel?: string }) {
  return (
    <div style={{
      background: '#1e293b',
      borderRadius: 8,
      padding: '12px 16px',
      borderLeft: `3px solid ${color}`,
    }}>
      <div style={{ color: TEXT_COLORS.secondary, fontSize: 11, marginBottom: 4 }}>{label}</div>
      <div style={{ color, fontWeight: 700, fontSize: 20 }}>{value}</div>
      {sublabel && <div style={{ color: TEXT_COLORS.secondary, fontSize: 10, marginTop: 2 }}>{sublabel}</div>}
    </div>
  )
}

function GuidanceCard({ title, text }: { title: string; text: string }) {
  return (
    <Card size="small" title={<span style={{ color: TEXT_COLORS.primary, fontSize: 13 }}>{title}</span>} style={{ background: '#1e293b', border: '1px solid #334155' }}>
      <Paragraph style={{ color: TEXT_COLORS.secondary, fontSize: 12, margin: 0 }}>{text}</Paragraph>
    </Card>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================
export default function QuarterlyRefundingChart() {
  const { data: apiData, isLoading, error } = useQuarterlyRefundingData()

  if (isLoading) {
    return (
      <ChartContainer title="Quarterly Refunding（米財務省）" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (error || !apiData || !apiData.events || Object.keys(apiData.events).length === 0) {
    return (
      <ChartContainer title="Quarterly Refunding（米財務省）" showPeriodSelector={false}>
        <div style={{ color: TEXT_COLORS.secondary, textAlign: 'center', padding: 40 }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  const { events, auction_schedule, buyback_schedule, quarter_label, next_release } = apiData

  const tabItems = [
    {
      key: 'overview',
      label: '概要',
      children: <OverviewTab events={events} />,
    },
    {
      key: 'borrowing',
      label: '借入見込み',
      children: <BorrowingEstimatesTab events={events} />,
    },
    {
      key: 'auction',
      label: `入札予定 (${auction_schedule?.length || 0})`,
      children: <AuctionScheduleTab data={auction_schedule || []} />,
    },
    {
      key: 'buyback',
      label: `買入予定 (${buyback_schedule?.length || 0})`,
      children: <BuybackScheduleTab data={buyback_schedule || []} />,
    },
    {
      key: 'tbac',
      label: 'TBAC',
      children: <TBACTab events={events} />,
    },
  ]

  return (
    <ChartContainer
      title="Quarterly Refunding（米財務省）"
      dataSource="U.S. Department of the Treasury"
      sourceUrl="https://home.treasury.gov/policy-issues/financing-the-government/quarterly-refunding/most-recent-quarterly-refunding-documents"
      showPeriodSelector={false}
      handbookId="quarterly-refunding"
    >
      {/* ヘッダー: quarter_label + next_release */}
      <div style={LATEST_VALUE_BOX_STYLE}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          {quarter_label && (
            <span style={{ color: COLORS.blue, fontWeight: 700, fontSize: 20 }}>
              {quarter_label}
            </span>
          )}
          {next_release && (
            <span style={{ color: TEXT_COLORS.secondary, fontSize: 13 }}>
              次回: {formatDate(next_release)}
            </span>
          )}
          {events.policy_statement?.published_at && (
            <span style={{ color: TEXT_COLORS.secondary, fontSize: 13 }}>
              発表: {formatDate(events.policy_statement.published_at)}
            </span>
          )}
          {/* 主要数値 */}
          {metricValue(events, 'policy_statement', 'new_cash_raised') != null && (
            <span style={{ color: COLORS.green, fontWeight: 600, fontSize: 14 }}>
              New Cash {formatBillions(metricValue(events, 'policy_statement', 'new_cash_raised'))}
            </span>
          )}
          {metricValue(events, 'financing_estimates', 'borrowing_estimate_current_qtr') != null && (
            <span style={{ color: COLORS.amber, fontWeight: 600, fontSize: 14 }}>
              Borrowing Est. {formatBillions(metricValue(events, 'financing_estimates', 'borrowing_estimate_current_qtr'))}
            </span>
          )}
        </div>
      </div>

      <Tabs items={tabItems} defaultActiveKey="overview" size="small" />
    </ChartContainer>
  )
}
