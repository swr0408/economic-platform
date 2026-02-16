/**
 * BOC金融政策報告書チャートコンポーネント
 *
 * BOC Monetary Policy Report の見通しデータを表示
 * 最新と前回の見通しを比較表示（グラフ＋テーブル）
 *
 * データソース:
 * - Bank of Canada Valet API
 *
 * 発表スケジュール:
 * - 年4回（1月、4月、7月、10月）
 * - 政策金利発表と同時
 */
import { useState, useMemo } from 'react'
import { Tabs, Table, Tag, Empty } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// 共通モジュールのインポート
import { DARK_THEME } from '../../usa/common/chartConstants'

// 型定義
import type { BocMprData, BocMprComparisonItem } from '../../../../hooks/useDashboardData'

interface BocMonetaryPolicyReportChartProps {
  data: BocMprData | null
}

// 系列キーの順序と表示名
const SERIES_ORDER = [
  { key: 'gdp_qoq', label: '実質GDP（前期比年率）', shortLabel: 'GDP QoQ', color: '#1890ff' },
  { key: 'gdp_yoy', label: '実質GDP（前年比）', shortLabel: 'GDP YoY', color: '#52c41a' },
  { key: 'cpi_yoy', label: 'CPIインフレ（前年比）', shortLabel: 'CPI YoY', color: '#fa8c16' },
  { key: 'core_yoy', label: 'コアインフレ（前年比）', shortLabel: 'Core YoY', color: '#eb2f96' },
] as const

type SeriesKey = typeof SERIES_ORDER[number]['key']

// 四半期の日付をラベルに変換
function formatQuarterLabel(dateStr: string): string {
  const date = new Date(dateStr)
  const year = date.getFullYear()
  const month = date.getMonth() + 1
  const quarter = Math.ceil(month / 3)
  return `${year}Q${quarter}`
}

// 差分の表示テキスト
function formatDiff(diff: number | null): string {
  if (diff === null) return '-'
  if (diff === 0) return '±0.0'
  return diff > 0 ? `+${diff.toFixed(1)}` : diff.toFixed(1)
}

// グラフ用データ型
interface ChartDataPoint {
  date: string
  label: string
  latest: number | null
  previous: number | null
}

