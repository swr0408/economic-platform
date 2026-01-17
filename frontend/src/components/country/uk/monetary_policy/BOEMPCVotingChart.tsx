/**
 * BOE MPC投票履歴チャートコンポーネント
 *
 * BOE金融政策委員会メンバーの投票履歴をテーブル形式で表示
 *
 * データソース:
 * - Bank of England Excel file
 *
 * 発表スケジュール:
 * - MPC発表日（年8回程度）
 * - 発表時刻: 12:00 ロンドン時間（20:00-21:00 JST）
 */
import { useState, useMemo } from 'react'
import { Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import ChartContainer from '../../../common/ChartContainer'
import DataTablePagination from '../../../common/DataTablePagination'
import LoadingChart from '../../../common/LoadingChart'
import { SimpleLatestValueBox } from '../../usa/common/ChartComponents'
import { CHART_COLORS } from '../../usa/common/chartConstants'

// 型定義
import type { BOEMPCVotingData } from '../../../../hooks/useDashboardData'

interface BOEMPCVotingChartProps {
  data: BOEMPCVotingData | null
}

interface MPCVotingRecord {
  date: string
  bank_rate: number | null
  [key: string]: string | number | null | undefined
}

const INITIAL_ROW_COUNT = 5
const INCREMENT_COUNT = 5

export default function BOEMPCVotingChart({ data }: BOEMPCVotingChartProps) {
  const [visibleCount, setVisibleCount] = useState(INITIAL_ROW_COUNT)

  // データを取得
  const tableData = useMemo<MPCVotingRecord[]>(() => {
    if (!data?.data || data.data.length === 0) return []
    return data.data
  }, [data])

  const members = useMemo<string[]>(() => {
    if (!data?.members) return []
    return data.members
  }, [data])

  const visibleData = useMemo(() => {
    return tableData.slice(0, visibleCount)
  }, [tableData, visibleCount])

  // 最新の政策金利を取得
  const latestBankRate = useMemo(() => {
    if (tableData.length === 0) return null
    const latest = tableData[0]
    return {
      value: latest.bank_rate,
      date: latest.date
    }
  }, [tableData])

  const hasData = tableData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="MPC BOEメンバー投票履歴" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="MPC BOEメンバー投票履歴" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#94a3b8' }}>
          データが見つかりませんでした
        </div>
      </ChartContainer>
    )
  }

  // カラム定義: 日付、政策金利、各メンバー
  const columns: ColumnsType<MPCVotingRecord> = [
    {
      title: '日付',
      dataIndex: 'date',
      key: 'date',
      width: 100,
      align: 'center',
      fixed: 'left',
      render: (value: string) => {
        const date = new Date(value)
        return date.toLocaleDateString('ja-JP', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit'
        })
      }
    },
    {
      title: '政策金利',
      dataIndex: 'bank_rate',
      key: 'bank_rate',
      width: 80,
      align: 'center',
      fixed: 'left',
      render: (value: number | null) => {
        if (value === null) return 'N/A'
        return `${(value * 100).toFixed(2)}%`
      }
    },
    ...members.map(memberName => ({
      title: memberName,
      dataIndex: memberName,
      key: memberName,
      width: 80,
      align: 'center' as const,
      render: (value: number | null | undefined) => {
        if (value === null || value === undefined) return '-'
        return `${(value * 100).toFixed(2)}%`
      }
    }))
  ]

  return (
    <div id="boe-mpc-voting-chart">
      <ChartContainer
        title="MPC BOEメンバー投票履歴"
        showPeriodSelector={false}
        dataSource="Bank of England"
        sourceUrl="https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="最新の政策金利"
          value={latestBankRate?.value !== null && latestBankRate?.value !== undefined
            ? latestBankRate.value * 100
            : undefined}
          valueColor={CHART_COLORS.primary}
          date={latestBankRate?.date}
          nextRelease={data.next_release ? {
            date: data.next_release.date,
            label: data.next_release.time_jst ? `${data.next_release.time_jst} JST` : undefined
          } : null}
          format="percent"
          decimals={2}
        />

        <Table
          columns={columns}
          dataSource={visibleData}
          pagination={false}
          rowKey={(record) => record.date}
          size="small"
          scroll={{ x: 'max-content' }}
          style={{ marginTop: 16 }}
        />
        <DataTablePagination
          currentCount={visibleCount}
          totalCount={tableData.length}
          initialCount={INITIAL_ROW_COUNT}
          incrementCount={INCREMENT_COUNT}
          onShowMore={() => setVisibleCount(prev => Math.min(prev + INCREMENT_COUNT, tableData.length))}
          onReset={() => setVisibleCount(INITIAL_ROW_COUNT)}
        />
      </ChartContainer>
    </div>
  )
}
