/**
 * 日本 価格DIスプレッドテーブルコンポーネント
 *
 * 販売価格判断DI - 仕入価格判断DI で計算
 * 企業のマージン（採算）とインフレ転嫁状況を表す
 *
 * - マイナス幅が大きいほど、企業のマージンが圧縮されている
 * - プラスになると、コスト上昇を価格転嫁できている状態
 *
 * データソース:
 * - 日銀短観（BOJ Tankan Survey）
 * - 販売価格判断DI: A12シート
 * - 仕入価格判断DI: A13シート
 *
 * 発表スケジュール:
 * - 四半期（4月、7月、10月、12月）
 */

import { useEffect, useState, useMemo } from 'react'
import { Table } from 'antd'
import { CalendarOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import DataTablePagination from '../../../common/DataTablePagination'

import { TEXT_COLORS } from '../../usa/common/chartConstants'

// =============================================================================
// 型定義
// =============================================================================

interface PriceDISpreadDataPoint {
  date: string
  value: number
  spread: number
  large_manufacturing_spread: number | null
  all_industries_spread: number | null
  large_manufacturing_selling: number | null
  large_manufacturing_purchase: number | null
  all_industries_selling: number | null
  all_industries_purchase: number | null
}

interface NextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  label?: string
}

interface PriceDISpreadResponse {
  data: PriceDISpreadDataPoint[]
  latest: PriceDISpreadDataPoint | null
  metadata: {
    source: string
    description: string
    unit: string
    frequency: string
  }
  next_release?: NextRelease
  cached: boolean
  source: string
  last_updated: string
}

interface TableRow {
  key: string
  quarter: string
  large_manufacturing_selling: number | null
  large_manufacturing_purchase: number | null
  large_manufacturing_spread: number | null
  all_industries_selling: number | null
  all_industries_purchase: number | null
  all_industries_spread: number | null
}

// =============================================================================
// 定数
// =============================================================================

const INITIAL_ROW_COUNT = 5
const INCREMENT_COUNT = 10

// =============================================================================
// ユーティリティ関数
// =============================================================================

// 四半期日付をフォーマット（例：2025Q4）
function formatQuarterDate(dateStr: string): string {
  const date = new Date(dateStr)
  const year = date.getFullYear()
  const month = date.getMonth() + 1

  let quarter: number
  if (month <= 3) quarter = 1
  else if (month <= 6) quarter = 2
  else if (month <= 9) quarter = 3
  else quarter = 4

  return `${year}Q${quarter}`
}

// 次回発表日時のフォーマット
function formatNextRelease(nextRelease: NextRelease | null | undefined): string | null {
  if (!nextRelease) return null
  if (nextRelease.datetime_jst) {
    const dt = new Date(nextRelease.datetime_jst)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    const hours = dt.getHours().toString().padStart(2, '0')
    const minutes = dt.getMinutes().toString().padStart(2, '0')
    return `${month}/${day} ${hours}:${minutes}`
  }
  if (nextRelease.time_jst && nextRelease.date) {
    const dt = new Date(nextRelease.date)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    return `${month}/${day} ${nextRelease.time_jst}`
  }
  if (nextRelease.date) {
    const dt = new Date(nextRelease.date)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    return `${month}/${day}`
  }
  return null
}

// =============================================================================
// API呼び出し関数
// =============================================================================

async function fetchPriceDISpreadData(): Promise<PriceDISpreadResponse | null> {
  try {
    const response = await fetch('/api/japan/price-di-spread')
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    return await response.json()
  } catch (error) {
    console.error('Failed to fetch price DI spread data:', error)
    return null
  }
}

// =============================================================================
// コンポーネント
// =============================================================================

