/**
 * 中国 李克強指数（Li Keqiang Index）チャートコンポーネント
 *
 * MacroMicroのスクリーンショットを表示
 * データソース: MacroMicro (Li Keqiang Index - Citi/Wind定義)
 *
 * FMPマッピング: なし（マーケットインパクトタブなし）
 */

import { useState, useEffect } from 'react'
import { Card, Button, Spin, Typography, Image } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { useIsMaster } from '../../../../hooks/useIsMaster'
import { withVisibility } from '../../../common/withVisibility'

const { Text } = Typography

import { fetchWithTimeout } from '../../../../utils/apiConfig'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

interface ScreenshotData {
  screenshot_url: string | null
  last_updated: string | null
  refreshed?: boolean
}

function CnLiKeqiangIndexChart() {
  const isMaster = useIsMaster()
  const [imageKey, setImageKey] = useState(0)
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
      const response = await fetchWithTimeout(`${API_BASE_URL}/api/china/li-keqiang-index-screenshot`, undefined, 30_000)
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
      const response = await fetchWithTimeout(`${API_BASE_URL}/api/china/li-keqiang-index-screenshot?force_refresh=true`, undefined, 90_000)
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
      <Card title="李克強指数">
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
            <span>李克強指数</span>
            {isMaster && (
              <Button size="small" icon={<ReloadOutlined />} onClick={handleRefresh} loading={refreshing} style={{ position: 'absolute', right: 0 }}>
                再取得
              </Button>
            )}
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
    <div id="li-keqiang-index">
      <Card
        title={
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', position: 'relative' }}>
            <span>李克強指数</span>
            {isMaster && (
              <Button size="small" icon={<ReloadOutlined />} onClick={handleRefresh} loading={refreshing} style={{ position: 'absolute', right: 0 }}>
                更新
              </Button>
            )}
          </div>
        }
      >
        {/* スクリーンショット表示 */}
        <div style={{ textAlign: 'center' }}>
          {data?.screenshot_url ? (
            <Image
              key={`li-keqiang-${imageKey}`}
              src={`${API_BASE_URL}/api/china/li-keqiang-index-screenshot/image?t=${imageKey}`}
              alt="China Li Keqiang Index"
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
              href="https://en.macromicro.me/series/28284/china-keqiang-index-new"
              target="_blank"
              rel="noopener noreferrer"
            >
              MacroMicro
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

// special 限定 (一般ユーザには非表示)
export default withVisibility(CnLiKeqiangIndexChart, 'special')
