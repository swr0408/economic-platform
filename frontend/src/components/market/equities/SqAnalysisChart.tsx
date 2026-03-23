import { useState, useMemo } from 'react'
import { Typography, Segmented, Table, Tooltip } from 'antd'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import ChartContainer from '../../common/ChartContainer'
import type { ColumnsType } from 'antd/es/table'
import {
  classifyBias,
  classifyMonthlyBias,
  returnColor,
  winRateColor,
  nColor,
  nTooltip,
  shouldBold,
  getRowStyle,
  getBadgeStyle,
  generateSummary,
  generateMonthlySummary,
  PRIORITY_A_KEYS,
  SQ_COLORS,
  type BiasLabel,
} from './sqAnalysisUtils'

const { Text } = Typography

const DARK = {
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  neutral: '#94a3b8',
}

// ---------- Types ----------

interface StatGroup {
  mean: number | null
  median: number | null
  win_rate: number | null
  count: number
}

interface GroupStats {
  label: string
  count: number
  d_minus2_to_minus1: StatGroup
  d_minus1_to_sq: StatGroup
  d_minus2_to_sq: StatGroup
  sq_day_oc: StatGroup
  sq_to_next: StatGroup
  intraday_return?: StatGroup
  intraday_regular_return?: StatGroup
}

interface SqDataItem {
  date: string
  year: number
  month: number
  type: string
  sq_close: number | null
  d_minus2_to_minus1: number | null
  d_minus1_to_sq: number | null
  d_minus2_to_sq: number | null
  sq_day_oc: number | null
  sq_to_next: number | null
  intraday_return?: number | null
  intraday_regular_return?: number | null
}

interface SqResponse {
  nikkei225: {
    data: SqDataItem[]
    summary: {
      all: GroupStats
      sq?: GroupStats
      msq?: GroupStats
      monthly: Record<string, GroupStats>
    }
  }
  sp500: {
    data: SqDataItem[]
    summary: {
      all: GroupStats
      sq?: GroupStats
      msq?: GroupStats
      monthly: Record<string, GroupStats>
    }
  }
  cached: boolean
  source: string
  last_updated: string | null
}

// ---------- Hook ----------

