/**
 * 可視性管理画面 (master 限定)
 *
 * - GET    /api/admin/visibility               (一覧)
 * - PUT    /api/admin/visibility/{code}        (upsert)
 * - DELETE /api/admin/visibility/{code}        (削除 = public 扱いに戻す)
 *
 * バックエンド側で require_role("master") により強制されているため、
 * フロントの ProtectedRoute と二重防御となる。
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { EyeOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { useAuth } from '../contexts/AuthContext'
import { invalidateVisibilityCache } from '../hooks/useVisibleIndicators'

const { Title, Text } = Typography

const colors = {
  bgPrimary: '#0f172a',
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  border: '#334155',
}

type Visibility = 'public' | 'special' | 'master'

interface VisibilityRow {
  indicator_code: string
  visibility: Visibility
  reason: string | null
  updated_at: string | null
  updated_by: number | null
}

const VIS_COLORS: Record<Visibility, string> = {
  public: 'green',
  special: 'geekblue',
  master: 'gold',
}

const VIS_OPTIONS: { value: Visibility; label: string }[] = [
  { value: 'public', label: 'public (全員)' },
  { value: 'special', label: 'special (special/master)' },
  { value: 'master', label: 'master (master のみ)' },
]

async function readDetail(res: Response): Promise<string> {
  try {
    const data = await res.json()
    if (data?.detail) return typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
  } catch {
    /* ignore */
  }
  return `HTTP ${res.status}`
}

