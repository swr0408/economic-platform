/**
 * ユーザー管理画面 (master 限定)
 *
 * - GET    /api/auth/users
 * - PATCH  /api/auth/users/{id}/role
 * - PATCH  /api/auth/users/{id}/active
 *
 * バックエンド側で require_role("master") により強制されているため、
 * フロントの ProtectedRoute と二重防御となる。
 */
import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useAuth, type AuthUser, type UserRole } from '../contexts/AuthContext'

const { Title, Text } = Typography

const colors = {
  bgSecondary: '#1e293b',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  border: '#334155',
}

const ROLE_COLORS: Record<UserRole, string> = {
  master: 'gold',
  special: 'geekblue',
  general: 'default',
}

const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
  { value: 'master', label: 'master' },
  { value: 'special', label: 'special' },
  { value: 'general', label: 'general' },
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

export default function AdminUsersPage() {
  const { authFetch, user: currentUser } = useAuth()
  const [users, setUsers] = useState<AuthUser[]>([])
  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [savingId, setSavingId] = useState<number | null>(null)

  const fetchUsers = useCallback(async () => {
    setLoading(true)
    setErrorMsg(null)
    try {
      const res = await authFetch('/api/auth/users')
      if (!res.ok) {
        setErrorMsg(await readDetail(res))
        return
      }
      const data = (await res.json()) as AuthUser[]
      setUsers(data)
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'ユーザー一覧の取得に失敗しました')
    } finally {
      setLoading(false)
    }
  }, [authFetch])

  useEffect(() => {
    void fetchUsers()
  }, [fetchUsers])

  const handleRoleChange = async (id: number, role: UserRole) => {
    setSavingId(id)
    setErrorMsg(null)
    try {
      const res = await authFetch(`/api/auth/users/${id}/role`, {
        method: 'PATCH',
        body: JSON.stringify({ role }),
      })
      if (!res.ok) {
        setErrorMsg(await readDetail(res))
        return
      }
      const updated = (await res.json()) as AuthUser
      setUsers((prev) => prev.map((u) => (u.id === id ? updated : u)))
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'ロール変更に失敗しました')
    } finally {
      setSavingId(null)
    }
  }

  const handleActiveToggle = async (id: number, isActive: boolean) => {
    setSavingId(id)
    setErrorMsg(null)
    try {
      const res = await authFetch(`/api/auth/users/${id}/active`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: isActive }),
      })
      if (!res.ok) {
        setErrorMsg(await readDetail(res))
        return
      }
      const updated = (await res.json()) as AuthUser
      setUsers((prev) => prev.map((u) => (u.id === id ? updated : u)))
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : '有効状態の変更に失敗しました')
    } finally {
      setSavingId(null)
    }
  }

  const columns: ColumnsType<AuthUser> = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    {
      title: 'ユーザー名',
      dataIndex: 'username',
      render: (v: string, row) => (
        <Space>
          <Text style={{ color: colors.textPrimary }}>{v}</Text>
          {row.id === currentUser?.id && <Tag color="green">YOU</Tag>}
        </Space>
      ),
    },
    {
      title: 'メール',
      dataIndex: 'email',
      render: (v: string | null) => (
        <Text style={{ color: colors.textSecondary }}>{v ?? '-'}</Text>
      ),
    },
    {
      title: 'ロール',
      dataIndex: 'role',
      width: 200,
      render: (role: UserRole, row) => {
        const isSelf = row.id === currentUser?.id
        return (
          <Space>
            <Tag color={ROLE_COLORS[role]}>{role}</Tag>
            <Select
              size="small"
              value={role}
              options={ROLE_OPTIONS}
              disabled={isSelf || savingId === row.id}
              style={{ width: 110 }}
              onChange={(next) => {
                if (next !== role) void handleRoleChange(row.id, next)
              }}
            />
          </Space>
        )
      },
    },
    {
      title: '有効',
      dataIndex: 'is_active',
      width: 110,
      render: (active: boolean, row) => {
        const isSelf = row.id === currentUser?.id
        const sw = (
          <Switch
            checked={active}
            disabled={isSelf || savingId === row.id}
            onChange={(checked) => void handleActiveToggle(row.id, checked)}
          />
        )
        if (active) {
          // 有効化操作には確認不要
          return sw
        }
        return sw
      },
    },
    {
      title: '作成日時',
      dataIndex: 'created_at',
      render: (v: string) => (
        <Text style={{ color: colors.textSecondary, fontSize: 12 }}>
          {new Date(v).toLocaleString('ja-JP')}
        </Text>
      ),
    },
    {
      title: '最終ログイン',
      dataIndex: 'last_login_at',
      render: (v: string | null) => (
        <Text style={{ color: colors.textSecondary, fontSize: 12 }}>
          {v ? new Date(v).toLocaleString('ja-JP') : '-'}
        </Text>
      ),
    },
  ]

  // 無効化操作のみ確認ダイアログを出すために、Switch を Popconfirm でラップ版を切り替えても良いが、
  // シンプルさを優先し直接トグルにしてある。誤操作リスクを減らすには Popconfirm を導入可能。
  void Popconfirm

  return (
    <div style={{ padding: 24 }}>
      <Card
        style={{
          background: colors.bgSecondary,
          border: `1px solid ${colors.border}`,
        }}
        styles={{ body: { padding: 24 } }}
      >
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <Title level={4} style={{ color: colors.textPrimary, margin: 0 }}>
                ユーザー管理
              </Title>
              <Text style={{ color: colors.textSecondary, fontSize: 13 }}>
                master ロール限定 (バックエンドでも require_role("master") によって強制されます)
              </Text>
            </div>
            <Button onClick={() => void fetchUsers()} loading={loading}>
              再読み込み
            </Button>
          </div>

          {errorMsg && (
            <Alert message={errorMsg} type="error" showIcon closable onClose={() => setErrorMsg(null)} />
          )}

          <Table
            rowKey="id"
            size="small"
            loading={loading}
            dataSource={users}
            columns={columns}
            pagination={false}
          />
        </Space>
      </Card>
    </div>
  )
}
