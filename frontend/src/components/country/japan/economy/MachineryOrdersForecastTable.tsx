/**
 * 機械受注見通しテーブルコンポーネント（日本）
 *
 * データソース: 内閣府 経済社会総合研究所 (ESRI)
 * - 機械受注見通し調査（四半期）
 * - 達成率、前期比
 *
 * 表示:
 * - 四半期ごとの達成率・前期比テーブル
 *
 * 計算式参考:
 * - 前期比（%）= (当期見通し額 / 前期実績額 - 1) × 100
 * - 達成率 = 実績額 ÷ 見通し額（単純集計値）
 */
import { useMemo, useState, useEffect } from 'react'
import { Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import DataTablePagination from '../../../common/DataTablePagination'

import {
  fetchMachineryOrdersForecastData,
  type MachineryOrdersForecastDataPoint,
} from '../../../../api/japanMachineryOrdersForecastApi'

interface MachineryOrdersForecastTableProps {
  title?: string
}

interface TableRow extends MachineryOrdersForecastDataPoint {
  key: string
}

const INITIAL_ROW_COUNT = 5
const INCREMENT_COUNT = 10

export default function MachineryOrdersForecastTable({
  title = "民間需要（船舶・電力を除く）達成率"
}: MachineryOrdersForecastTableProps) {
  const [data, setData] = useState<MachineryOrdersForecastDataPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [visibleCount, setVisibleCount] = useState(INITIAL_ROW_COUNT)

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      setError(null)
      try {
        const response = await fetchMachineryOrdersForecastData()
        if (response.table_data) {
          setData(response.table_data)
        }
      } catch (err) {
        console.error('Failed to fetch machinery orders forecast data:', err)
        setError(err instanceof Error ? err.message : 'Failed to load data')
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [])

  const tableData = useMemo(() => {
    return data.map((item, index) => ({
      ...item,
      key: `${item.date}-${index}`
    }))
  }, [data])

  const visibleData = useMemo(() => {
    return tableData.slice(0, visibleCount)
  }, [tableData, visibleCount])

  const columns: ColumnsType<TableRow> = [
    {
      title: '期間',
      dataIndex: 'date',
      key: 'date',
      width: 100,
      align: 'center' as const,
      fixed: 'left' as const,
      render: (value: string) => {
        const date = new Date(value)
        const year = date.getFullYear()
        const month = date.getMonth() + 1

        let quarter
        if (month >= 1 && month <= 3) quarter = 'Q1'
        else if (month >= 4 && month <= 6) quarter = 'Q2'
        else if (month >= 7 && month <= 9) quarter = 'Q3'
        else quarter = 'Q4'

        return `${year} ${quarter}`
      },
    },
    {
      title: '前期比',
      dataIndex: 'qoq_change',
      key: 'qoq_change',
      width: 100,
      align: 'center' as const,
      render: (value: number | null) => {
        if (value === null || value === undefined) return '-'
        const color = value >= 0 ? '#52c41a' : '#ff4d4f'
        return <span style={{ color }}>{value >= 0 ? '+' : ''}{value.toFixed(1)}%</span>
      },
    },
    {
      title: '達成率',
      dataIndex: 'achievement_rate',
      key: 'achievement_rate',
      width: 100,
      align: 'center' as const,
      render: (value: number | null) => {
        if (value === null || value === undefined) return '-'
        return `${value.toFixed(2)}%`
      },
    },
  ]

  const handleShowMore = () => {
    setVisibleCount(prev => Math.min(prev + INCREMENT_COUNT, tableData.length))
  }

  const handleReset = () => {
    setVisibleCount(INITIAL_ROW_COUNT)
  }

  if (loading) {
    return <LoadingChart title={title} />
  }

  if (error) {
    return (
      <ChartContainer title={title} showDataSource={false}>
        <div style={{ textAlign: 'center', color: 'red', padding: '20px' }}>
          <p>Error: {error}</p>
        </div>
      </ChartContainer>
    )
  }

  if (!data || data.length === 0) {
    return (
      <ChartContainer title={title} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  return (
    <div id="machinery-orders-forecast-table">
      <ChartContainer
        title={title}
        showDataSource={true}
        dataSource="内閣府"
        sourceUrl="https://www.esri.cao.go.jp/jp/stat/juchu/juchu.html"
      >
        <Table
          columns={columns}
          dataSource={visibleData}
          rowKey="key"
          pagination={false}
          loading={loading}
          size="small"
          scroll={{ x: 'max-content' }}
          bordered
        />
        <DataTablePagination
          currentCount={visibleCount}
          totalCount={tableData.length}
          initialCount={INITIAL_ROW_COUNT}
          incrementCount={INCREMENT_COUNT}
          onShowMore={handleShowMore}
          onReset={handleReset}
          showMoreText={`さらに${INCREMENT_COUNT}件表示`}
          resetText="リセット"
          size="small"
        />
      </ChartContainer>
    </div>
  )
}
