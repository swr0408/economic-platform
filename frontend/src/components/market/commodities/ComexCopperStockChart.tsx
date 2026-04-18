import { useEffect, useState } from 'react'
import { Button, Image, Spin } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { fetchWithTimeout } from '../../../utils/apiConfig'
import { useIsMaster } from '../../../hooks/useIsMaster'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

const DARK_THEME = {
  cardBg: '#1e293b',
  border: '#334155',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  link: '#60a5fa',
}

const MACROMICRO_URL = 'https://www.macromicro.me/series/8742/copper-comex-warehouse-stock'

interface ScreenshotResponse {
  copper_url: string | null
  last_updated: string | null
  refreshed?: boolean
}

export default function ComexCopperStockChart() {
  const isMaster = useIsMaster()
  const [data, setData] = useState<ScreenshotResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [imageKey, setImageKey] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const load = async (force = false) => {
    try {
      setError(null)
      if (force) setRefreshing(true)
      else setLoading(true)
      const url = `${API_BASE_URL}/api/market/comex-warehouse-screenshot${force ? '?force_refresh=true' : ''}`
      const res = await fetchWithTimeout(url, undefined, force ? 120_000 : 30_000)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json: ScreenshotResponse = await res.json()
      setData(json)
      if (force) setImageKey(Date.now())
    } catch (e) {
      console.error('COMEX copper screenshot load failed:', e)
      setError('スクリーンショットの取得に失敗しました')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    load(false)
  }, [])

  return (
    <div
      id="comex-copper-stock"
      style={{
        background: DARK_THEME.cardBg,
        border: `1px solid ${DARK_THEME.border}`,
        borderRadius: 8,
        padding: 16,
        marginBottom: 16,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          position: 'relative',
          marginBottom: 12,
        }}
      >
        <span style={{ color: DARK_THEME.textPrimary, fontSize: 16, fontWeight: 600 }}>
          COMEX Copper Warehouse Stock
        </span>
        {isMaster && (
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={() => load(true)}
            loading={refreshing}
            style={{ position: 'absolute', right: 0 }}
          >
            更新
          </Button>
        )}
      </div>

      <div style={{ textAlign: 'center', minHeight: 360 }}>
        {loading ? (
          <div style={{ padding: '80px 0' }}>
            <Spin size="large" />
          </div>
        ) : error && !data?.copper_url ? (
          <div style={{ padding: '80px 0', color: DARK_THEME.textSecondary }}>{error}</div>
        ) : data?.copper_url ? (
          <Image
            key={`comex-copper-${imageKey}`}
            src={`${API_BASE_URL}/api/market/comex-warehouse-screenshot/copper?t=${imageKey}`}
            alt="COMEX Copper Warehouse Stock"
            style={{ maxWidth: '100%', height: 'auto' }}
            preview={true}
            placeholder={
              <div style={{ padding: '40px', background: DARK_THEME.cardBg }}>
                <Spin />
              </div>
            }
          />
        ) : (
          <div style={{ padding: '80px 0', color: DARK_THEME.textSecondary }}>
            スクリーンショットが利用できません
          </div>
        )}
      </div>

      <div style={{ marginTop: 12, fontSize: 12, color: DARK_THEME.textSecondary }}>
        Data source:{' '}
        <a
          href={MACROMICRO_URL}
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: DARK_THEME.link }}
        >
          MacroMicro
        </a>
        {data?.last_updated && (
          <span style={{ marginLeft: 16 }}>
            Last Updated: {new Date(data.last_updated).toLocaleString('ja-JP')}
          </span>
        )}
      </div>
    </div>
  )
}