function useSqAnalysisData() {
  return useQuery({
    queryKey: ['market', 'sq-analysis'],
    queryFn: async () => {
      const { data } = await axios.get<SqResponse>('/api/market/sq-analysis')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

// ---------- Cell Renderers ----------

interface SummaryRow {
  key: string
  mean: number | null
  median: number | null
  win_rate: number | null
  count: number
}

/** バッジコンポーネント */
function BiasBadge({ bias }: { bias: BiasLabel }) {
  const style = getBadgeStyle(bias)
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '1px 6px',
        borderRadius: 4,
        fontSize: 11,
        fontWeight: 600,
        backgroundColor: style.backgroundColor,
        color: style.color,
        lineHeight: '18px',
        whiteSpace: 'nowrap',
      }}
    >
      {style.label}
    </span>
  )
}

/** 平均・中央値セル */
function PctCell({
  val,
  bias,
  isPriorityA,
  monthly = false,
}: {
  val: number | null | undefined
  bias: BiasLabel
  isPriorityA: boolean
  monthly?: boolean
}) {
  if (val == null) return <Text style={{ color: DARK.neutral }}>—</Text>
  const color = returnColor(val, monthly)
  const bold = shouldBold(val, bias, isPriorityA, 'return')
  return (
    <Text
      style={{
        color,
        fontFamily: 'monospace',
        fontSize: 13,
        fontWeight: bold ? 700 : 400,
      }}
    >
      {val > 0 ? '+' : ''}{val.toFixed(2)}%
    </Text>
  )
}

/** 上昇確率セル */
function WinRateCell({
  val,
  bias,
  isPriorityA,
  monthly = false,
}: {
  val: number | null | undefined
  bias: BiasLabel
  isPriorityA: boolean
  monthly?: boolean
}) {
  if (val == null) return <Text style={{ color: DARK.neutral }}>—</Text>
  const color = winRateColor(val, monthly)
  const bold = shouldBold(val, bias, isPriorityA, 'winRate')
  return (
    <Text style={{ color, fontWeight: bold ? 700 : 600, fontSize: 13 }}>
      {val.toFixed(1)}%
    </Text>
  )
}

/** N セル */
function NCell({ n }: { n: number }) {
  const color = nColor(n)
  const tip = nTooltip(n)
  const content = <Text style={{ color, fontSize: 13 }}>{n}</Text>
  if (tip) {
    return <Tooltip title={tip}>{content}</Tooltip>
  }
  return content
}

// ---------- Summary Table ----------

function SummaryTable({
  stats,
  isNikkei,
  periodLabel,
}: {
  stats: GroupStats
  isNikkei: boolean
  periodLabel: string
}) {
  const rows: SummaryRow[] = [
    { key: '前々日→前日', ...stats.d_minus2_to_minus1 },
    { key: '前日→SQ日', ...stats.d_minus1_to_sq },
    { key: '前2日間合計', ...stats.d_minus2_to_sq },
    { key: 'SQ当日(始値→終値)', ...stats.sq_day_oc },
    { key: 'SQ→翌営業日', ...stats.sq_to_next },
  ]
  if (isNikkei && stats.intraday_return) {
    rows.push({ key: '当日ｲﾝﾄﾗﾃﾞｲ(9:00-15:00)', ...stats.intraday_return })
  }
  if (!isNikkei && stats.intraday_regular_return) {
    rows.push({ key: '正規取引(9:30-16:00 ET)', ...stats.intraday_regular_return })
  }

  const summaryText = generateSummary(rows, periodLabel)

  const columns: ColumnsType<SummaryRow> = [
    {
      title: '期間',
      dataIndex: 'key',
      key: 'key',
      width: 220,
      render: (_: unknown, row: SummaryRow) => {
        const rs = getRowStyle(row.mean, row.median, row.win_rate, row.count, row.key)
        return (
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {rs.showDot && (
              <span style={{
                display: 'inline-block',
                width: 6,
                height: 6,
                borderRadius: '50%',
                backgroundColor: rs.badge === '強気' || rs.badge === 'やや強気'
                  ? SQ_COLORS.positiveVeryStrong
                  : SQ_COLORS.negativeVeryStrong,
                flexShrink: 0,
              }} />
            )}
            <Text style={{ color: DARK.textPrimary, fontSize: 13 }}>{row.key}</Text>
            {rs.showBadge && <BiasBadge bias={rs.badge} />}
          </span>
        )
      },
    },
    {
      title: '平均',
      dataIndex: 'mean',
      key: 'mean',
      width: 100,
      align: 'right' as const,
      render: (_: unknown, row: SummaryRow) => {
        const bias = classifyBias(row.mean, row.median, row.win_rate, row.count)
        const isPriorityA = PRIORITY_A_KEYS.has(row.key)
        return <PctCell val={row.mean} bias={bias} isPriorityA={isPriorityA} />
      },
    },
    {
      title: '中央値',
      dataIndex: 'median',
      key: 'median',
      width: 100,
      align: 'right' as const,
      render: (_: unknown, row: SummaryRow) => {
        const bias = classifyBias(row.mean, row.median, row.win_rate, row.count)
        const isPriorityA = PRIORITY_A_KEYS.has(row.key)
        return <PctCell val={row.median} bias={bias} isPriorityA={isPriorityA} />
      },
    },
    {
      title: '上昇確率',
      dataIndex: 'win_rate',
      key: 'win_rate',
      width: 100,
      align: 'right' as const,
      render: (_: unknown, row: SummaryRow) => {
        const bias = classifyBias(row.mean, row.median, row.win_rate, row.count)
        const isPriorityA = PRIORITY_A_KEYS.has(row.key)
        return <WinRateCell val={row.win_rate} bias={bias} isPriorityA={isPriorityA} />
      },
    },
    {
      title: 'N',
      dataIndex: 'count',
      key: 'count',
      width: 60,
      align: 'right' as const,
      render: (_: unknown, row: SummaryRow) => <NCell n={row.count} />,
    },
  ]

  return (
    <div>
      {summaryText && (
        <div style={{
          marginBottom: 10,
          padding: '6px 10px',
          backgroundColor: '#1e293b',
          borderRadius: 4,
          borderLeft: '3px solid #475569',
        }}>
          <Text style={{ color: DARK.textSecondary, fontSize: 12, lineHeight: '1.6' }}>
            {summaryText}
          </Text>
        </div>
      )}
      <Table
        dataSource={rows}
        rowKey="key"
        size="small"
        pagination={false}
        style={{ marginBottom: 16 }}
        columns={columns}
        onRow={(row) => {
          const rs = getRowStyle(row.mean, row.median, row.win_rate, row.count, row.key)
          return {
            style: rs.background ? { backgroundColor: rs.background } : undefined,
          }
        }}
      />
    </div>
  )
}

// ---------- Monthly Summary ----------

function calcMonthlyStats(data: SqDataItem[], field: string) {
  const byMonth: Record<number, number[]> = {}
  for (const d of data) {
    const val = (d as unknown as Record<string, unknown>)[field] as number | null | undefined
    if (val != null) {
      if (!byMonth[d.month]) byMonth[d.month] = []
      byMonth[d.month].push(val)
    }
  }
  return Object.entries(byMonth)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([month, vals]) => {
      const sum = vals.reduce((a, b) => a + b, 0)
      const sorted = [...vals].sort((a, b) => a - b)
      const median = sorted.length % 2 === 0
        ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
        : sorted[Math.floor(sorted.length / 2)]
      return {
        month: `${month}月`,
        monthNum: Number(month),
        mean: Math.round((sum / vals.length) * 10000) / 10000,
        median: Math.round(median * 10000) / 10000,
        win_rate: Math.round((vals.filter(v => v > 0).length / vals.length) * 1000) / 10,
        count: vals.length,
      }
    })
}

