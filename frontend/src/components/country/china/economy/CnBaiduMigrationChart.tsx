/**
 * 中国 人流総量（百度迁徙 Baidu Migration）チャートコンポーネント
 *
 * 百度地图慧眼のスクリーンショットを表示
 * データソース: 百度地图慧眼 (https://qianxi.baidu.com/)
 *
 * FMPマッピング: なし（マーケットインパクトタブなし）
 */

import { useState, useEffect } from 'react'
import { Card, Button, Spin, Typography, Image } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'

const { Text } = Typography

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

interface ScreenshotData {
  screenshot_url: string | null
  last_updated: string | null
  refreshed?: boolean
}

export default function CnBaiduMigrationChart() {
  const [imageKey, setImageKey] = useState(Date.now())
  const [refreshing, setRefreshing] = useState(false)
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<ScreenshotData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadScreenshotUrl()
  }, [])

  const loadScreenshotUrl = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await fetch(`${API_BASE_URL}/api/china/baidu-migration-screenshot`)
      if (!response.ok) {
        throw new Error('Failed to load screenshot URL')
      }
      const result = await response.json()
      setData(result)
    } catch (err) {
      console.error('Failed to load screenshot URL:', err)
      setError('スクリーンショットの読み込みに失敗しました')
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/china/baidu-migration-screenshot?force_refresh=true`)
      if (!response.ok) {
        throw new Error('Failed to refresh screenshot')
      }
      const result = await response.json()
      setData(result)
      setImageKey(Date.now())
    } catch (err) {
      console.error('Failed to refresh screenshot:', err)
      setError('スクリーンショットの更新に失敗しました')
    } finally {
      setRefreshing(false)
    }
  }

  if (loading) {
    return (
      <Card title="人流総量">
        <div style={{ textAlign: 'center', padding: '60px 0' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16, color: '#666' }}>読み込み中...</div>
        </div>
      </Card>
    )
  }

  if (error && !data) {
    return (
      <Card
        title={
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', position: 'relative' }}>
            <span>人流総量</span>
            <Button size="small" icon={<ReloadOutlined />} onClick={handleRefresh} loading={refreshing} style={{ position: 'absolute', right: 0 }}>
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
    <div id="total-number-of-people">
      <Card
        title={
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', position: 'relative' }}>
            <span>人流総量</span>
            <Button size="small" icon={<ReloadOutlined />} onClick={handleRefresh} loading={refreshing} style={{ position: 'absolute', right: 0 }}>
              更新
            </Button>
          </div>
        }
      >
        {/* スクリーンショット表示 */}
        <div style={{ textAlign: 'center' }}>
          {data?.screenshot_url ? (
            <Image
              key={`baidu-migration-${imageKey}`}
              src={`${API_BASE_URL}/api/china/baidu-migration-screenshot/image?t=${imageKey}`}
              alt="China Baidu Migration - Total Number of People"
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

        {/* ソース情報 */}
        <div style={{ marginTop: 16, textAlign: 'center' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Data Source:{' '}
            <a
              href="https://qianxi.baidu.com/#/"
              target="_blank"
              rel="noopener noreferrer"
            >
              百度地图慧眼
            </a>
            {data?.last_updated && (
              <span style={{ marginLeft: 16 }}>
                Last Updated: {new Date(data.last_updated).toLocaleString('ja-JP')}
              </span>
            )}
          </Text>
        </div>
      </Card>
    </div>
  )
}