export default function AdminVisibilityPage() {
  const { authFetch } = useAuth()
  const [items, setItems] = useState<VisibilityRow[]>([])
  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [filterText, setFilterText] = useState('')
  const [filterVis, setFilterVis] = useState<Visibility | ''>('')
  const [editing, setEditing] = useState<VisibilityRow | null>(null)

  const fetchAll = useCallback(async () => {
    setLoading(true)
    setErrorMsg(null)
    try {
      const res = await authFetch('/api/admin/visibility')
      if (!res.ok) {
        setErrorMsg(await readDetail(res))
        return
      }
      const data = (await res.json()) as { items: VisibilityRow[] }
      setItems(data.items || [])
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : '取得に失敗しました')
    } finally {
      setLoading(false)
    }
  }, [authFetch])

  useEffect(() => {
    fetchAll()
  }, [fetchAll])

  const filtered = useMemo(() => {
    return items.filter((it) => {
      if (filterVis && it.visibility !== filterVis) return false
      if (filterText) {
        const t = filterText.toLowerCase()
        if (!it.indicator_code.toLowerCase().includes(t) && !(it.reason || '').toLowerCase().includes(t)) {
          return false
        }
      }
      return true
    })
  }, [items, filterText, filterVis])

  const handleSave = async (row: VisibilityRow) => {
    try {
      const res = await authFetch(`/api/admin/visibility/${encodeURIComponent(row.indicator_code)}`, {
        method: 'PUT',
        body: JSON.stringify({ visibility: row.visibility, reason: row.reason }),
      })
      if (!res.ok) {
        message.error(await readDetail(res))
        return
      }
      message.success('保存しました')
      invalidateVisibilityCache()
      setEditing(null)
      fetchAll()
    } catch (e) {
      message.error(e instanceof Error ? e.message : '保存に失敗しました')
    }
  }

  const handleDelete = async (code: string) => {
    try {
      const res = await authFetch(`/api/admin/visibility/${encodeURIComponent(code)}`, {
        method: 'DELETE',
      })
      if (!res.ok) {
        message.error(await readDetail(res))
        return
      }
      message.success('削除しました (public に戻りました)')
      invalidateVisibilityCache()
      fetchAll()
    } catch (e) {
      message.error(e instanceof Error ? e.message : '削除に失敗しました')
    }
  }

  const columns: ColumnsType<VisibilityRow> = [
    {
      title: 'indicator_code',
      dataIndex: 'indicator_code',
      key: 'indicator_code',
      sorter: (a, b) => a.indicator_code.localeCompare(b.indicator_code),
      render: (code: string) => (
        <Text style={{ color: colors.textPrimary, fontFamily: 'monospace', fontSize: 12 }}>{code}</Text>
      ),
    },
    {
      title: 'visibility',
      dataIndex: 'visibility',
      key: 'visibility',
      width: 140,
      filters: VIS_OPTIONS.map((o) => ({ text: o.label, value: o.value })),
      onFilter: (value, record) => record.visibility === value,
      render: (v: Visibility) => <Tag color={VIS_COLORS[v]}>{v}</Tag>,
    },
    {
      title: 'reason',
      dataIndex: 'reason',
      key: 'reason',
      ellipsis: true,
      render: (r: string | null) => (
        <Text style={{ color: colors.textSecondary, fontSize: 12 }}>{r || '-'}</Text>
      ),
    },
    {
      title: 'updated_at',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 160,
      render: (s: string | null) => (
        <Text style={{ color: colors.textSecondary, fontSize: 11 }}>
          {s ? new Date(s).toLocaleString('ja-JP') : '-'}
        </Text>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      render: (_, record) => (
        <Space size={4}>
          <Button size="small" onClick={() => setEditing({ ...record })}>編集</Button>
          <Popconfirm
            title="この visibility を削除しますか？"
            description="削除すると public 扱いに戻ります。"
            onConfirm={() => handleDelete(record.indicator_code)}
            okText="削除"
            cancelText="キャンセル"
          >
            <Button size="small" danger>削除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={4} style={{ color: colors.textPrimary, margin: 0 }}>
          <EyeOutlined style={{ marginRight: 8, color: '#10b981' }} />
          可視性管理
        </Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchAll} loading={loading}>
            更新
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() =>
              setEditing({
                indicator_code: '',
                visibility: 'special',
                reason: null,
                updated_at: null,
                updated_by: null,
              })
            }
          >
            新規追加
          </Button>
        </Space>
      </div>

      {errorMsg && (
        <Alert message={errorMsg} type="error" closable style={{ marginBottom: 12 }} onClose={() => setErrorMsg(null)} />
      )}

      <Card
        size="small"
        style={{ marginBottom: 12, background: colors.bgSecondary, borderColor: colors.border }}
      >
        <Space wrap>
          <Input
            placeholder="indicator_code / reason 検索"
            allowClear
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            style={{ width: 280 }}
          />
          <Select
            placeholder="visibility 絞り込み"
            allowClear
            value={filterVis || undefined}
            onChange={(v) => setFilterVis((v as Visibility) || '')}
            options={VIS_OPTIONS}
            style={{ width: 220 }}
          />
          <Text style={{ color: colors.textSecondary, fontSize: 12 }}>
            {filtered.length} / {items.length} 件
          </Text>
        </Space>
      </Card>

      <Table<VisibilityRow>
        rowKey="indicator_code"
        columns={columns}
        dataSource={filtered}
        loading={loading}
        size="small"
        pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ['25', '50', '100', '200'] }}
      />

      {/* 編集 / 新規モーダル */}
      <Modal
        title={editing && items.find((i) => i.indicator_code === editing.indicator_code) ? 'visibility を編集' : 'visibility を追加'}
        open={!!editing}
        onCancel={() => {
          setEditing(null)
        }}
        onOk={() => editing && handleSave(editing)}
        okText="保存"
        cancelText="キャンセル"
        destroyOnClose
      >
        {editing && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <div>
              <Text style={{ color: colors.textSecondary }}>indicator_code</Text>
              <Input
                value={editing.indicator_code}
                onChange={(e) => setEditing({ ...editing, indicator_code: e.target.value })}
                disabled={!!items.find((i) => i.indicator_code === editing.indicator_code)}
                placeholder="例: usa:economy:retail_sales"
              />
            </div>
            <div>
              <Text style={{ color: colors.textSecondary }}>visibility</Text>
              <Select
                value={editing.visibility}
                onChange={(v) => setEditing({ ...editing, visibility: v as Visibility })}
                options={VIS_OPTIONS}
                style={{ width: '100%' }}
              />
            </div>
            <div>
              <Text style={{ color: colors.textSecondary }}>reason (任意)</Text>
              <Input.TextArea
                value={editing.reason || ''}
                onChange={(e) => setEditing({ ...editing, reason: e.target.value || null })}
                rows={2}
                placeholder="例: 有料サービスのスクリーンショット"
              />
            </div>
          </Space>
        )}
      </Modal>
    </div>
  )
}
