/**
 * 鉱工業生産予測指数テーブルコンポーネント（日本）
 *
 * データソース: 経済産業省 (METI)
 * Excel URL: https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_ygzosm1je.xlsx
 * PDF URL: https://www.meti.go.jp/statistics/tyo/iip/result/pdf/reference/rev_forecast.pdf
 * 更新: 月次（IIPと同時）
 *
 * 表示:
 * - 今月予測・翌月予測テーブル
 * - 補正値テーブル（PDFから抽出）
 */
import { useState, useEffect, useMemo } from 'react'
import { Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import DataTablePagination from '../../../common/DataTablePagination'
import {
  fetchJapanIIPForecastData,
  formatJapanIIPForecastDataForTable,
  formatForecastMonth,
  type JapanIIPForecastDataPoint,
  type RevisionTable,
} from '../../../../api/japanIIPForecastApi'

// =============================================================================
// 型定義
// =============================================================================

interface IIPForecastTableRow extends JapanIIPForecastDataPoint {
  key: string
}

interface RevisionTableRow {
  key: string
  [key: string]: string | number | null
}

const INITIAL_ROW_COUNT = 5
const INCREMENT_COUNT = 10

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function JapanIIPForecastTable() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<JapanIIPForecastDataPoint[]>([])
  const [forecastMonth, setForecastMonth] = useState<string | null>(null)
  const [nextMonth, setNextMonth] = useState<string | null>(null)
  const [revisionTable, setRevisionTable] = useState<RevisionTable | null>(null)
  const [visibleCount, setVisibleCount] = useState(INITIAL_ROW_COUNT)

  // データ取得
  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      setError(null)
      try {
        const response = await fetchJapanIIPForecastData()
        if (response.error) {
          setError(response.error)
        } else {
          setData(response.data)
          setForecastMonth(response.forecast_month)
          setNextMonth(response.next_month)
          setRevisionTable(response.revision_table || null)
        }
      } catch (err) {
        console.error('Failed to fetch IIP Forecast data:', err)
        setError(err instanceof Error ? err.message : 'データの取得に失敗しました')
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [])

  // テーブルデータ
  const tableData = useMemo(() => {
    if (!data) return []
    return formatJapanIIPForecastDataForTable(data)
  }, [data])

  // 表示件数制限
  const visibleData = useMemo(() => {
    return tableData.slice(0, visibleCount)
  }, [tableData, visibleCount])

  // 補正値テーブルのカラム
  const revisionTableColumns: ColumnsType<RevisionTableRow> = useMemo(() => {
    if (!revisionTable || !revisionTable.columns || revisionTable.columns.length === 0) {
      return []
    }
    return revisionTable.columns.map((col, idx) => ({
      title: col,
      dataIndex: `col${idx}`,
      key: `col${idx}`,
      align: 'center' as const,
      width: idx === 0 ? 150 : 120,
      render: (value: string | number | null) => {
        if (idx > 0 && typeof value === 'number') {
          const color = value > 0 ? '#3f8600' : value < 0 ? '#cf1322' : undefined
          return (
            <span style={{ color, fontWeight: 'bold' }}>
              {value > 0 ? '+' : ''}{value.toFixed(1)}%
            </span>
          )
        }
        return value
      },
    }))
  }, [revisionTable])

  // 補正値テーブルのデータ
  const revisionTableData = useMemo(() => {
    if (!revisionTable || !revisionTable.rows || revisionTable.rows.length === 0) {
      return []
    }
    return revisionTable.rows.map((row, rowIdx) => {
      const rowData: RevisionTableRow = { key: `rev-row-${rowIdx}` }
      row.forEach((cell, colIdx) => {
        rowData[`col${colIdx}`] = cell
      })
      return rowData
    })
  }, [revisionTable])

  // 予測テーブルのカラム
  const columns: ColumnsType<IIPForecastTableRow> = [
    {
      title: '年月',
      dataIndex: 'item_name',
      key: 'item_name',
      width: 200,
      align: 'center' as const,
    },
    {
      title: forecastMonth ? formatForecastMonth(forecastMonth) : '生産予測調査1ヶ月先',
      dataIndex: 'this_month',
      key: 'this_month',
      width: 120,
      align: 'center' as const,
      render: (value: number | null) => {
        if (value === null) return '-'
        const color = value > 0 ? '#3f8600' : value < 0 ? '#cf1322' : undefined
        return (
          <span style={{ color, fontWeight: 500 }}>
            {value > 0 ? '+' : ''}{value.toFixed(1)}%
          </span>
        )
      },
    },
    {
      title: nextMonth ? formatForecastMonth(nextMonth) : '生産予測調査2ヶ月先',
      dataIndex: 'next_month',
      key: 'next_month',
      width: 120,
      align: 'center' as const,
      render: (value: number | null) => {
        if (value === null) return '-'
        const color = value > 0 ? '#3f8600' : value < 0 ? '#cf1322' : undefined
        return (
          <span style={{ color, fontWeight: 500 }}>
            {value > 0 ? '+' : ''}{value.toFixed(1)}%
          </span>
        )
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
    return <LoadingChart title="生産予測調査" />
  }

  if (error) {
    return (
      <ChartContainer title="鉱工業生産予測指数（IIP Forecast）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>
          {error}
        </div>
      </ChartContainer>
    )
  }

  if (!data || data.length === 0) {
    return (
      <ChartContainer title="鉱工業生産予測指数（IIP Forecast）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  return (
    <div id="japan-iip-forecast-table">
      <ChartContainer
        title="鉱工業生産予測指数"
        showPeriodSelector={false}
        dataSource="経済産業省"
        sourceUrl="https://www.meti.go.jp/statistics/tyo/iip/"
      >
        {/* 補正値テーブル */}
        {revisionTable && revisionTableColumns.length > 0 && revisionTableData.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <Table
              columns={revisionTableColumns}
              dataSource={revisionTableData}
              pagination={false}
              size="small"
              bordered
              style={{ maxWidth: 400 }}
            />
          </div>
        )}

        {/* 予測テーブル */}
        <Table
          columns={columns}
          dataSource={visibleData}
          rowKey="key"
          pagination={false}
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