export default function BocMonetaryPolicyReportChart({ data }: BocMonetaryPolicyReportChartProps) {
  const [activeTab, setActiveTab] = useState<string>('comparison')
  const [selectedSeries, setSelectedSeries] = useState<SeriesKey>('gdp_qoq')

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="BOC金融政策報告書" />
  }

  const hasData = !!data?.comparison
  const comparison = data?.comparison
  const latestReport = data?.latest_report
  const previousReport = data?.previous_report

  if (!hasData) {
    return (
      <ChartContainer title="BOC金融政策報告書" showPeriodSelector={false} showDataSource={false}>
        <Empty description="データがありません" />
      </ChartContainer>
    )
  }

  // 比較テーブル用のカラム定義
  const columns: ColumnsType<BocMprComparisonItem> = [
    {
      title: '期間',
      dataIndex: 'date',
      key: 'date',
      width: 100,
      render: (date: string) => (
        <span style={{ fontWeight: 500, color: DARK_THEME.textPrimary }}>
          {formatQuarterLabel(date)}
        </span>
      ),
    },
    {
      title: `${comparison?.latest_period || '最新'} (%)`,
      dataIndex: 'latest',
      key: 'latest',
      width: 120,
      align: 'right',
      render: (val: number | null) => (
        <span style={{ color: '#1890ff', fontWeight: 600 }}>
          {val !== null ? val.toFixed(1) : '-'}
        </span>
      ),
    },
    {
      title: `${comparison?.previous_period || '前回'} (%)`,
      dataIndex: 'previous',
      key: 'previous',
      width: 120,
      align: 'right',
      render: (val: number | null) => (
        <span style={{ color: '#888' }}>
          {val !== null ? val.toFixed(1) : '-'}
        </span>
      ),
    },
    {
      title: '差分',
      dataIndex: 'diff',
      key: 'diff',
      width: 100,
      align: 'right',
      render: (diff: number | null) => (
        <Tag color={diff === null ? 'default' : diff > 0 ? 'green' : diff < 0 ? 'red' : 'default'}>
          {formatDiff(diff)}
        </Tag>
      ),
    },
  ]

  // 現在選択中の系列データ
  const currentSeriesData = useMemo(() => {
    if (!comparison?.series_comparison) return []
    const seriesComp = comparison.series_comparison[selectedSeries]
    return seriesComp?.data || []
  }, [comparison, selectedSeries])

  // グラフ用データに変換
  const chartData: ChartDataPoint[] = useMemo(() => {
    return currentSeriesData.map(item => ({
      date: item.date,
      label: formatQuarterLabel(item.date),
      latest: item.latest,
      previous: item.previous,
    }))
  }, [currentSeriesData])

  // 現在選択中の系列情報
  const currentSeriesInfo = SERIES_ORDER.find(s => s.key === selectedSeries)
  const currentSeriesLabel = currentSeriesInfo?.label || ''
  const currentSeriesColor = currentSeriesInfo?.color || '#1890ff'

  // Y軸のドメインを計算
  const yDomain = useMemo(() => {
    const values = chartData.flatMap(d => [d.latest, d.previous]).filter((v): v is number => v !== null)
    if (values.length === 0) return [-1, 5]
    const min = Math.min(...values)
    const max = Math.max(...values)
    const padding = (max - min) * 0.2 || 1
    return [Math.floor(min - padding), Math.ceil(max + padding)]
  }, [chartData])

  return (
    <div id="boc-mpr-chart">
      <ChartContainer
        title="BOC金融政策報告書"
        showPeriodSelector={false}
        dataSource="Bank of Canada"
        sourceUrl="https://www.bankofcanada.ca/publications/mpr/"
      >
        {/* レポート期間情報 */}
        <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <span style={{ color: DARK_THEME.textPrimary, fontSize: 14 }}>
            最新: <strong style={{ color: '#1890ff' }}>{latestReport?.report_label}</strong>
          </span>
          <span style={{ color: DARK_THEME.textSecondary, fontSize: 14 }}>
            前回: <strong>{previousReport?.report_label}</strong>
          </span>
        </div>

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'comparison',
              label: '見通し比較',
              children: (
                <div>
                  {/* 系列選択タブ */}
                  <div style={{ marginBottom: 16 }}>
                    <Tabs
                      type="card"
                      size="small"
                      activeKey={selectedSeries}
                      onChange={(key) => setSelectedSeries(key as SeriesKey)}
                      items={SERIES_ORDER.map(series => ({
                        key: series.key,
                        label: series.shortLabel,
                      }))}
                    />
                  </div>

                  {/* 比較グラフ */}
                  <div style={{ marginBottom: 24 }}>
                    <div style={{ marginBottom: 8 }}>
                      <span style={{ color: DARK_THEME.textPrimary, fontWeight: 600 }}>
                        {currentSeriesLabel}
                      </span>
                    </div>
                    <ResponsiveContainer width="100%" height={300}>
                      <LineChart
                        data={chartData}
                        margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.borderLight} />
                        <XAxis
                          dataKey="label"
                          tick={{ fill: DARK_THEME.textSecondary, fontSize: 12 }}
                          axisLine={{ stroke: DARK_THEME.borderLight }}
                          tickLine={{ stroke: DARK_THEME.borderLight }}
                        />
                        <YAxis
                          domain={yDomain}
                          tick={{ fill: DARK_THEME.textSecondary, fontSize: 12 }}
                          axisLine={{ stroke: DARK_THEME.borderLight }}
                          tickLine={{ stroke: DARK_THEME.borderLight }}
                          tickFormatter={(v) => `${v}%`}
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: DARK_THEME.bgTertiary,
                            border: `1px solid ${DARK_THEME.borderLight}`,
                            borderRadius: 8,
                          }}
                          labelStyle={{ color: DARK_THEME.textPrimary, fontWeight: 'bold' }}
                          formatter={(value, name) => {
                            const numValue = value as number | null
                            return [
                              numValue !== null ? `${numValue.toFixed(1)}%` : '-',
                              name,
                            ]
                          }}
                        />
                        <Legend
                          wrapperStyle={{ paddingTop: 16 }}
                        />
                        <ReferenceLine
                          y={0}
                          stroke={DARK_THEME.textSecondary}
                          strokeDasharray="3 3"
                        />
                        {/* 最新見通し */}
                        <Line
                          type="monotone"
                          dataKey="latest"
                          name={comparison?.latest_period || '最新'}
                          stroke={currentSeriesColor}
                          strokeWidth={2}
                          dot={{ r: 5, fill: currentSeriesColor }}
                          activeDot={{ r: 7 }}
                          connectNulls
                        />
                        {/* 前回見通し */}
                        <Line
                          type="monotone"
                          dataKey="previous"
                          name={comparison?.previous_period || '前回'}
                          stroke="#888"
                          strokeWidth={2}
                          strokeDasharray="5 5"
                          dot={{ r: 4, fill: '#888' }}
                          activeDot={{ r: 6 }}
                          connectNulls
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>

                  {/* 比較テーブル */}
                  <Table
                    columns={columns}
                    dataSource={currentSeriesData}
                    rowKey="date"
                    pagination={false}
                    size="small"
                    style={{
                      backgroundColor: DARK_THEME.bgSecondary,
                    }}
                  />
                </div>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="ca_boc_rate" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
