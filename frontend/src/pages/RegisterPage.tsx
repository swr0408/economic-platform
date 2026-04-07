/**
 * 新規登録画面
 *
 * backend 側で role は常に 'general' に強制される。
 * master / special への昇格は DB 直接または master 専用 API から行う想定。
 */
import { useState } from 'react'
import { Button, Card, Form, Input, Typography, Alert, Space } from 'antd'
import { UserOutlined, LockOutlined, MailOutlined } from '@ant-design/icons'
import { Link, useNavigate } from 'react-router-dom'
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

interface FormValues {
  username: string
  password: string
  password_confirm: string
  email?: string
}

function RegisterPage() {
  const navigate = useNavigate()
  const { register } = useAuth()
  const [submitting, setSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const handleSubmit = async (values: FormValues) => {
    setErrorMsg(null)
    if (values.password !== values.password_confirm) {
      setErrorMsg('パスワードが一致しません')
      return
    }
    setSubmitting(true)
    try {
      await register(values.username, values.password, values.email)
      navigate('/', { replace: true })
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : '登録に失敗しました')
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
            <Text style={{ color: colors.textSecondary, fontSize: 13 }}>新規登録</Text>
          </div>

          {errorMsg && (
            <Alert message={errorMsg} type="error" showIcon closable onClose={() => setErrorMsg(null)} />
          )}

          <Form layout="vertical" onFinish={handleSubmit} requiredMark={false}>
            <Form.Item
              label={<span style={{ color: colors.textSecondary }}>ユーザー名</span>}
              name="username"
              rules={[
                { required: true, message: 'ユーザー名を入力してください' },
                { min: 3, max: 64, message: '3〜64文字で入力してください' },
                {
                  pattern: /^[A-Za-z0-9_-]+$/,
                  message: '英数・ハイフン・アンダースコアのみ使用できます',
                },
              ]}
            >
              <Input prefix={<UserOutlined />} size="large" autoComplete="username" />
            </Form.Item>

            <Form.Item
              label={<span style={{ color: colors.textSecondary }}>メールアドレス（任意）</span>}
              name="email"
              rules={[{ type: 'email', message: '有効なメールアドレスを入力してください' }]}
            >
              <Input prefix={<MailOutlined />} size="large" autoComplete="email" />
            </Form.Item>

            <Form.Item
              label={<span style={{ color: colors.textSecondary }}>パスワード</span>}
              name="password"
              rules={[
                { required: true, message: 'パスワードを入力してください' },
                { min: 8, max: 128, message: '8文字以上で入力してください' },
              ]}
            >
              <Input.Password prefix={<LockOutlined />} size="large" autoComplete="new-password" />
            </Form.Item>

            <Form.Item
              label={<span style={{ color: colors.textSecondary }}>パスワード（確認）</span>}
              name="password_confirm"
              dependencies={['password']}
              rules={[{ required: true, message: 'もう一度入力してください' }]}
            >
              <Input.Password prefix={<LockOutlined />} size="large" autoComplete="new-password" />
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
                登録する
              </Button>
            </Form.Item>
          </Form>

          <div style={{ textAlign: 'center' }}>
            <Text style={{ color: colors.textSecondary, fontSize: 13 }}>
              既にアカウントをお持ちの方は{' '}
              <Link to="/login" style={{ color: colors.accent }}>
                ログイン
              </Link>
            </Text>
          </div>
        </Space>
      </Card>
    </div>
  )
}

export default RegisterPage
