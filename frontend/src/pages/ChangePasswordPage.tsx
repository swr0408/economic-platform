/**
 * パスワード変更画面 (認証済みユーザー向け)
 *
 * - 現パスワードを照合してから新パスワードに差し替える
 * - 成功時はサーバー側で発行済みトークン全てが強制失効するので、
 *   クライアント状態もクリアして /login へ誘導する
 */
import { useState } from 'react'
import { Alert, Button, Card, Form, Input, Space, Typography } from 'antd'
import { LockOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const { Title, Text } = Typography

const colors = {
  bgSecondary: '#1e293b',
  accent: '#10b981',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  border: '#334155',
}

interface FormValues {
  current_password: string
  new_password: string
  new_password_confirm: string
}

export default function ChangePasswordPage() {
  const navigate = useNavigate()
  const { changePassword } = useAuth()
  const [submitting, setSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const handleSubmit = async (values: FormValues) => {
    setErrorMsg(null)
    setSuccessMsg(null)
    if (values.new_password !== values.new_password_confirm) {
      setErrorMsg('新しいパスワードが一致しません')
      return
    }
    setSubmitting(true)
    try {
      await changePassword(values.current_password, values.new_password)
      setSuccessMsg('パスワードを変更しました。再度ログインしてください。')
      setTimeout(() => {
        navigate('/login', { replace: true })
      }, 1200)
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'パスワード変更に失敗しました')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: 24 }}>
      <Card
        style={{
          width: '100%',
          maxWidth: 480,
          background: colors.bgSecondary,
          border: `1px solid ${colors.border}`,
        }}
        styles={{ body: { padding: 32 } }}
      >
        <Space direction="vertical" size={24} style={{ width: '100%' }}>
          <div>
            <Title level={4} style={{ color: colors.textPrimary, marginBottom: 4 }}>
              パスワード変更
            </Title>
            <Text style={{ color: colors.textSecondary, fontSize: 13 }}>
              変更後は再度ログインが必要です
            </Text>
          </div>

          {errorMsg && (
            <Alert message={errorMsg} type="error" showIcon closable onClose={() => setErrorMsg(null)} />
          )}
          {successMsg && <Alert message={successMsg} type="success" showIcon />}

          <Form layout="vertical" onFinish={handleSubmit} requiredMark={false}>
            <Form.Item
              label={<span style={{ color: colors.textSecondary }}>現在のパスワード</span>}
              name="current_password"
              rules={[{ required: true, message: '現在のパスワードを入力してください' }]}
            >
              <Input.Password prefix={<LockOutlined />} size="large" autoComplete="current-password" />
            </Form.Item>

            <Form.Item
              label={<span style={{ color: colors.textSecondary }}>新しいパスワード</span>}
              name="new_password"
              rules={[
                { required: true, message: '新しいパスワードを入力してください' },
                { min: 8, max: 128, message: '8文字以上で入力してください' },
              ]}
            >
              <Input.Password prefix={<LockOutlined />} size="large" autoComplete="new-password" />
            </Form.Item>

            <Form.Item
              label={<span style={{ color: colors.textSecondary }}>新しいパスワード（確認）</span>}
              name="new_password_confirm"
              dependencies={['new_password']}
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
                変更する
              </Button>
            </Form.Item>
          </Form>
        </Space>
      </Card>
    </div>
  )
}
