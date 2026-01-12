/**
 * BOJ政策金利期待テーブルコンポーネント
 *
 * データソース: 東京短資
 * URL: https://www.tokyotanshi.co.jp/archives/15647
 * 更新頻度: 営業日毎、15:30 JST頃
 */
import { useEffect, useState } from 'react'
import { Table, Spin, Alert } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import ChartContainer from '../../../common/ChartContainer'
import {
  fetchBOJMeetingExpectations,
  formatMeetingDate,
  formatOISRate,
  formatDifference,
  formatProbability,
  type BOJMeetingExpectation,
  type BOJMeetingExpectationsData,
} from '../../../../utils/japan/bojMeetingExpectationsApi'

const BOJMeetingExpectationsTable: React.FC = () => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<BOJMeetingExpectationsData | null>(null)

  useEffect(() => {
    let isSubscribed = true

    fetchBOJMeetingExpectations()
      .then((result) => {
        if (isSubscribed) {
          setData(result)
          setError(null)
        }
      })
      .catch((err) => {
        if (isSubscribed) {
          setError('BOJ会合期待データの取得に失敗しました')
          console.error('Error fetching BOJ meeting expectations:', err)
        }
      })
      .finally(() => {
        if (isSubscribed) {
          setLoading(false)
        }
      })

    return () => {
      isSubscribed = false
    }
  }, [])

  const columns: ColumnsType<BOJMeetingExpectation> = [
    {
      title: '日銀会合日',
      dataIndex: 'meeting_date',
      key: 'meeting_date',
      render: (date: string) => formatMeetingDate(date),
      width: 150,
    },
    {
      title: 'OIS気配値 (%)',
      dataIndex: 'ois_rate',
      key: 'ois_rate',
      render: (value: number | null) => formatOISRate(value),
      align: 'right',
      width: 180,
    },
    {
      title: '対前会合差分 (%)',
      dataIndex: 'difference',
      key: 'difference',
      render: (value: number | null) => formatDifference(value),
      align: 'right',
      width: 150,
    },
    {
      title: '政策金利変更織込み比率',
      dataIndex: 'probability',
      key: 'probability',
      render: (value: number | null) => formatProbability(value),
      align: 'right',
      width: 220,
    },
  ]

  if (loading) {
    return (
      <ChartContainer title="日銀政策金利期待（OIS）" dataSource="東京短資" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: '50px 0' }}>
          <Spin size="large" />
        </div>
      </ChartContainer>
    )
  }

  if (error || !data) {
    return (
      <ChartContainer title="日銀政策金利期待（OIS）" dataSource="東京短資" showPeriodSelector={false}>
        <Alert
          message="データ取得エラー"
          description={error || 'データの読み込みに失敗しました'}
          type="error"
          showIcon
        />
      </ChartContainer>
    )
  }

  return (
    <ChartContainer
      title="日銀政策金利期待（OIS）"
      dataSource="東京短資"
      sourceUrl="https://www.tokyotanshi.co.jp/archives/15647"
      showPeriodSelector={false}
    >
      <Table
        columns={columns}
        dataSource={data.meetings}
        rowKey="meeting_date"
        pagination={false}
        bordered
        size="small"
        scroll={{ x: 700 }}
      />
    </ChartContainer>
  )
}

export default BOJMeetingExpectationsTable
