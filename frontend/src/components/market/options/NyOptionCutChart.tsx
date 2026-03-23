import { useMemo } from 'react'
import { Typography, Table, Spin, Tag, Image } from 'antd'
import { LinkOutlined, ClockCircleOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import ChartContainer from '../../common/ChartContainer'

const { Text } = Typography

// ===== Types =====

interface ExpiryItem {
  pair: string
  strike: number
  amount_mn: number
  amount_str: string
}

interface NyOptionCutData {
  date: string
  headline: string
  article_body: string
  image_url: string
  table_image_url: string | null
  date_published: string
  author: string
  expiry_data: ExpiryItem[]
  source_url: string
}

interface NyOptionCutResponse {
  data: NyOptionCutData | null
  status: 'published' | 'not_published' | 'weekend'
  cached: boolean
  source: string
  last_updated: string | null
}

// ===== Colors =====

const PAIR_COLORS: Record<string, string> = {
  'EUR/USD': '#3b82f6',
  'USD/JPY': '#ef4444',
  'GBP/USD': '#22c55e',
  'USD/CHF': '#f59e0b',
  'USD/CAD': '#8b5cf6',
  'AUD/USD': '#06b6d4',
  'NZD/USD': '#14b8a6',
  'EUR/GBP': '#ec4899',
  'EUR/JPY': '#f97316',
}

// ===== Hook =====

function useNyOptionCutData() {
  return useQuery({
    queryKey: ['market', 'ny-option-cut'],
    queryFn: async () => {
      const { data } = await axios.get<NyOptionCutResponse>('/api/market/ny-option-cut')
      return data
    },
    staleTime: 30 * 60 * 1000,
    refetchOnMount: false,
  })
}

// ===== Helper =====

function formatPublishedDate(dateStr: string): string {
  try {
    const d = new Date(dateStr)
    const jst = new Date(d.getTime() + 9 * 60 * 60 * 1000)
    const month = jst.getMonth() + 1
    const day = jst.getDate()
    const hours = jst.getUTCHours().toString().padStart(2, '0')
    const minutes = jst.getUTCMinutes().toString().padStart(2, '0')
    return `${month}/${day} ${hours}:${minutes} JST`
  } catch {
    return dateStr
  }
}

// ===== Component =====

export default function NyOptionCutChart() {
  const { data: response, isLoading } = useNyOptionCutData()

  const tableData = useMemo(() => {
    if (!response?.data?.expiry_data) return []
    return response.data.expiry_data.map((item, idx) => ({
      key: idx,
      ...item,
    }))
  }, [response])

  const columns = useMemo(() => [
    {
      title: '通貨ペア',
      dataIndex: 'pair',
      key: 'pair',
      width: 120,
      render: (pair: string) => (
        <Tag color={PAIR_COLORS[pair] || '#64748b'} style={{ fontWeight: 600 }}>
          {pair}
        </Tag>
      ),
      onCell: (record: ExpiryItem & { key: number }, index: number | undefined) => {
        if (index === undefined) return {}
        const data = tableData
        // 同一ペアの連続行をマージ
        if (index > 0 && data[index].pair === data[index - 1].pair) {
          return { rowSpan: 0 }
        }
        let count = 1
        for (let i = index + 1; i < data.length && data[i].pair === record.pair; i++) {
          count++
        }
        return { rowSpan: count }
      },
    },
    {
      title: 'ストライク',
      dataIndex: 'strike',
      key: 'strike',
      width: 120,
      render: (strike: number) => (
        <Text style={{ color: '#f1f5f9', fontFamily: 'monospace', fontWeight: 600 }}>
          {strike}
        </Text>
      ),
    },
    {
      title: '想定元本',
      dataIndex: 'amount_str',
      key: 'amount_str',
      render: (amount: string) => (
        <Text style={{ color: '#94a3b8' }}>{amount}</Text>
      ),
    },
  ], [tableData])

  return (
    <ChartContainer
      title="NYオプションカット (10:00 AM ET)"
      dataSource="investingLive"
      sourceUrl="https://investinglive.com/Orders"
      showPeriodSelector={false}
      handbookId="ny-option-cut"
    >
      {isLoading && (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Spin size="large" />
        </div>
      )}

      {!isLoading && response?.status === 'not_published' && (
        <div style={{
          textAlign: 'center',
          padding: 40,
          color: '#94a3b8',
          background: '#0f172a',
          borderRadius: 8,
          border: '1px solid #1e293b',
        }}>
          <ClockCircleOutlined style={{ fontSize: 28, marginBottom: 12, display: 'block' }} />
          <Text style={{ color: '#94a3b8', fontSize: 14 }}>
            本日の記事はまだ公開されていません
          </Text>
          <br />
          <Text style={{ color: '#64748b', fontSize: 12 }}>
            通常 14:00〜15:00 JST 頃に公開されます
          </Text>
        </div>
      )}

      {!isLoading && response?.status === 'weekend' && (
        <div style={{
          textAlign: 'center',
          padding: 40,
          color: '#94a3b8',
          background: '#0f172a',
          borderRadius: 8,
          border: '1px solid #1e293b',
        }}>
          <Text style={{ color: '#94a3b8', fontSize: 14 }}>
            週末のため更新はありません
          </Text>
        </div>
      )}

      {!isLoading && response?.data && (
        <>
          {/* 公開情報 */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 12,
            flexWrap: 'wrap',
            gap: 8,
          }}>
            <Text style={{ color: '#94a3b8', fontSize: 12 }}>
              {response.data.date_published && formatPublishedDate(response.data.date_published)}
              {response.data.author && ` | ${response.data.author}`}
            </Text>
            <a
              href={response.data.source_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: '#60a5fa', fontSize: 12 }}
            >
              <LinkOutlined /> 元記事を見る
            </a>
          </div>

          {/* テーブル画像（Seleniumで取得したスクリーンショット） */}
          {response.data.table_image_url && (
            <div style={{ textAlign: 'center', marginBottom: 16 }}>
              <Image
                src={`/api/market/ny-option-cut/table-image?t=${response.data.date}`}
                alt="FX Option Expiries Table"
                style={{
                  maxWidth: '100%',
                  borderRadius: 8,
                  border: '1px solid #334155',
                  cursor: 'pointer',
                }}
                preview={{ mask: 'クリックで拡大' }}
                placeholder={
                  <div style={{ padding: 40, background: '#1e293b', borderRadius: 8 }}>
                    <Spin />
                  </div>
                }
              />
            </div>
          )}

          {/* パース済みオプションデータテーブル */}
          {tableData.length > 0 && (
            <Table
              dataSource={tableData}
              columns={columns}
              size="small"
              pagination={false}
              bordered
              style={{ marginBottom: 16 }}
              className="dark-table"
            />
          )}

          {/* 記事分析テキスト */}
          {response.data.article_body && (
            <div style={{
              padding: 16,
              background: '#0f172a',
              borderRadius: 8,
              border: '1px solid #1e293b',
            }}>
              <Text style={{ color: '#94a3b8', whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.7 }}>
                {response.data.article_body}
              </Text>
            </div>
          )}
        </>
      )}
    </ChartContainer>
  )
}