export default function JapanPriceDISpreadChart() {
  const [data, setData] = useState<PriceDISpreadResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [visibleRowCount, setVisibleRowCount] = useState(INITIAL_ROW_COUNT)

  // データ取得
  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      const result = await fetchPriceDISpreadData()
      setData(result)
      setLoading(false)
    }
    loadData()
  }, [])

  const handleShowMore = () => {
    const totalCount = data?.data?.length ?? 0
    setVisibleRowCount((prev) => Math.min(prev + INCREMENT_COUNT, totalCount))
  }

  const handleReset = () => {
    setVisibleRowCount(INITIAL_ROW_COUNT)
  }

  // DI値のレンダリング（色分け）
  const renderDIValue = (val: number | null | undefined) => {
    if (val === null || val === undefined) return '-'
    const color = val > 0 ? '#3f8600' : val < 0 ? '#cf1322' : undefined
    return <span style={{ color, fontWeight: 500 }}>{val.toFixed(1)}</span>
  }

  // スプレッド値のレンダリング（色分け、強調）
  const renderSpreadValue = (val: number | null | undefined) => {
    if (val === null || val === undefined) return '-'
    const color = val >= 0 ? '#3f8600' : '#cf1322'
    return <span style={{ color, fontWeight: 600 }}>{val.toFixed(1)}</span>
  }

  // カラム定義
  const columns: ColumnsType<TableRow> = [
    {
      title: '期間',
      dataIndex: 'quarter',
      key: 'quarter',
      align: 'center',
      width: 90,
      fixed: 'left',
    },
    {
      title: '大企業製造業',
      children: [
        {
          title: '販売価格DI',
          dataIndex: 'large_manufacturing_selling',
          key: 'large_manufacturing_selling',
          width: 100,
          align: 'center' as const,
          render: renderDIValue,
        },
        {
          title: '仕入価格DI',
          dataIndex: 'large_manufacturing_purchase',
          key: 'large_manufacturing_purchase',
          width: 100,
          align: 'center' as const,
          render: renderDIValue,
        },
        {
          title: 'スプレッド',
          dataIndex: 'large_manufacturing_spread',
          key: 'large_manufacturing_spread',
          width: 100,
          align: 'center' as const,
          render: renderSpreadValue,
        },
      ],
    },
    {
      title: '全産業',
      children: [
        {
          title: '販売価格DI',
          dataIndex: 'all_industries_selling',
          key: 'all_industries_selling',
          width: 100,
          align: 'center' as const,
          render: renderDIValue,
        },
        {
          title: '仕入価格DI',
          dataIndex: 'all_industries_purchase',
          key: 'all_industries_purchase',
          width: 100,
          align: 'center' as const,
          render: renderDIValue,
        },
        {
          title: 'スプレッド',
          dataIndex: 'all_industries_spread',
          key: 'all_industries_spread',
          width: 100,
          align: 'center' as const,
          render: renderSpreadValue,
        },
      ],
    },
  ]

  // テーブルデータを変換
  const tableData = useMemo<TableRow[]>(() => {
    if (!data?.data) return []

    return data.data
      .sort((a, b) => b.date.localeCompare(a.date))
      .slice(0, visibleRowCount)
      .map((point) => ({
        key: point.date,
        quarter: formatQuarterDate(point.date),
        large_manufacturing_selling: point.large_manufacturing_selling,
        large_manufacturing_purchase: point.large_manufacturing_purchase,
        large_manufacturing_spread: point.large_manufacturing_spread,
        all_industries_selling: point.all_industries_selling,
        all_industries_purchase: point.all_industries_purchase,
        all_industries_spread: point.all_industries_spread,
      }))
  }, [data, visibleRowCount])

  const totalCount = data?.data?.length ?? 0

  // ローディング
  if (loading) {
    return <LoadingChart title="価格DIスプレッド" />
  }

  // データなし
  if (!data || !data.data || data.data.length === 0) {
    return (
      <ChartContainer title="価格DIスプレッド" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>データがありません</div>
      </ChartContainer>
    )
  }

  const nextReleaseFormatted = formatNextRelease(data.next_release)

  return (
    <div id="japan-price-di-spread-table">
      <ChartContainer
        title="価格DIスプレッド（販売価格DI - 仕入価格DI）"
        showPeriodSelector={false}
        dataSource="日本銀行（BOJ）短観"
        sourceUrl="https://www.boj.or.jp/statistics/tk/index.htm"
        extra={
          nextReleaseFormatted && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 12,
              color: TEXT_COLORS.secondary,
            }}>
              <CalendarOutlined />
              <span>次回発表: {nextReleaseFormatted}</span>
            </div>
          )
        }
      >
        {/* テーブル */}
        <Table
          columns={columns}
          dataSource={tableData}
          pagination={false}
          size="small"
          bordered
          scroll={{ x: 'max-content' }}
        />

        {/* ページネーション */}
        <DataTablePagination
          currentCount={visibleRowCount}
          totalCount={totalCount}
          initialCount={INITIAL_ROW_COUNT}
          incrementCount={INCREMENT_COUNT}
          onShowMore={handleShowMore}
          onReset={handleReset}
        />
      </ChartContainer>
    </div>
  )
}
