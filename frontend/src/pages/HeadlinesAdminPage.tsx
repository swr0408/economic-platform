import { Card, Typography, Tag, Button, Table, Space, Spin, message } from 'antd'
import {
  CheckCircleOutlined, CloseCircleOutlined,
  ApiOutlined, CloudDownloadOutlined, TranslationOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { useAdminStatus, useRSSLogs, useRunRSSBackfill } from '../hooks/useHeadlines'

const { Text, Title } = Typography

const colors = {
  bgPrimary: '#0f172a',
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  accent: '#10b981',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textTertiary: '#64748b',
  border: '#334155',
}

function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <Tag
      icon={ok ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
      color={ok ? 'success' : 'error'}
      style={{ fontSize: 12 }}
    >
      {label}
    </Tag>
  )
}

function HeadlinesAdminPage() {
  const { data: status, isLoading } = useAdminStatus()
  const { data: logs = [] } = useRSSLogs(20)
  const rssRun = useRunRSSBackfill()

  const handleRSSRun = async () => {
    try {
      const result = await rssRun.mutateAsync()
      message.success(`RSS取得完了: ${result.items_seen || 0}件取得, ${result.items_inserted || 0}件挿入`)
    } catch (e: any) {
      message.error(e.message)
    }
  }

  if (isLoading) {
    return <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>
  }

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto' }}>
      <Title level={4} style={{ color: colors.textPrimary, marginBottom: 16 }}>
        <ApiOutlined style={{ marginRight: 8, color: colors.accent }} />
        ヘッドライン管理
      </Title>

      {/* Status Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
        {/* Discord */}
        <Card size="small" style={{ background: colors.bgSecondary, borderColor: colors.border }}>
          <Space direction="vertical" size={4} style={{ width: '100%' }}>
            <Text strong style={{ color: colors.textPrimary }}>
              <ApiOutlined style={{ marginRight: 4 }} /> Discord
            </Text>
            <StatusBadge ok={status?.discord?.is_running || false} label={status?.discord?.is_running ? '稼働中' : '停止'} />
            <StatusBadge ok={status?.discord?.is_connected || false} label={status?.discord?.is_connected ? '接続中' : '未接続'} />
            {status?.discord?.guild_count !== undefined && (
              <Text style={{ color: colors.textSecondary, fontSize: 11 }}>
                {status.discord.guild_count} サーバー
              </Text>
            )}
          </Space>
        </Card>

        {/* RSS */}
        <Card size="small" style={{ background: colors.bgSecondary, borderColor: colors.border }}>
          <Space direction="vertical" size={4} style={{ width: '100%' }}>
            <Text strong style={{ color: colors.textPrimary }}>
              <CloudDownloadOutlined style={{ marginRight: 4 }} /> RSS補填
            </Text>
            <StatusBadge ok={status?.rss?.is_running || false} label={status?.rss?.is_running ? '稼働中' : '停止'} />
            <Text style={{ color: colors.textSecondary, fontSize: 11 }}>
              最終取得: {status?.rss?.last_fetch_at
                ? dayjs(status.rss.last_fetch_at).format('MM/DD HH:mm')
                : '-'}
            </Text>
            <Text style={{ color: colors.textSecondary, fontSize: 11 }}>
              前回: {status?.rss?.last_items_seen || 0}件取得 / {status?.rss?.last_items_inserted || 0}件挿入
            </Text>
            <Button
              size="small"
              icon={<PlayCircleOutlined />}
              onClick={handleRSSRun}
              loading={rssRun.isPending}
              style={{ marginTop: 4 }}
            >
              手動実行
            </Button>
          </Space>
        </Card>

        {/* Translation */}
        <Card size="small" style={{ background: colors.bgSecondary, borderColor: colors.border }}>
          <Space direction="vertical" size={4} style={{ width: '100%' }}>
            <Text strong style={{ color: colors.textPrimary }}>
              <TranslationOutlined style={{ marginRight: 4 }} /> 翻訳ワーカー
            </Text>
            <StatusBadge ok={status?.translation?.is_running || false} label={status?.translation?.is_running ? '稼働中' : '停止'} />
            <Text style={{ color: colors.textSecondary, fontSize: 11 }}>
              待機中: {status?.translation?.pending_count || 0}件
            </Text>
            <Text style={{ color: status?.translation?.failed_count ? '#ef4444' : colors.textSecondary, fontSize: 11 }}>
              失敗: {status?.translation?.failed_count || 0}件
            </Text>
          </Space>
        </Card>
      </div>

      {/* RSS Logs Table */}
      <Card
        title={<Text style={{ color: colors.textPrimary }}>RSS取得ログ</Text>}
        size="small"
        style={{ background: colors.bgSecondary, borderColor: colors.border }}
      >
        <Table
          dataSource={logs}
          rowKey="id"
          size="small"
          pagination={false}
          scroll={{ x: 600 }}
          columns={[
            {
              title: '時刻',
              dataIndex: 'fetched_at',
              width: 130,
              render: (v: string) => dayjs(v).format('MM/DD HH:mm:ss'),
            },
            {
              title: 'HTTP',
              dataIndex: 'http_status',
              width: 60,
              render: (v: number) => (
                <Tag color={v === 200 ? 'success' : v === 304 ? 'default' : 'error'} style={{ margin: 0 }}>
                  {v}
                </Tag>
              ),
            },
            { title: '取得', dataIndex: 'items_seen', width: 60 },
            { title: '挿入', dataIndex: 'items_inserted', width: 60 },
            { title: '重複', dataIndex: 'items_deduped', width: 60 },
          ]}
        />
      </Card>
    </div>
  )
}

export default HeadlinesAdminPage