interface MonthlyRow {
  month: string
  monthNum: number
  mean: number
  median: number
  win_rate: number
  count: number
}

function MonthlySummaryTable({ data, field, fieldLabel }: { data: SqDataItem[]; field: string; fieldLabel: string }) {
  const rows = useMemo(() => calcMonthlyStats(data, field), [data, field])

  if (rows.length === 0) return null

  const summaryRows = rows.map(r => ({
    key: r.month,
    mean: r.mean,
    median: r.median,
    win_rate: r.win_rate,
    count: r.count,
  }))
  const summaryText = generateMonthlySummary(summaryRows, fieldLabel)

  const columns: ColumnsType<MonthlyRow> = [
    {
      title: '月',
      dataIndex: 'month',
      key: 'month',
      width: 80,
      render: (_: unknown, row: MonthlyRow) => {
        const rs = getRowStyle(row.mean, row.median, row.win_rate, row.count, row.month, true)
        return (
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Text style={{ color: DARK.textPrimary }}>{row.month}</Text>
            {rs.showBadge && <BiasBadge bias={rs.badge} />}
          </span>
        )
      },
    },
    {
      title: '平均',
      dataIndex: 'mean',
      key: 'mean',
      width: 90,
      align: 'right' as const,
      render: (_: unknown, row: MonthlyRow) => {
        const bias = classifyMonthlyBias(row.mean, row.median, row.win_rate, row.count)
        return <PctCell val={row.mean} bias={bias} isPriorityA={false} monthly />
      },
    },
    {
      title: '中央値',
      dataIndex: 'median',
      key: 'median',
      width: 90,
      align: 'right' as const,
      render: (_: unknown, row: MonthlyRow) => {
        const bias = classifyMonthlyBias(row.mean, row.median, row.win_rate, row.count)
        return <PctCell val={row.median} bias={bias} isPriorityA={false} monthly />
      },
    },
    {
      title: '上昇確率',
      dataIndex: 'win_rate',
      key: 'win_rate',
      width: 90,
      align: 'right' as const,
      render: (_: unknown, row: MonthlyRow) => {
        const bias = classifyMonthlyBias(row.mean, row.median, row.win_rate, row.count)
        return <WinRateCell val={row.win_rate} bias={bias} isPriorityA={false} monthly />
      },
    },
    {
      title: 'N',
      dataIndex: 'count',
      key: 'count',
      width: 50,
      align: 'right' as const,
      render: (_: unknown, row: MonthlyRow) => <NCell n={row.count} />,
    },
  ]

  return (
    <div>
      {summaryText && (
        <div style={{
          marginBottom: 8,
          padding: '4px 10px',
          borderRadius: 4,
          borderLeft: '3px solid #334155',
        }}>
          <Text style={{ color: '#64748b', fontSize: 11, lineHeight: '1.5' }}>
            {summaryText}
          </Text>
        </div>
      )}
      <Table
        dataSource={rows}
        rowKey="month"
        size="small"
        pagination={false}
        style={{ marginBottom: 16 }}
        columns={columns}
      />
    </div>
  )
}

