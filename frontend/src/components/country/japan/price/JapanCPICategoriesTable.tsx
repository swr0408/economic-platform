/**
 * Japan CPI 10 Major Categories Card Component
 * 全国CPI 10大費目別カード（独立カード）
 *
 * 表示データ:
 * - 当月と前月の前年比、寄与度
 * - 10大費目: 食料、住居、光熱・水道、家具・家事用品、被服及び履物、
 *            保健医療、交通・通信、教育、教養娯楽、諸雑費
 */

import { useEffect, useState } from 'react'
import { Table, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import {
  fetchCPICategoriesData,
  formatCategoryDate,
  type CPICategory,
  type CPICategoriesResponse,
} from '../../../../utils/japan/cpiApi'

const { Text } = Typography

interface TableRow {
  key: string
  category: string
  currentYoY: number | null
  currentContribution: number | null
  previousYoY: number | null
  previousContribution: number | null
}

export default function JapanCPICategoriesCard() {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<TableRow[]>([])
  const [currentMonth, setCurrentMonth] = useState<string>('')
  const [previousMonth, setPreviousMonth] = useState<string>('')
  const [error, setError] = useState<string | null>(null)
  const [response, setResponse] = useState<CPICategoriesResponse | null>(null)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetchCPICategoriesData()
      setResponse(res)

      if (res.error) {
        setError(res.error)
        return
      }

      if (res.data && res.data.categories) {
        setCurrentMonth(res.data.current_month)
        setPreviousMonth(res.data.previous_month)

        const tableData: TableRow[] = res.data.categories.map((cat: CPICategory) => ({
          key: cat.code,
          category: cat.name,
          currentYoY: cat.current.yoy,
          currentContribution: cat.current.contribution,
          previousYoY: cat.previous.yoy,
          previousContribution: cat.previous.contribution,
        }))

        setData(tableData)
      }
    } catch (err) {
      console.error('Error fetching CPI categories data:', err)
      setError('データの読み込みに失敗しました')
    } finally {
      setLoading(false)
    }
  }

  const formatValueWithColor = (value: number | null, decimals: number = 1) => {
    if (value === null) return <Text type="secondary">-</Text>
    const formatted = value.toFixed(decimals)
    const color = value > 0 ? '#3f8600' : value < 0 ? '#cf1322' : undefined
    return <span style={{ color }}>{value > 0 ? '+' : ''}{formatted}</span>
  }

  const columns: ColumnsType<TableRow> = [
    {
      title: '',
      dataIndex: 'category',
      key: 'category',
      align: 'center',
      width: 140,
      fixed: 'left',
      render: (text: string) => <strong>{text}</strong>,
    },
    {
      title: formatCategoryDate(currentMonth),
      children: [
        {
          title: '前年比（%）',
          dataIndex: 'currentYoY',
          key: 'currentYoY',
          align: 'center',
          width: 100,
          render: (value: number | null) => formatValueWithColor(value, 1),
        },
        {
          title: '寄与度',
          dataIndex: 'currentContribution',
          key: 'currentContribution',
          align: 'center',
          width: 80,
          render: (value: number | null) => formatValueWithColor(value, 2),
        },
      ],
    },
    {
      title: formatCategoryDate(previousMonth),
      children: [
        {
          title: '前年比（%）',
          dataIndex: 'previousYoY',
          key: 'previousYoY',
          align: 'center',
          width: 100,
          render: (value: number | null) => formatValueWithColor(value, 1),
        },
        {
          title: '寄与度',
          dataIndex: 'previousContribution',
          key: 'previousContribution',
          align: 'center',
          width: 80,
          render: (value: number | null) => formatValueWithColor(value, 2),
        },
      ],
    },
  ]

  // 次回発表日のフォーマット
  const formatNextRelease = () => {
    if (!response?.next_release) return null
    const nr = response.next_release
    if (nr.datetime_jst) {
      const dt = new Date(nr.datetime_jst)
      return `${dt.getMonth() + 1}/${dt.getDate()} ${dt.getHours().toString().padStart(2, '0')}:${dt.getMinutes().toString().padStart(2, '0')}`
    }
    if (nr.date) {
      const dt = new Date(nr.date)
      return `${dt.getMonth() + 1}/${dt.getDate()}`
    }
    return null
  }

  // ローディング状態
  if (loading) {
    return <LoadingChart title="CPI 10大費目別" />
  }

  // エラー状態
  if (error) {
    return (
      <ChartContainer title="CPI 10大費目別" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>
          {error}
        </div>
      </ChartContainer>
    )
  }

  return (
    <div id="japan-cpi-categories-card">
      <ChartContainer
        title="CPI 10大費目別"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="総務省統計局"
        sourceUrl="https://www.stat.go.jp/data/cpi/"
        handbookId="cpi-categories"
      >
        {/* 次回発表日 */}
        {response?.next_release && (
          <div style={{ marginBottom: 12, fontSize: 13, color: '#94a3b8' }}>
            次回発表: {formatNextRelease()}
          </div>
        )}

        <Table
          columns={columns}
          dataSource={data}
          pagination={false}
          bordered
          size="small"
          scroll={{ x: 600 }}
        />
      </ChartContainer>
    </div>
  )
}
