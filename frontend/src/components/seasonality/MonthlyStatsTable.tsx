import { useEffect, useState } from 'react'
import { Spin, Alert, Typography, Segmented, Popover, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { InfoCircleOutlined } from '@ant-design/icons'
import axios from 'axios'

const { Text } = Typography

const COLORS = {
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textTertiary: '#64748b',
  border: '#334155',
  positive: '#10b981',
  positiveAlt: '#34d399',
  negative: '#ef4444',
  negativeAlt: '#f87171',
  full: '#3b82f6',
  recent: '#f59e0b',
}

interface PeriodStats {
  n: number
  mean: number
  median: number
  std: number
  ci95_low: number
  ci95_high: number
  neg_rate: number
  mean_median_gap: number
  p_value: number | null
}

interface MonthData {
  month: number
  full: PeriodStats
  recent: PeriodStats
  diff: {
    mean_diff: number
    neg_rate_diff: number
  }
}

interface MonthlyStatsResponse {
  symbol: string
  generated_at: string
  periods: {
    full: { start_year: number; end_year: number; label: string }
    recent: { start_year: number; end_year: number; label: string }
  }
  months: MonthData[]
}

interface RowData {
  key: number
  month: string
  n: number
  mean: number
  median: number
  gap: number
  std: number
  ci: string
  negRate: number
  pValue: number | null
}

const MONTH_LABELS = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

type PeriodMode = 'full' | 'recent'

interface MonthlyStatsTableProps {
  symbol: string
}

export default function MonthlyStatsTable({ symbol }: MonthlyStatsTableProps) {
  const [data, setData] = useState<MonthlyStatsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [periodMode, setPeriodMode] = useState<PeriodMode>('full')

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await axios.get<MonthlyStatsResponse>(
          `/api/seasonality/${encodeURIComponent(symbol)}/monthly-stats`
        )
        setData(response.data)
      } catch (err) {
        console.error('Failed to fetch monthly stats:', err)
        if (axios.isAxiosError(err) && err.response?.status === 404) {
          setError('この銘柄の月別統計データはまだ生成されていません。')
        } else {
          setError('月別統計データの取得に失敗しました。')
        }
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [symbol])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '60px 20px' }}>
        <Spin />
        <p style={{ marginTop: 12, color: COLORS.textSecondary }}>テーブルを読み込み中...</p>
      </div>
    )
  }

  if (error) {
    return <Alert message="情報" description={error} type="info" showIcon style={{ marginBottom: 16 }} />
  }

  if (!data || !data.months || data.months.length === 0) {
    return <Alert message="データなし" description="データがありません。" type="warning" showIcon />
  }

  // 行データ整形
  const rows: RowData[] = data.months.map((m) => {
    const stats = periodMode === 'full' ? m.full : m.recent
    return {
      key: m.month,
      month: MONTH_LABELS[m.month - 1],
      n: stats.n,
      mean: stats.mean,
      median: stats.median,
      gap: stats.mean_median_gap,
      std: stats.std,
      ci: `[${stats.ci95_low.toFixed(2)}, ${stats.ci95_high.toFixed(2)}]`,
      negRate: stats.neg_rate * 100,
      pValue: stats.p_value,
    }
  })

  const fmtSign = (v: number, digits = 2) => `${v >= 0 ? '+' : ''}${v.toFixed(digits)}`

  const fmtP = (p: number | null): { text: string; color: string } => {
    if (p === null || p === undefined) return { text: '—', color: COLORS.textTertiary }
    let stars = ''
    let color = COLORS.textPrimary
    if (p < 0.01) {
      stars = ' ***'
      color = COLORS.positive
    } else if (p < 0.05) {
      stars = ' **'
      color = COLORS.positiveAlt
    } else if (p < 0.10) {
      stars = ' *'
      color = COLORS.recent
    } else {
      color = COLORS.textSecondary
    }
    const text = p < 0.001 ? `<0.001${stars}` : `${p.toFixed(3)}${stars}`
    return { text, color }
  }

  const columns: ColumnsType<RowData> = [
    {
      title: '月',
      dataIndex: 'month',
      key: 'month',
      width: 60,
      fixed: 'left',
      render: (v: string) => <span style={{ color: COLORS.textPrimary, fontWeight: 600 }}>{v}</span>,
    },
    {
      title: 'n',
      dataIndex: 'n',
      key: 'n',
      width: 50,
      align: 'right',
      sorter: (a, b) => a.n - b.n,
      render: (v: number) => <span style={{ color: COLORS.textSecondary }}>{v}</span>,
    },
    {
      title: '平均',
      dataIndex: 'mean',
      key: 'mean',
      width: 80,
      align: 'right',
      sorter: (a, b) => a.mean - b.mean,
      render: (v: number) => (
        <span style={{ color: v >= 0 ? COLORS.positive : COLORS.negativeAlt, fontWeight: 600 }}>
          {fmtSign(v)}%
        </span>
      ),
    },
    {
      title: '中央値',
      dataIndex: 'median',
      key: 'median',
      width: 80,
      align: 'right',
      sorter: (a, b) => a.median - b.median,
      render: (v: number) => (
        <span style={{ color: v >= 0 ? COLORS.positive : COLORS.negativeAlt }}>{fmtSign(v)}%</span>
      ),
    },
    {
      title: '平均-中央値',
      dataIndex: 'gap',
      key: 'gap',
      width: 100,
      align: 'right',
      sorter: (a, b) => a.gap - b.gap,
      render: (v: number) => <span style={{ color: COLORS.textPrimary }}>{fmtSign(v)}%</span>,
    },
    {
      title: 'σ',
      dataIndex: 'std',
      key: 'std',
      width: 70,
      align: 'right',
      sorter: (a, b) => a.std - b.std,
      render: (v: number) => <span style={{ color: COLORS.textPrimary }}>{v.toFixed(2)}%</span>,
    },
    {
      title: '95% CI',
      dataIndex: 'ci',
      key: 'ci',
      width: 130,
      align: 'right',
      render: (v: string) => <span style={{ color: COLORS.textSecondary, fontSize: 11 }}>{v}</span>,
    },
    {
      title: '下落率',
      dataIndex: 'negRate',
      key: 'negRate',
      width: 80,
      align: 'right',
      sorter: (a, b) => a.negRate - b.negRate,
      render: (v: number) => (
        <span style={{ color: v >= 50 ? COLORS.negativeAlt : COLORS.positive, fontWeight: 600 }}>
          {v.toFixed(1)}%
        </span>
      ),
    },
    {
      title: 'p値',
      dataIndex: 'pValue',
      key: 'pValue',
      width: 110,
      align: 'right',
      sorter: (a, b) => (a.pValue ?? 1) - (b.pValue ?? 1),
      render: (v: number | null) => {
        const f = fmtP(v)
        return <span style={{ color: f.color, fontWeight: 600 }}>{f.text}</span>
      },
    },
  ]

  return (
    <div>
      {/* ヘッダー */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 16,
        flexWrap: 'wrap',
        gap: 12,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Text style={{ color: COLORS.textPrimary, fontSize: 14, fontWeight: 600 }}>
            月別詳細テーブル
          </Text>
          <Popover
            trigger="click"
            placement="bottomLeft"
            overlayStyle={{ maxWidth: 520 }}
            content={
              <div style={{ fontSize: 12, lineHeight: 1.7, maxWidth: 480, color: COLORS.textPrimary }}>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 月別詳細テーブル</b><br />
                  12ヵ月の全指標を一覧表示。列ヘッダのクリックで <b>並べ替え可能</b>。
                  「強い月」「弱い月」「ばらつきの大きい月」「有意な月」を横並びで比較できます。
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 列の見方</b><br />
                  ・<b>n</b>: サンプル数（年数）<br />
                  ・<b>平均 / 中央値</b>: 月次リターンの中心値<br />
                  ・<b>平均-中央値</b>: 分布の歪み（プラスなら上振れ外れ値、マイナスなら下振れ外れ値の影響）<br />
                  ・<b>σ</b>: ばらつき（標準偏差）。大きいほど月内リスクが高い<br />
                  ・<b>95% CI</b>: 平均の95%信頼区間。0をまたぐと有意差なし<br />
                  ・<b>下落率</b>: マイナスとなった年の割合。50%超は赤<br />
                  ・<b>p値</b>: 「真の月平均=0」を仮定した両側t検定の確率
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b style={{ color: '#fbbf24' }}>● 有意性記号（p値）</b><br />
                  *** p&lt;0.01 / ** p&lt;0.05 / * p&lt;0.10
                </div>
                <div>
                  <b style={{ color: '#fbbf24' }}>● 全期間 / 直近 切替</b><br />
                  上部のスイッチで集計期間を切り替えられます。両者を見比べると「構造変化」が分かります。
                </div>
              </div>
            }
          >
            <InfoCircleOutlined style={{ color: COLORS.textSecondary, cursor: 'pointer' }} />
          </Popover>
        </div>
        <Segmented
          value={periodMode}
          onChange={(v) => setPeriodMode(v as PeriodMode)}
          options={[
            { label: data.periods.full.label, value: 'full' },
            { label: data.periods.recent.label, value: 'recent' },
          ]}
          size="small"
        />
      </div>

      <Table<RowData>
        columns={columns}
        dataSource={rows}
        pagination={false}
        size="small"
        scroll={{ x: 760 }}
        rowKey="key"
      />

      <div style={{ marginTop: 8, fontSize: 11, color: COLORS.textTertiary, textAlign: 'right' }}>
        ※ 列ヘッダクリックで並べ替え可 / p値: *** p&lt;0.01 / ** p&lt;0.05 / * p&lt;0.10（H₀: 月平均=0）
      </div>
    </div>
  )
}