// ---------- Detail Table ----------

function DetailTable({ data, isNikkei }: { data: SqDataItem[]; isNikkei: boolean }) {
  const pctCellSimple = (v: number | null | undefined) => {
    if (v == null) return <Text style={{ color: DARK.neutral }}>—</Text>
    const color = returnColor(v)
    return (
      <Text style={{ color, fontFamily: 'monospace', fontSize: 13 }}>
        {v > 0 ? '+' : ''}{v.toFixed(2)}%
      </Text>
    )
  }

  const columns: ColumnsType<SqDataItem> = [
    {
      title: '日付',
      dataIndex: 'date',
      key: 'date',
      width: 110,
      fixed: 'left' as const,
      render: (v: string) => <Text style={{ color: DARK.textPrimary, fontSize: 13 }}>{v}</Text>,
    },
    ...(isNikkei ? [{
      title: 'タイプ',
      dataIndex: 'type',
      key: 'type',
      width: 70,
      render: (v: string) => (
        <span
          style={{
            display: 'inline-block',
            padding: '1px 6px',
            borderRadius: 4,
            fontSize: 11,
            fontWeight: 600,
            backgroundColor: v === 'MSQ' ? '#422006' : '#1e3a5f',
            color: v === 'MSQ' ? '#fbbf24' : '#60a5fa',
            margin: 0,
          }}
        >
          {v}
        </span>
      ),
    }] : []),
    {
      title: '前々日→前日',
      dataIndex: 'd_minus2_to_minus1',
      key: 'd_minus2_to_minus1',
      width: 110,
      align: 'right' as const,
      render: (v: number | null) => pctCellSimple(v),
    },
    {
      title: '前日→SQ日',
      dataIndex: 'd_minus1_to_sq',
      key: 'd_minus1_to_sq',
      width: 110,
      align: 'right' as const,
      render: (v: number | null) => pctCellSimple(v),
    },
    {
      title: '前2日間',
      dataIndex: 'd_minus2_to_sq',
      key: 'd_minus2_to_sq',
      width: 100,
      align: 'right' as const,
      render: (v: number | null) => pctCellSimple(v),
    },
    {
      title: 'SQ当日(O→C)',
      dataIndex: 'sq_day_oc',
      key: 'sq_day_oc',
      width: 110,
      align: 'right' as const,
      render: (v: number | null) => pctCellSimple(v),
    },
    ...(isNikkei ? [{
      title: 'ｲﾝﾄﾗﾃﾞｲ',
      dataIndex: 'intraday_return' as const,
      key: 'intraday_return',
      width: 100,
      align: 'right' as const,
      render: (v: number | null | undefined) => pctCellSimple(v),
    }] : [
      {
        title: '正規取引',
        dataIndex: 'intraday_regular_return' as const,
        key: 'intraday_regular_return',
        width: 100,
        align: 'right' as const,
        render: (v: number | null | undefined) => pctCellSimple(v),
      },
    ]),
    {
      title: 'SQ→翌日',
      dataIndex: 'sq_to_next',
      key: 'sq_to_next',
      width: 100,
      align: 'right' as const,
      render: (v: number | null) => pctCellSimple(v),
    },
  ]

  return (
    <Table
      dataSource={data}
      rowKey="date"
      size="small"
      pagination={{ pageSize: 20, size: 'small' }}
      scroll={{ x: 900 }}
      columns={columns}
    />
  )
}

// ---------- Main Component ----------

type MarketTab = 'nikkei225' | 'sp500'
type ViewTab = 'summary' | 'monthly' | 'detail'
type PeriodFilter = 'all' | '10y' | '20y' | '30y'

