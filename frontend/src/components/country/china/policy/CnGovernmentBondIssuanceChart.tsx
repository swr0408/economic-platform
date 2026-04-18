/**
 * 中国国債発行チャートコンポーネント
 *
 * 3タブ構成:
 * 1. 今後の入札予定（upcoming）- テーブル
 * 2. 直近の入札結果（recent_results）- テーブル
 * 3. 月次供給量（monthly_supply）- 棒グラフ
 *
 * データソース: 中国財政部 (MOF) https://zwgls.mof.gov.cn/ywgg/
 * FMPマッピング: なし
 */
import { useState, useEffect, useMemo } from 'react'
import { Button, Table, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import { useIsMaster } from '../../../../hooks/useIsMaster'
import { withVisibility } from '../../../common/withVisibility'

import {
  usePeriodFiltering,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardBarChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

// =============================================================================
// 型定義
// =============================================================================

interface UpcomingAuction {
  bond_name: string | null
  bond_type: string
  is_reissue: boolean
  maturity_years: number | null
  maturity_days: number | null
  issue_amount: number | null
  bidding_date: string | null
  bidding_time_start: string | null
  bidding_time_end: string | null
  bidding_method: string | null
  interest_start_date: string | null
  listing_date: string | null
  publish_date: string | null
}

interface RecentResult {
  notice_number: string | null
  bond_name: string | null
  bond_type: string
  is_reissue: boolean
  maturity_years: number | null
  maturity_days: number | null
  planned_amount: number | null
  actual_amount: number | null
  issue_price: number | null
  annual_yield: number | null
  coupon_rate: number | null
  interest_start_date: string | null
  redemption_date: string | null
  listing_date: string | null
  publish_date: string | null
}

interface MonthlySupply {
  date: string
  interest_bearing: number
  discount: number
  savings: number
  total: number
}

interface BondIssuanceApiResponse {
  upcoming: UpcomingAuction[]
  recent_results: RecentResult[]
  monthly_supply: MonthlySupply[]
  metadata: Record<string, unknown>
}

type ViewMode = 'upcoming' | 'results' | 'supply'

// =============================================================================
// カラー設定
// =============================================================================
const COLOR_INTEREST_BEARING = '#3b82f6'  // 青 - 附息国債
const COLOR_DISCOUNT = '#f97316'          // オレンジ - 贴现国債
const COLOR_SAVINGS = '#22c55e'           // 緑 - 储蓄国債

// =============================================================================
// ユーティリティ
// =============================================================================

const formatDateJP = (dateStr: string | null): string => {
  if (!dateStr) return '-'
  const [y, m, d] = dateStr.split('-')
  return `${y}/${m}/${d}`
}

const formatDateLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}/${month}`
}

const formatDateFull = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month, day] = dateStr.split('-')
  return `${year}年${parseInt(month)}月${parseInt(day)}日`
}

const bondTypeLabel = (type: string): { label: string; color: string } => {
  switch (type) {
    case 'interest_bearing': return { label: '附息', color: 'blue' }
    case 'discount': return { label: '贴现', color: 'orange' }
    case 'savings': return { label: '储蓄', color: 'green' }
    default: return { label: type, color: 'default' }
  }
}

const maturityLabel = (years: number | null, days: number | null): string => {
  if (years) return `${years}年`
  if (days) return `${days}天`
  return '-'
}

// =============================================================================
// テーブル列定義
// =============================================================================

const upcomingColumns: ColumnsType<UpcomingAuction> = [
  {
    title: '入札日',
    dataIndex: 'bidding_date',
    key: 'bidding_date',
    width: 100,
    render: (val: string | null, record: UpcomingAuction) => {
      const dateStr = formatDateJP(val)
      const timeStr = record.bidding_time_start
        ? `${record.bidding_time_start}~${record.bidding_time_end || ''}`
        : ''
      return (
        <div>
          <div style={{ fontWeight: 600 }}>{dateStr}</div>
          {timeStr && <div style={{ fontSize: 11, color: '#666' }}>{timeStr}</div>}
        </div>
      )
    },
  },
  {
    title: '銘柄',
    dataIndex: 'bond_name',
    key: 'bond_name',
    ellipsis: true,
    render: (val: string | null, record: UpcomingAuction) => {
      const bt = bondTypeLabel(record.bond_type)
      return (
        <div>
          <Tag color={bt.color} style={{ marginRight: 4 }}>{bt.label}</Tag>
          {record.is_reissue && <Tag color="purple" style={{ marginRight: 4 }}>続発</Tag>}
          <span>{val || '-'}</span>
        </div>
      )
    },
  },
  {
    title: '年限',
    key: 'maturity',
    width: 70,
    align: 'center' as const,
    render: (_: unknown, record: UpcomingAuction) =>
      maturityLabel(record.maturity_years, record.maturity_days),
  },
  {
    title: '発行額(億元)',
    dataIndex: 'issue_amount',
    key: 'issue_amount',
    width: 110,
    align: 'right' as const,
    render: (val: number | null) => val ? `${val.toLocaleString()}` : '-',
  },
]

const resultColumns: ColumnsType<RecentResult> = [
  {
    title: '発表日',
    dataIndex: 'publish_date',
    key: 'publish_date',
    width: 100,
    render: (val: string | null) => formatDateJP(val),
  },
  {
    title: '銘柄',
    dataIndex: 'bond_name',
    key: 'bond_name',
    ellipsis: true,
    render: (val: string | null, record: RecentResult) => {
      const bt = bondTypeLabel(record.bond_type)
      return (
        <div>
          <Tag color={bt.color} style={{ marginRight: 4 }}>{bt.label}</Tag>
          {record.is_reissue && <Tag color="purple" style={{ marginRight: 4 }}>続発</Tag>}
          <span style={{ fontSize: 12 }}>{val?.replace(/（以下称本期国债）已完成招标工作/, '') || record.notice_number || '-'}</span>
        </div>
      )
    },
  },
  {
    title: '年限',
    key: 'maturity',
    width: 65,
    align: 'center' as const,
    render: (_: unknown, record: RecentResult) =>
      maturityLabel(record.maturity_years, record.maturity_days),
  },
  {
    title: '発行額(億)',
    dataIndex: 'actual_amount',
    key: 'actual_amount',
    width: 85,
    align: 'right' as const,
    render: (val: number | null) => val ? `${val.toLocaleString()}` : '-',
  },
  {
    title: '利回り',
    dataIndex: 'annual_yield',
    key: 'annual_yield',
    width: 75,
    align: 'right' as const,
    render: (val: number | null) =>
      val != null ? (
        <span style={{ color: val >= 2.5 ? '#ef4444' : val >= 1.5 ? '#f97316' : '#22c55e', fontWeight: 600 }}>
          {val.toFixed(2)}%
        </span>
      ) : '-',
  },
  {
    title: '票面利率',
    dataIndex: 'coupon_rate',
    key: 'coupon_rate',
    width: 80,
    align: 'right' as const,
    render: (val: number | null) => val != null ? `${val.toFixed(2)}%` : '-',
  },
  {
    title: '価格',
    dataIndex: 'issue_price',
    key: 'issue_price',
    width: 75,
    align: 'right' as const,
    render: (val: number | null) => val != null ? val.toFixed(2) : '-',
  },
]

// =============================================================================
// メインコンポーネント
// =============================================================================

function CnGovernmentBondIssuanceChart() {
  const isMaster = useIsMaster()
  const [viewMode, setViewMode] = useState<ViewMode>('upcoming')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(3)
  const [loading, setLoading] = useState(true)
  const [apiData, setApiData] = useState<BondIssuanceApiResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async (forceRefresh = false) => {
    try {
      setLoading(true)
      setError(null)
      const url = `${API_BASE_URL}/api/china/mof/bond-issuance${forceRefresh ? '?force_refresh=true' : ''}`
      const resp = await fetch(url)
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const json: BondIssuanceApiResponse = await resp.json()
      setApiData(json)
    } catch (e) {
      console.error('[CnBondIssuance] fetch error:', e)
      setError('データの取得に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  const upcoming = apiData?.upcoming ?? []
  const recentResults = apiData?.recent_results ?? []
  const monthlySupply = apiData?.monthly_supply ?? []

  const filteredSupply = usePeriodFiltering(monthlySupply, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2024,
  })

  // サマリー
  const summary = useMemo(() => {
    if (!apiData) return null
    const meta = apiData.metadata || {}
    return {
      totalNotices: (meta.total_notices as number) || 0,
      totalResults: (meta.total_results as number) || 0,
      upcomingCount: upcoming.length,
    }
  }, [apiData, upcoming])

  if (loading) {
    return <LoadingChart title="国債発行（Government Bond Issuance）" />
  }

  if (error) {
    return (
      <div id="bond-issuance">
        <ChartContainer title="国債発行（Government Bond Issuance）" showPeriodSelector={false} showDataSource={false}>
          <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
            {error}
            {isMaster && (
              <div style={{ marginTop: 12 }}>
                <Button size="small" onClick={() => fetchData(true)}>再取得</Button>
              </div>
            )}
          </div>
        </ChartContainer>
      </div>
    )
  }

  return (
    <div id="bond-issuance">
      <ChartContainer
        title="国債発行（Government Bond Issuance）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="中国財政部 (MOF)"
        sourceUrl="https://zwgls.mof.gov.cn/ywgg/"
      >
        {/* サマリー */}
        {summary && (
          <div style={{
            display: 'flex',
            gap: 16,
            marginBottom: 12,
            padding: '8px 12px',
            background: 'var(--ea-bg-tertiary, #f8f9fa)',
            borderRadius: 8,
            fontSize: 13,
            color: 'var(--ea-text-primary, #333)',
          }}>
            <span>
              今後の入札: <strong style={{ color: upcoming.length > 0 ? '#1890ff' : '#999' }}>{summary.upcomingCount}件</strong>
            </span>
            <span>通知: {summary.totalNotices}件</span>
            <span>公告: {summary.totalResults}件</span>
          </div>
        )}

        {/* タブ切替 */}
        <div style={{ marginBottom: 8 }}>
          <ViewModeButtonGroup
            options={[
              { mode: 'upcoming' as ViewMode, label: '入札予定' },
              { mode: 'results' as ViewMode, label: '入札結果' },
              { mode: 'supply' as ViewMode, label: '月次供給量' },
            ]}
            currentMode={viewMode}
            onChange={setViewMode}
          />
        </div>

        {/* タブ1: 入札予定 */}
        {viewMode === 'upcoming' && (
          upcoming.length > 0 ? (
            <Table
              dataSource={upcoming}
              columns={upcomingColumns}
              rowKey={(r) => `${r.bidding_date}-${r.bond_name}`}
              pagination={false}
              size="small"
              style={{ marginTop: 8 }}
            />
          ) : (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
              今後の入札予定はありません
            </div>
          )
        )}

        {/* タブ2: 入札結果 */}
        {viewMode === 'results' && (
          recentResults.length > 0 ? (
            <Table
              dataSource={recentResults}
              columns={resultColumns}
              rowKey={(r) => `${r.publish_date}-${r.notice_number}`}
              pagination={{ pageSize: 15, size: 'small' }}
              size="small"
              scroll={{ x: 680 }}
              style={{ marginTop: 8 }}
            />
          ) : (
            <NoDataMessage />
          )
        )}

        {/* タブ3: 月次供給量 */}
        {viewMode === 'supply' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            {filteredSupply.length > 0 ? (
              <StandardBarChart
                data={filteredSupply}
                bars={[
                  { dataKey: 'interest_bearing', color: COLOR_INTEREST_BEARING, name: '附息国債', stackId: 'supply' },
                  { dataKey: 'discount', color: COLOR_DISCOUNT, name: '贴現国債', stackId: 'supply' },
                  { dataKey: 'savings', color: COLOR_SAVINGS, name: '储蓄国債', stackId: 'supply' },
                ]}
                yAxisFormatter={(v) => `${v.toLocaleString()}`}
                xAxisFormatter={formatDateLabel}
                tooltipLabelFormatter={formatDateFull}
                tooltipValueFormatter={(v) => `${v.toLocaleString()}億元`}
                showLegend={true}
              />
            ) : (
              <NoDataMessage />
            )}
          </>
        )}
      </ChartContainer>
    </div>
  )
}

// special 限定 (一般ユーザには非表示)
export default withVisibility(CnGovernmentBondIssuanceChart, 'special')
