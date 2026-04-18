import { useState, useEffect } from 'react'
import { Card, Button, Spin, Typography, Image } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { useIsMaster } from '../../../hooks/useIsMaster'
import { fetchWithTimeout } from '../../../utils/apiConfig'

const { Text } = Typography

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

interface ScreenshotResp {
  gold_url: string | null
  silver_url: string | null
  copper_url?: string | null
  last_updated: string | null
  refreshed?: boolean
}

export default function ComexGoldStockChart() {
  const isMaster = useIsMaster()
  const [imageKey, setImageKey] = useState(0)
  const [refreshing, setRefreshing] = useState(false)
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<ScreenshotResp | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    load()
  }, [])

  const load = async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await fetchWithTimeout(
        `${API_BASE_URL}/api/market/comex-warehouse-screenshot`,
        undefined,
        30_000,
      )
      if (!res.ok) throw new Error('Failed to load screenshot URL')
      setData(await res.json())
    } catch (e) {
      console.error(e)
      setError('スクリーンショットの読み込みに失敗しました')
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      const res = await fetchWithTimeout(
        `${API_BASE_URL}/api/market/comex-warehouse-screenshot?force_refresh=true`,
        undefined,
        120_000,
      )
      if (!res.ok) throw new Error('Failed to refresh')
      setData(await res.json())
      setImageKey(Date.now())
    } catch (e) {
      console.error(e)
      setError('スクリーンショットの更新に失敗しました')
    } finally {
      setRefreshing(false)
    }
  }

  const titleBar = (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span>COMEX金在庫</span>
      {isMaster && (
        <Button size="small" icon={<ReloadOutlined />} onClick={handleRefresh} loading={refreshing}>
          更新
        </Button>
      )}
    </div>
  )

  if (loading) {
    return (
      <Card title={titleBar}>
        <div style={{ textAlign: 'center', padding: '60px 0' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16, color: '#666' }}>読み込み中...</div>
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card title={titleBar}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>{error}</div>
      </Card>
    )
  }

  return (
    <Card title={titleBar}>
      <div style={{ textAlign: 'center' }}>
        {data?.gold_url ? (
          <Image
            key={`gold-${imageKey}`}
            src={`${API_BASE_URL}/api/market/comex-warehouse-screenshot/gold?t=${imageKey}`}
            alt="COMEX Gold Warehouse Stock"
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