function calcGroupStats(data: SqDataItem[], isNikkei: boolean): GroupStats {
  const _stats = (values: (number | null | undefined)[]): StatGroup => {
    const valid = values.filter((v): v is number => v != null)
    if (valid.length === 0) return { mean: null, median: null, win_rate: null, count: 0 }
    const sum = valid.reduce((a, b) => a + b, 0)
    const sorted = [...valid].sort((a, b) => a - b)
    const median = sorted.length % 2 === 0
      ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
      : sorted[Math.floor(sorted.length / 2)]
    return {
      mean: Math.round((sum / valid.length) * 10000) / 10000,
      median: Math.round(median * 10000) / 10000,
      win_rate: Math.round((valid.filter(v => v > 0).length / valid.length) * 1000) / 10,
      count: valid.length,
    }
  }
  const stats: GroupStats = {
    label: '全体',
    count: data.length,
    d_minus2_to_minus1: _stats(data.map(d => d.d_minus2_to_minus1)),
    d_minus1_to_sq: _stats(data.map(d => d.d_minus1_to_sq)),
    d_minus2_to_sq: _stats(data.map(d => d.d_minus2_to_sq)),
    sq_day_oc: _stats(data.map(d => d.sq_day_oc)),
    sq_to_next: _stats(data.map(d => d.sq_to_next)),
  }
  if (isNikkei) {
    const vals = data.map(d => d.intraday_return).filter(v => v != null)
    if (vals.length > 0) stats.intraday_return = _stats(vals)
  } else {
    const vals = data.map(d => d.intraday_regular_return).filter(v => v != null)
    if (vals.length > 0) stats.intraday_regular_return = _stats(vals)
  }
  return stats
}

const PERIOD_LABELS: Record<PeriodFilter, string> = {
  all: '全期間',
  '10y': '直近10年',
  '20y': '直近20年',
  '30y': '直近30年',
}

