/**
 * ログイン画面
 *
 * 既存 EconAlpha のダークテーマ (#0f172a / #10b981) に合わせた簡素なフォーム。
 * MainLayout の外側で表示するため、ヘッダー/サイドバーは出ない。
 */
import { useState } from 'react'
import { Button, Card, Form, Input, Typography, Alert, Space } from 'antd'
import { UserOutlined, LockOutlined } from '@ant-design/icons'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const { Title, Text } = Typography

const colors = {
  bgPrimary: '#0f172a',
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  accent: '#10b981',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  border: '#334155',
}

interface LocationState {
  from?: { pathname?: string }
}

function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { login } = useAuth()
  const [submitting, setSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const from = (location.state as LocationState | null)?.from?.pathname || '/'

  const handleSubmit = async (values: { username: string; password: string }) => {
    setErrorMsg(null)
    setSubmitting(true)
    try {
      await login(values.username, values.password)
      navigate(from, { replace: true })
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'ログインに失敗しました')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        background: colors.bgPrimary,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
    >
      <Card
        style={{
          width: '100%',
          maxWidth: 420,
          background: colors.bgSecondary,
          border: `1px solid ${colors.border}`,
        }}
        styles={{ body: { padding: 32 } }}
      >
        <Space direction="vertical" size={24} style={{ width: '100%' }}>
          <div style={{ textAlign: 'center' }}>
            <Title level={3} style={{ color: colors.textPrimary, marginBottom: 4 }}>
              Econ<span style={{ color: colors.accent }}>Alpha</span>
            </Title>
            <Text style={{ color: colors.textSecondary, fontSize: 13 }}>ログイン</Text>
          </div>

          {errorMsg && (
            <Alert message={errorMsg} type="error" showIcon closable onClose={() => setErrorMsg(null)} />
          )}

          <Form layout="vertical" onFinish={handleSubmit} requiredMark={false}>
            <Form.Item
              label={<span style={{ color: colors.textSecondary }}>ユーザー名</span>}
              name="username"
              rules={[{ required: true, message: 'ユーザー名を入力してください' }]}
            >
              <Input prefix={<UserOutlined />} size="large" autoComplete="username" />
            </Form.Item>

            <Form.Item
              label={<span style={{ color: colors.textSecondary }}>パスワード</span>}
              name="password"
              rules={[{ required: true, message: 'パスワードを入力してください' }]}
            >
              <Input.Password prefix={<LockOutlined />} size="large" autoComplete="current-password" />
            </Form.Item>

            <Form.Item style={{ marginBottom: 0 }}>
              <Button
                type="primary"
                htmlType="submit"
                size="large"
                block
                loading={submitting}
                style={{ background: colors.accent, borderColor: colors.accent }}
              >
                ログイン
              </Button>
            </Form.Item>
          </Form>

          <div style={{ textAlign: 'center' }}>
            <Text style={{ color: colors.textSecondary, fontSize: 13 }}>
              アカウントをお持ちでない方は{' '}
              <Link to="/register" style={{ color: colors.accent }}>
                新規登録
              </Link>
            </Text>
          </div>
        </Space>
      </Card>
    </div>
  )
}

export default LoginPage
