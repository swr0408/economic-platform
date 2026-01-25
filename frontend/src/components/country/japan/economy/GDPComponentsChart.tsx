/**
 * 日本GDP構成要素チャート（前期比）
 *
 * データソース: e-Stat（内閣府）
 * 更新: 四半期毎（速報・改定値）
 *
 * 表示内容:
 * - 民間最終消費支出（前期比）- 棒グラフ
 * - 民間企業設備（前期比）- 棒グラフ
 * - PPI PCE関連項目風のレイアウト（テーブル/グラフ切替）
 */
import { useState, useEffect, useMemo } from 'react'
import { Tabs, Table, Button, Spin, Alert } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  fetchGDPComponentsData,
  type GDPComponentsData,
} from '../../../../utils/japan/gdpComponentsApi'

// 共通モジュールのインポート
import {
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  LatestValueBox,
  ZERO_LINE_PROPS,
  ViewModeButtonGroup,
  type TooltipPayloadItem,
} from '../../usa/common/ChartComponents'
import {
  TOOLTIP_STYLE,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  DARK_THEME,
  TEXT_COLORS,
} from '../../usa/common/chartConstants'

// =============================================================================
// 型定義
// =============================================================================

// 表示モード
type ViewMode = 'qoq_chart' | 'qoq_table'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'qoq_chart', label: '前期比' },
  { mode: 'qoq_table', label: '前期比（テーブル）' },
]

// マージ済みデータの型
interface MergedDataItem {
  date: string
  consumption: number | null
  investment: number | null
}

// カラー設定
const COLORS: Record<string, string> = {
  consumption: '#3b82f6',  // 民間最終消費支出（青）
  investment: '#10b981',   // 民間企業設備（緑）
}

// 項目の日本語名
const COMPONENT_LABELS: Record<string, string> = {
  consumption: '民間最終消費支出',
  investment: '民間企業設備',
}

// =============================================================================
// 四半期フォーマット
// =============================================================================

function formatQuarterLabel(dateStr: string): string {
  // YYYY-Q1 -> 2024年Q1
  const match = dateStr.match(/^(\d{4})-Q([1-4])$/)
  if (match) {
    return `${match[1]}年Q${match[2]}`
  }
  // フォールバック: 通常の日付
  const date = new Date(dateStr)
  if (!isNaN(date.getTime())) {
    const year = date.getFullYear()
    const month = date.getMonth() + 1
    const quarter = Math.ceil(month / 3)
    return `${year}年Q${quarter}`
  }
  return dateStr
}

// =============================================================================
// カスタムツールチップ
// =============================================================================

