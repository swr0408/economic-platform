import { useState, useEffect, useRef } from 'react'
import { Spin, Button, Modal } from 'antd'
import { ReloadOutlined, ExpandOutlined, ZoomInOutlined, ZoomOutOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'

interface FedWatchScreenshotResponse {
  image_url: string | null
  last_updated: string | null
  cached: boolean
  source: string
  response_time_ms: number
  error?: string
}

export default function CMEFedWatchChart() {
  const [data, setData] = useState<FedWatchScreenshotResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [imageTimestamp, setImageTimestamp] = useState(Date.now())

  // 拡大表示用のstate
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [zoomLevel, setZoomLevel] = useState(1)
  const imageRef = useRef<HTMLImageElement>(null)

  const loadScreenshot = async (forceRefresh = false) => {
    try {
      const url = forceRefresh
        ? '/api/fedwatch/screenshot?refresh=true'
        : '/api/fedwatch/screenshot'
      const response = await fetch(url)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const result: FedWatchScreenshotResponse = await response.json()
      setData(result)

      if (forceRefresh) {
        setImageTimestamp(Date.now())
      }

      if (result.error) {
        setError(result.error)
      } else {
        setError(null)
      }
    } catch (err) {
      console.error('Error loading FedWatch screenshot:', err)
      setError(err instanceof Error ? err.message : 'Failed to load screenshot')
    }
  }

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      await loadScreenshot()
      setLoading(false)
    }
    load()
  }, [])

  const handleRefresh = async () => {
    setRefreshing(true)
    await loadScreenshot(true)
    setRefreshing(false)
  }

  // モーダルを開く
  const openModal = () => {
    setZoomLevel(1)
    setIsModalOpen(true)
  }

  // モーダルを閉じる
  const closeModal = () => {
    setIsModalOpen(false)
    setZoomLevel(1)
  }

  // ズームイン
  const zoomIn = () => {
    setZoomLevel(prev => Math.min(prev + 0.25, 3))
  }

  // ズームアウト
  const zoomOut = () => {
    setZoomLevel(prev => Math.max(prev - 0.25, 0.5))
  }

  // ズームリセット
  const resetZoom = () => {
    setZoomLevel(1)
  }

  if (loading) {
    return (
      <div id="fedwatch-chart">
        <ChartContainer
          title="CME FEDWATCH TOOL"
          showPeriodSelector={false}
          source="CME Group"
        >
          <div style={{ textAlign: 'center', padding: '60px 0' }}>
            <Spin size="large" />
            <div style={{ marginTop: 16, color: '#666' }}>FedWatchデータを読み込み中...</div>
          </div>
        </ChartContainer>
      </div>
    )
  }

  const imageUrl = `/api/fedwatch/image?t=${imageTimestamp}`

  return (
    <div id="fedwatch-chart">
      <ChartContainer
        title="Fed Watch"
        showPeriodSelector={false}
        source="CME Group"
        extra={
          <div style={{ display: 'flex', gap: 8 }}>
            <Button
              icon={<ExpandOutlined />}
              onClick={openModal}
              size="small"
              title="拡大表示"
            >
              拡大
            </Button>
            <Button
              icon={<ReloadOutlined spin={refreshing} />}
              onClick={handleRefresh}
              loading={refreshing}
              size="small"
            >
              更新
            </Button>
          </div>
        }
      >
        {error && !data?.image_url ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>
            Error: {error}
          </div>
        ) : (
          <div style={{ position: 'relative' }}>
            {/* スクリーンショット画像（クリックで拡大） */}
            <div
              style={{
                width: '100%',
                overflow: 'auto',
                backgroundColor: '#fff',
                borderRadius: 4,
                cursor: 'zoom-in',
              }}
              onClick={openModal}
            >
              <img
                ref={imageRef}
                src={imageUrl}
                alt="CME FedWatch Tool"
                style={{
                  maxWidth: '100%',
                  height: 'auto',
                  display: 'block',
                }}
                onError={(e) => {
                  const target = e.target as HTMLImageElement
                  target.style.display = 'none'
                  setError('Screenshot image not available')
                }}
              />
            </div>

            {/* メタ情報 */}
            <div style={{
              marginTop: 12,
              fontSize: 11,
              color: '#999',
              display: 'flex',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: 8
            }}>
              {data?.last_updated && (
                <span>
                  Last updated: {new Date(data.last_updated).toLocaleString('ja-JP', { timeZone: 'Asia/Tokyo' })}
                </span>
              )}
            </div>
          </div>
        )}
      </ChartContainer>

      {/* 拡大モーダル */}
      <Modal
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingRight: 32 }}>
            <span>Fed Watch</span>
            <div style={{ display: 'flex', gap: 8 }}>
              <Button
                icon={<ZoomOutOutlined />}
                onClick={zoomOut}
                size="small"
                disabled={zoomLevel <= 0.5}
              />
              <Button
                onClick={resetZoom}
                size="small"
              >
                {Math.round(zoomLevel * 100)}%
              </Button>
              <Button
                icon={<ZoomInOutlined />}
                onClick={zoomIn}
                size="small"
                disabled={zoomLevel >= 3}
              />
            </div>
          </div>
        }
        open={isModalOpen}
        onCancel={closeModal}
        footer={null}
        width="95vw"
        style={{ top: 20 }}
        styles={{
          body: {
            maxHeight: 'calc(100vh - 150px)',
            overflow: 'auto',
            padding: 16,
            backgroundColor: '#f5f5f5',
          }
        }}
      >
        <div
          style={{
            overflow: 'auto',
            textAlign: 'center',
            backgroundColor: '#fff',
            borderRadius: 4,
            padding: 16,
          }}
        >
          <img
            src={imageUrl}
            alt="CME FedWatch Tool"
            style={{
              transform: `scale(${zoomLevel})`,
              transformOrigin: 'top left',
              maxWidth: zoomLevel === 1 ? '100%' : 'none',
              height: 'auto',
              display: 'inline-block',
              transition: 'transform 0.2s ease',
            }}
          />
        </div>

        {/* モーダル内のメタ情報 */}
        <div style={{
          marginTop: 12,
          fontSize: 12,
          color: '#666',
          display: 'flex',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 8
        }}>
          {data?.last_updated && (
            <span>
              Last updated: {new Date(data.last_updated).toLocaleString('ja-JP', { timeZone: 'Asia/Tokyo' })}
            </span>
          )}
          <span>
            Source: CME Group FedWatch Tool
          </span>
        </div>
      </Modal>
    </div>
  )
}