export default function SqAnalysisChart() {
  const { data: apiData, isLoading, error } = useSqAnalysisData()
  const [market, setMarket] = useState<MarketTab>('nikkei225')
  const [view, setView] = useState<ViewTab>('summary')
  const [period, setPeriod] = useState<PeriodFilter>('all')

  const marketData = useMemo(() => {
    if (!apiData) return null
    return market === 'nikkei225' ? apiData.nikkei225 : apiData.sp500
  }, [apiData, market])

  const isNikkei = market === 'nikkei225'

  const [sqFilter, setSqFilter] = useState<'all' | 'SQ' | 'MSQ'>('all')

  const periodOptions = useMemo(() => {
    const opts: { label: string; value: PeriodFilter }[] = [
      { label: '全期間', value: 'all' },
      { label: '10年', value: '10y' },
    ]
    if (!marketData?.data?.length) return opts
    const minYear = Math.min(...marketData.data.map(d => d.year))
    const currentYear = new Date().getFullYear()
    const span = currentYear - minYear
    if (span >= 20) opts.push({ label: '20年', value: '20y' })
    if (span >= 30) opts.push({ label: '30年', value: '30y' })
    return opts
  }, [marketData])

  const periodStartYear = useMemo(() => {
    if (period === 'all') return 0
    const years = parseInt(period)
    return new Date().getFullYear() - years
  }, [period])

  const filteredData = useMemo(() => {
    if (!marketData?.data) return []
    let data = [...marketData.data]
    if (periodStartYear > 0) {
      data = data.filter(d => d.year >= periodStartYear)
    }
    if (isNikkei && sqFilter !== 'all') {
      data = data.filter(d => d.type === sqFilter)
    }
    return data.reverse()
  }, [marketData, isNikkei, sqFilter, periodStartYear])

  const summaryStats = useMemo(() => {
    if (filteredData.length === 0) return null
    return calcGroupStats(filteredData, isNikkei)
  }, [filteredData, isNikkei])

  if (isLoading) {
    return (
      <ChartContainer title="SQ/MSQ 検証分析" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (error || !apiData) {
    return (
      <ChartContainer title="SQ/MSQ 検証分析" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK.textSecondary }}>
          データの取得に失敗しました
        </div>
      </ChartContainer>
    )
  }

  const periodLabel = PERIOD_LABELS[period]
  const sqFilterLabel = sqFilter === 'all' ? '' : sqFilter === 'MSQ' ? '（MSQのみ）' : '（SQのみ）'

  return (
    <ChartContainer
      title="SQ/MSQ 検証分析"
      dataSource="yfinance / Dukascopy"
      showPeriodSelector={false}
      handbookId="sq-settlement"
    >
      {/* コントロール */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
        <Segmented
          value={market}
          onChange={(v) => { setMarket(v as MarketTab); setSqFilter('all') }}
          options={[
            { label: '日経225', value: 'nikkei225' },
            { label: 'S&P 500', value: 'sp500' },
          ]}
          style={{ backgroundColor: '#1e293b' }}
        />
        <Segmented
          value={view}
          onChange={(v) => setView(v as ViewTab)}
          options={[
            { label: 'サマリー', value: 'summary' },
            { label: '月別', value: 'monthly' },
            { label: '詳細', value: 'detail' },
          ]}
          style={{ backgroundColor: '#1e293b' }}
        />
        <Segmented
          value={period}
          onChange={(v) => setPeriod(v as PeriodFilter)}
          options={periodOptions}
          style={{ backgroundColor: '#1e293b' }}
        />
        {isNikkei && (
          <Segmented
            value={sqFilter}
            onChange={(v) => setSqFilter(v as 'all' | 'SQ' | 'MSQ')}
            options={[
              { label: '全て', value: 'all' },
              { label: 'SQのみ', value: 'SQ' },
              { label: 'MSQのみ', value: 'MSQ' },
            ]}
            style={{ backgroundColor: '#1e293b' }}
          />
        )}
      </div>

      {/* 説明 */}
      <div style={{ marginBottom: 16, padding: '8px 12px', backgroundColor: '#1e293b', borderRadius: 6, border: '1px solid #334155' }}>
        <Text style={{ color: DARK.textSecondary, fontSize: 12 }}>
          {isNikkei
            ? 'SQ = 毎月第2金曜日、MSQ = 3,6,9,12月の第2金曜日（メジャーSQ）'
            : 'S&P500 オプション満期 = 3,6,9,12月の第3金曜日'}
          {' | '}対象期間: 2010年〜現在
        </Text>
      </div>

      {/* サマリービュー */}
      {view === 'summary' && summaryStats && (
        <div>
          <Text style={{ color: DARK.textPrimary, fontSize: 15, fontWeight: 600, display: 'block', marginBottom: 12 }}>
            {summaryStats.label}{sqFilterLabel}（{summaryStats.count}回 / {periodLabel}）
          </Text>
          <SummaryTable stats={summaryStats} isNikkei={isNikkei} periodLabel={`${periodLabel}${sqFilterLabel}`} />
        </div>
      )}

      {/* 月別ビュー */}
      {view === 'monthly' && filteredData.length > 0 && (
        <div>
          <Text style={{ color: DARK.textPrimary, fontSize: 14, fontWeight: 600, display: 'block', marginBottom: 8 }}>
            月別: 前2日間の騰落率
          </Text>
          <MonthlySummaryTable data={filteredData} field="d_minus2_to_sq" fieldLabel="前2日間" />

          <Text style={{ color: DARK.textPrimary, fontSize: 14, fontWeight: 600, display: 'block', marginBottom: 8, marginTop: 16 }}>
            月別: SQ当日（始値→終値）
          </Text>
          <MonthlySummaryTable data={filteredData} field="sq_day_oc" fieldLabel="SQ当日" />

          <Text style={{ color: DARK.textPrimary, fontSize: 14, fontWeight: 600, display: 'block', marginBottom: 8, marginTop: 16 }}>
            月別: SQ→翌営業日
          </Text>
          <MonthlySummaryTable data={filteredData} field="sq_to_next" fieldLabel="SQ→翌営業日" />
        </div>
      )}

      {/* 詳細ビュー */}
      {view === 'detail' && (
        <DetailTable data={filteredData} isNikkei={isNikkei} />
      )}
    </ChartContainer>
  )
}