function ComponentTooltip({ active, payload, label }: {
  active?: boolean
  payload?: TooltipPayloadItem[]
  label?: string
}) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
        {formatQuarterLabel(label || '')}
      </div>
      {payload.map((item, index) => {
        const displayName = COMPONENT_LABELS[item.dataKey] || item.name
        const value = item.value
        const sign = value >= 0 ? '+' : ''
        return (
          <div
            key={index}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 4,
              fontSize: 13,
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span
                style={{
                  display: 'inline-block',
                  width: 10,
                  height: 10,
                  borderRadius: 2,
                  backgroundColor: item.color,
                  marginRight: 6,
                }}
              />
              {displayName}
            </span>
            <span style={{ fontWeight: 500, color: value >= 0 ? '#10b981' : '#ef4444' }}>
              {value != null ? `${sign}${value.toFixed(2)}%` : '-'}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

const GDPComponentsChart: React.FC = () => {
  const [data, setData] = useState<GDPComponentsData | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('qoq_chart')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(5)
  const [displayCount, setDisplayCount] = useState<number>(10)

  const INITIAL_COUNT = 5
  const INCREMENT_COUNT = 20

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await fetchGDPComponentsData()
      setData(response)
    } catch (err) {
      console.error('Error fetching GDP components data:', err)
      setError('データの取得に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  // チャート用にデータをマージ
  const mergedData = useMemo<MergedDataItem[]>(() => {
    if (!data?.series) return []

    // 全日付を収集
    const dateSet = new Set<string>()
    for (const series of data.series) {
      for (const item of series.data) {
        dateSet.add(item.date)
      }
    }

    // シリーズ名からデータをマップ
    const consumptionMap = new Map<string, number | null>()
    const investmentMap = new Map<string, number | null>()

    for (const series of data.series) {
      const map = series.name === '民間最終消費支出' ? consumptionMap : investmentMap
      for (const item of series.data) {
        map.set(item.date, item.value)
      }
    }

    // 日付ごとにマージ（新しい順にソート）
    const result: MergedDataItem[] = []
    for (const date of Array.from(dateSet).sort().reverse()) {
      result.push({
        date,
        consumption: consumptionMap.get(date) ?? null,
        investment: investmentMap.get(date) ?? null,
      })
    }

    return result
  }, [data])

  // 期間フィルタリング（グラフ用・古い順）
  const filteredData = useMemo(() => {
    if (!mergedData.length) return []

    // グラフ用に古い順に並び替え
    const sorted = [...mergedData].reverse()

    if (currentPeriod === 'default' || currentPeriod === 'all') {
      return sorted
    }

    const years = typeof currentPeriod === 'number' ? currentPeriod : 5
    const now = new Date()
    const cutoffYear = now.getFullYear() - years

    return sorted.filter(item => {
      const match = item.date.match(/^(\d{4})/)
      if (match) {
        return parseInt(match[1], 10) >= cutoffYear
      }
      return true
    })
  }, [mergedData, currentPeriod])

  // テーブル用データ（新しい順）
  const tableData = useMemo(() => {
    return mergedData.map((item, index) => ({
      ...item,
      key: item.date || index,
    }))
  }, [mergedData])

  // 表示するテーブルデータ
  const displayedTableData = tableData.slice(0, displayCount)
  const hasMoreData = tableData.length > displayCount

  const handleShowMore = () => {
    setDisplayCount((prev) => Math.min(prev + INCREMENT_COUNT, tableData.length))
  }

  const handleReset = () => {
    setDisplayCount(INITIAL_COUNT)
  }

  // 値フォーマット（テーブル用）
  const formatValue = (value: number | null | undefined) => {
    if (value === undefined || value === null) return '-'
    const formattedValue = value.toFixed(2)
    const color = value >= 0 ? TEXT_COLORS.positive : TEXT_COLORS.negative
    const prefix = value >= 0 ? '+' : ''
    return <span style={{ color, fontWeight: 500 }}>{prefix}{formattedValue}%</span>
  }

  // テーブルカラム定義
  const tableColumns = [
    {
      title: '期間',
      dataIndex: 'date',
      key: 'date',
      align: 'center' as const,
      width: 100,
      render: (text: string) => (
        <strong style={{ color: DARK_THEME.textPrimary }}>{formatQuarterLabel(text)}</strong>
      ),
    },
    {
      title: '民間最終消費支出',
      dataIndex: 'consumption',
      key: 'consumption',
      width: 140,
      align: 'center' as const,
      render: (value: number | null) => formatValue(value),
    },
    {
      title: '民間企業設備',
      dataIndex: 'investment',
      key: 'investment',
      width: 120,
      align: 'center' as const,
      render: (value: number | null) => formatValue(value),
    },
  ]

  if (loading) {
    return (
      <ChartContainer title="GDP構成要素（前期比）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16, color: DARK_THEME.textSecondary }}>
            データ読み込み中...
          </div>
        </div>
      </ChartContainer>
    )
  }

  if (error) {
    return (
      <ChartContainer title="GDP構成要素（前期比）" showPeriodSelector={false} showDataSource={false}>
        <Alert message="エラー" description={error} type="error" showIcon />
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestConsumption = data?.latest?.components?.['民間最終消費支出']
  const latestInvestment = data?.latest?.components?.['民間企業設備']

  const latestItems = [
    {
      label: COMPONENT_LABELS.consumption,
      value: latestConsumption?.value,
      color: COLORS.consumption,
      format: 'percent' as const,
    },
    {
      label: COMPONENT_LABELS.investment,
      value: latestInvestment?.value,
      color: COLORS.investment,
      format: 'percent' as const,
    },
  ]

  return (
    <div id="japan-gdp-components">
      <ChartContainer
        title="GDP構成要素（前期比）"
        showPeriodSelector={false}
        dataSource="内閣府"
        sourceUrl="https://www.esri.cao.go.jp/jp/sna/menu.html"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={latestItems}
          date={data?.latest?.date}
          dateFormatter={formatQuarterLabel}
        />

        {/* タブ切替 */}
        <Tabs
          activeKey="timeseries"
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* 表示モード切替 */}
                  <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={(mode) => { setViewMode(mode); if (mode === 'qoq_table') setDisplayCount(INITIAL_COUNT) }} />

                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
                    <Button
                      icon={<AreaChartOutlined />}
                      onClick={() => {
                        window.open('/compare?s=japan_gdp_consumption_qoq&s=japan_gdp_investment_qoq', '_blank')
                      }}
                    >
                      データ比較
                    </Button>
                  </div>

                  {/* グラフ表示 */}
                  {viewMode === 'qoq_chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <ResponsiveContainer width="100%" height={450}>
                        <BarChart data={filteredData} margin={CHART_MARGIN}>
                          <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                          <XAxis
                            dataKey="date"
                            tickFormatter={formatQuarterLabel}
                            tick={AXIS_STYLE.tick}
                            interval={Math.floor(filteredData.length / 8)}
                          />
                          <YAxis
                            domain={['auto', 'auto']}
                            tick={AXIS_STYLE.tick}
                            tickFormatter={(v) => `${v}%`}
                          />
                          <RechartsTooltip content={<ComponentTooltip />} />
                          <Legend />
                          <ReferenceLine {...ZERO_LINE_PROPS} />
                          <Bar
                            dataKey="consumption"
                            fill={COLORS.consumption}
                            name={COMPONENT_LABELS.consumption}
                          />
                          <Bar
                            dataKey="investment"
                            fill={COLORS.investment}
                            name={COMPONENT_LABELS.investment}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </>
                  )}

                  {/* テーブル表示 */}
                  {viewMode === 'qoq_table' && (
                    <>
                      <Table
                        columns={tableColumns}
                        dataSource={displayedTableData}
                        pagination={false}
                        size="small"
                        rowKey="date"
                        bordered
                        scroll={{ x: 'max-content' }}
                        style={{
                          marginBottom: 16,
                          backgroundColor: DARK_THEME.bgSecondary,
                        }}
                      />

                      {/* ページネーションコントロール */}
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'center',
                          alignItems: 'center',
                          gap: 16,
                          marginTop: 8,
                        }}
                      >
                        {hasMoreData && (
                          <Button size="small" onClick={handleShowMore}>
                            もっと見る
                          </Button>
                        )}
                        {displayCount > INITIAL_COUNT && (
                          <Button size="small" onClick={handleReset}>
                            リセット
                          </Button>
                        )}
                      </div>
                    </>
                  )}
                </>
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}

export default GDPComponentsChart
