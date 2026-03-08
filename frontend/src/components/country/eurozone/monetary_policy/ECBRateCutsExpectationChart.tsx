import { useState, useEffect } from 'react'
import { Card, Button, Spin, Typography, Row, Col, Image } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'

const { Text } = Typography

interface ECBRateCutsExpectationChartProps {
  title?: string
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

interface ScreenshotData {
  yearend_url: string | null
  rate_cuts_url: string | null
  last_updated: string | null
  refreshed?: boolean
}

export default function ECBRateCutsExpectationChart({
  title = 'ECB利上げ・利下げ期待（2026年）'
}: ECBRateCutsExpectationChartProps) {
  const [imageKey, setImageKey] = useState(Date.now())
  const [refreshing, setRefreshing] = useState(false)
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<ScreenshotData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadScreenshotUrls()
  }, [])

  const loadScreenshotUrls = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await fetch(`${API_BASE_URL}/api/eurozone/ecb-rate-cuts-screenshot`)
      if (!response.ok) {
        throw new Error('Failed to load screenshot URLs')
      }
      const result = await response.json()
      setData(result)
    } catch (err) {
      console.error('Failed to load screenshot URLs:', err)
      setError('スクリーンショットの読み込みに失敗しました')
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/eurozone/ecb-rate-cuts-screenshot?force_refresh=true`)
      if (!response.ok) {
        throw new Error('Failed to refresh screenshots')
      }
      const result = await response.json()
      setData(result)
      setImageKey(Date.now())
    } catch (err) {
      console.error('Failed to refresh screenshots:', err)
      setError('スクリーンショットの更新に失敗しました')
    } finally {
      setRefreshing(false)
    }
  }

  if (loading) {
    return (
      <Card title={
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', position: 'relative' }}>
          <span>{title}</span>
          <Button size="small" icon={<ReloadOutlined />} onClick={handleRefresh} loading={refreshing} style={{ position: 'absolute', right: 0 }}>
            更新
          </Button>
        </div>
      }>
        <div style={{ textAlign: 'center', padding: '60px 0' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16, color: '#666' }}>読み込み中...</div>
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card
        title={
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', position: 'relative' }}>
            <span>{title}</span>
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={handleRefresh}
              loading={refreshing}
              style={{ position: 'absolute', right: 0 }}
            >
              再取得
            </Button>
          </div>
        }
      >
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          {error}
        </div>
      </Card>
    )
  }

  return (
    <Card
      title={
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', position: 'relative' }}>
          <span>{title}</span>
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={handleRefresh}
            loading={refreshing}
            style={{ position: 'absolute', right: 0 }}
          >
            更新
          </Button>
        </div>
      }
    >
      <Row gutter={[24, 24]}>
        {/* 年末金利予想 */}
        <Col xs={24} lg={12}>
          <div style={{ textAlign: 'center' }}>
            <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 12 }}>
              年末金利予想
            </Text>
            {data?.yearend_url ? (
              <Image
                key={`yearend-${imageKey}`}
                src={`${API_BASE_URL}/api/eurozone/ecb-rate-cuts-screenshot/yearend?t=${imageKey}`}
                alt="ECB Yearend Rate Expectations"
                style={{ maxWidth: '100%', height: 'auto' }}
                preview={true}
                placeholder={
                  <div style={{ padding: '40px', background: '#f5f5f5' }}>
                    <Spin />
                  </div>
                }
              />
            ) : (
              <div style={{ padding: '60px 0', color: '#999', background: '#f5f5f5', borderRadius: 8 }}>
                スクリーンショットが利用できません
              </div>
            )}
          </div>
        </Col>

        {/* 利上げ・利下げ回数 */}
        <Col xs={24} lg={12}>
          <div style={{ textAlign: 'center' }}>
            <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 12 }}>
              利上げ・利下げ回数予想
            </Text>
            {data?.rate_cuts_url ? (
              <Image
                key={`rate_cuts-${imageKey}`}
                src={`${API_BASE_URL}/api/eurozone/ecb-rate-cuts-screenshot/rate-cuts?t=${imageKey}`}
                alt="ECB Rate Cuts Expectations"
                style={{ maxWidth: '100%', height: 'auto' }}
                preview={true}
                placeholder={
                  <div style={{ padding: '40px', background: '#f5f5f5' }}>
                    <Spin />
                  </div>
                }
              />
            ) : (
              <div style={{ padding: '60px 0', color: '#999', background: '#f5f5f5', borderRadius: 8 }}>
                スクリーンショットが利用できません
              </div>
            )}
          </div>
        </Col>
      </Row>

      <div style={{ marginTop: 16, textAlign: 'center' }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          Data Source: MacroMicro
          {data?.last_updated && (
            <span style={{ marginLeft: 16 }}>
              Last Updated: {new Date(data.last_updated).toLocaleString('ja-JP')}
            </span>
          )}
        </Text>
      </div>
    </Card>
  )
}
