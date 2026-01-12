/**
 * BOJ Tankan Unified Table Component
 * 日銀短観 統合テーブル（6種類のデータを左右ボタンで切り替え表示）
 *
 * 1. 業況判断指数（DI） - 大企業製造業/非製造業の業況判断と先行き
 * 2. 設備投資額 - 大企業製造業/非製造業の投資額と修正率
 * 3. 生産・営業用設備判断指数（DI）
 * 4. 雇用人員判断指数（DI）
 * 5. 仕入価格判断指数（DI）
 * 6. 販売価格判断指数（DI）
 */

import { useEffect, useState, useMemo } from 'react'
import { Table, Button } from 'antd'
import { LeftOutlined, RightOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import DataTablePagination from '../../../common/DataTablePagination'

import {
  fetchBOJTankanData,
  formatQuarterDate as formatQuarterDateDI,
  type BOJTankanDataPoint,
} from '../../../../utils/japan/bojTankanApi'

import {
  fetchBOJTankanComprehensiveTable,
  formatQuarterDate as formatQuarterDateComp,
  formatFiscalYearDate,
  type DataType,
  type BOJTankanComprehensiveDataPoint,
} from '../../../../utils/japan/bojTankanComprehensiveApi'

type UnifiedDataType = 'business_conditions' | DataType

interface DataTypeConfig {
  type: UnifiedDataType
  displayName: string
}

const DATA_TYPES: DataTypeConfig[] = [
  { type: 'business_conditions', displayName: '業況判断指数（DI）' },
  { type: 'capital_investment', displayName: '設備投資額' },
  { type: 'production_facilities', displayName: '生産・営業用設備判断指数（DI）' },
  { type: 'employment', displayName: '雇用人員判断指数（DI）' },
  { type: 'purchase_price', displayName: '仕入価格判断指数（DI）' },
  { type: 'selling_price', displayName: '販売価格判断指数（DI）' },
]

interface TableRow {
  key: string
  quarter: string
  [key: string]: string | number | null | undefined
}

const INITIAL_ROW_COUNT = 5
const INCREMENT_COUNT = 10

export default function BOJTankanUnifiedTable() {
  const [currentDataTypeIndex, setCurrentDataTypeIndex] = useState(0)
  const [diData, setDiData] = useState<BOJTankanDataPoint[]>([])
  const [comprehensiveData, setComprehensiveData] = useState<BOJTankanComprehensiveDataPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [visibleRowCount, setVisibleRowCount] = useState(INITIAL_ROW_COUNT)

  const currentDataType = DATA_TYPES[currentDataTypeIndex]

  // データ取得
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true)
        setError(null)

        if (currentDataType.type === 'business_conditions') {
          // 業況判断DIデータを取得
          const response = await fetchBOJTankanData()
          setDiData(response.data)
          setComprehensiveData([])
        } else {
          // 包括的データを取得
          const response = await fetchBOJTankanComprehensiveTable(currentDataType.type as DataType)
          setComprehensiveData(response.table_data)
          setDiData([])
        }

        setVisibleRowCount(INITIAL_ROW_COUNT)
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'データの取得に失敗しました'
        setError(errorMessage)
        console.error('Error loading BOJ Tankan data:', err)
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [currentDataType.type])

  const handlePrevious = () => {
    setCurrentDataTypeIndex((prev) => (prev - 1 + DATA_TYPES.length) % DATA_TYPES.length)
  }

  const handleNext = () => {
    setCurrentDataTypeIndex((prev) => (prev + 1) % DATA_TYPES.length)
  }

  const handleShowMore = () => {
    const totalCount = currentDataType.type === 'business_conditions' ? diData.length : comprehensiveData.length
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

  // カラム定義を取得
  const getColumns = (): ColumnsType<TableRow> => {
    const baseColumns: ColumnsType<TableRow> = [
      {
        title: '期間',
        dataIndex: 'quarter',
        key: 'quarter',
        align: 'center',
        width: 100,
      },
    ]

    if (currentDataType.type === 'business_conditions') {
      // 業況判断DI
      return [
        ...baseColumns,
        {
          title: '大企業製造業',
          children: [
            {
              title: '業況判断',
              dataIndex: 'large_manufacturing_current',
              key: 'large_manufacturing_current',
              width: 120,
              align: 'center' as const,
              render: renderDIValue,
            },
            {
              title: '先行き',
              dataIndex: 'large_manufacturing_outlook',
              key: 'large_manufacturing_outlook',
              width: 120,
              align: 'center' as const,
              render: renderDIValue,
            },
          ],
        },
        {
          title: '大企業非製造業',
          children: [
            {
              title: '業況判断',
              dataIndex: 'large_non_manufacturing_current',
              key: 'large_non_manufacturing_current',
              width: 120,
              align: 'center' as const,
              render: renderDIValue,
            },
            {
              title: '先行き',
              dataIndex: 'large_non_manufacturing_outlook',
              key: 'large_non_manufacturing_outlook',
              width: 120,
              align: 'center' as const,
              render: renderDIValue,
            },
          ],
        },
      ]
    } else if (currentDataType.type === 'capital_investment') {
      // 設備投資額（修正率付き）
      return [
        ...baseColumns,
        {
          title: '大企業製造業',
          dataIndex: 'large_manufacturing',
          key: 'large_manufacturing',
          width: 180,
          align: 'center' as const,
          render: (val: number | null | undefined, record: TableRow, index: number) => {
            if (val === null || val === undefined) return '-'
            // 最新値には修正率を表示
            if (index === 0 && record.large_manufacturing_revision != null) {
              const revision = record.large_manufacturing_revision as number
              return `${val.toFixed(1)}% (${revision >= 0 ? '+' : ''}${revision.toFixed(1)})`
            }
            return `${val.toFixed(1)}%`
          },
        },
        {
          title: '大企業非製造業',
          dataIndex: 'large_non_manufacturing',
          key: 'large_non_manufacturing',
          width: 180,
          align: 'center' as const,
          render: (val: number | null | undefined, record: TableRow, index: number) => {
            if (val === null || val === undefined) return '-'
            if (index === 0 && record.large_non_manufacturing_revision != null) {
              const revision = record.large_non_manufacturing_revision as number
              return `${val.toFixed(1)}% (${revision >= 0 ? '+' : ''}${revision.toFixed(1)})`
            }
            return `${val.toFixed(1)}%`
          },
        },
      ]
    } else {
      // 生産・営業用設備、雇用人員、仕入価格、販売価格
      return [
        ...baseColumns,
        {
          title: '大企業全産業',
          children: [
            {
              title: '実績',
              dataIndex: 'all_industries_current',
              key: 'all_industries_current',
              width: 100,
              align: 'center' as const,
              render: renderDIValue,
            },
            {
              title: '予測',
              dataIndex: 'all_industries_forecast',
              key: 'all_industries_forecast',
              width: 100,
              align: 'center' as const,
              render: renderDIValue,
            },
          ],
        },
        {
          title: '大企業製造業',
          children: [
            {
              title: '実績',
              dataIndex: 'large_manufacturing_current',
              key: 'large_manufacturing_current',
              width: 100,
              align: 'center' as const,
              render: renderDIValue,
            },
            {
              title: '予測',
              dataIndex: 'large_manufacturing_forecast',
              key: 'large_manufacturing_forecast',
              width: 100,
              align: 'center' as const,
              render: renderDIValue,
            },
          ],
        },
      ]
    }
  }

  // 日付フォーマット
  const formatQuarter = (dateStr: string): string => {
    if (currentDataType.type === 'business_conditions') {
      return formatQuarterDateDI(dateStr)
    } else if (currentDataType.type === 'capital_investment') {
      return formatFiscalYearDate(dateStr)
    } else {
      return formatQuarterDateComp(dateStr)
    }
  }

  // テーブルデータを変換
  const tableData = useMemo<TableRow[]>(() => {
    const rawData = currentDataType.type === 'business_conditions' ? diData : comprehensiveData

    return rawData
      .sort((a, b) => b.date.localeCompare(a.date))
      .slice(0, visibleRowCount)
      .map((point) => ({
        key: point.date,
        quarter: formatQuarter(point.date),
        ...point,
      }))
  }, [currentDataType.type, diData, comprehensiveData, visibleRowCount])

  const totalCount = currentDataType.type === 'business_conditions' ? diData.length : comprehensiveData.length

  if (loading) {
    return <LoadingChart title="日銀短観" />
  }

  if (error) {
    return (
      <ChartContainer title="日銀短観" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>{error}</div>
      </ChartContainer>
    )
  }

  if (tableData.length === 0) {
    return (
      <ChartContainer title="日銀短観" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>データがありません</div>
      </ChartContainer>
    )
  }

  const title = `日銀短観 ${currentDataType.displayName}`

  return (
    <div id="japan-boj-tankan-unified-table">
      <ChartContainer
        title={title}
        showPeriodSelector={false}
        dataSource="日本銀行"
        sourceUrl="https://www.boj.or.jp/statistics/tk/index.htm"
        extra={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Button icon={<LeftOutlined />} onClick={handlePrevious} disabled={currentDataTypeIndex === 0} size="small" />
            <span style={{ fontSize: '12px', color: '#8c8c8c', minWidth: '40px', textAlign: 'center' }}>
              {currentDataTypeIndex + 1}/{DATA_TYPES.length}
            </span>
            <Button
              icon={<RightOutlined />}
              onClick={handleNext}
              disabled={currentDataTypeIndex === DATA_TYPES.length - 1}
              size="small"
            />
          </div>
        }
      >
        {/* テーブル */}
        <Table
          columns={getColumns()}
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
