import { useState, useRef } from 'react'
import { Spin, Button, Modal } from 'antd'
import { ReloadOutlined, ExpandOutlined, ZoomInOutlined, ZoomOutOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'

// Props型定義
interface CMEFedWatchChartProps {
  screenshotUrl: string | null
  lastUpdated?: string | null
  cached?: boolean
}

export default function CMEFedWatchChart({ screenshotUrl, lastUpdated, cached }: CMEFedWatchChartProps) {
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [imageTimestamp, setImageTimestamp] = useState(Date.now())
  // ローカルで管理する更新時刻（更新ボタン押下時に更新）
  const [localLastUpdated, setLocalLastUpdated] = useState<string | null>(null)
  const [localCached, setLocalCached] = useState<boolean | undefined>(cached)

  // 拡大表示用のstate
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [zoomLevel, setZoomLevel] = useState(1)
  const imageRef = useRef<HTMLImageElement>(null)

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      // スクリーンショットを強制更新
      await fetch('/api/fedwatch/screenshot?refresh=true')
      setImageTimestamp(Date.now())
      setLocalLastUpdated(new Date().toISOString())
      setLocalCached(false)
      setError(null)
    } catch (err) {
      console.error('Error refreshing FedWatch screenshot:', err)
      setError(err instanceof Error ? err.message : 'Failed to refresh')
    } finally {
      setRefreshing(false)
    }
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

  // データがnullの場合はローディング表示
  if (screenshotUrl === null) {
    return (
      <div id="fedwatch-chart">
        <ChartContainer
          title="Fed Watch"
          showPeriodSelector={false}
          source="CME Group"
          sourceUrl="https://www.cmegroup.com/ja/markets/interest-rates/cme-fedwatch-tool.html"
        >
          <div style={{ textAlign: 'center', padding: '60px 0' }}>
            <Spin size="large" />
            <div style={{ marginTop: 16, color: '#666' }}>FedWatchデータを読み込み中...</div>
          </div>
        </ChartContainer>
      </div>
    )
  }

  // 画像URLにタイムスタンプを付与（キャッシュ回避用）
  const imageUrl = `${screenshotUrl}?t=${imageTimestamp}`

  return (
    <div id="fedwatch-chart">
      <ChartContainer
        title="Fed Watch"
        showPeriodSelector={false}
        source="CME Group"
        sourceUrl="https://www.cmegroup.com/ja/markets/interest-rates/cme-fedwatch-tool.html"
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
        {error ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>
            Error: {error}
          </div>
        ) : (
          <div style={{ position: 'relative' }}>
            {/* 最終更新時刻 */}
            {(localLastUpdated || lastUpdated) && (
              <div
                style={{
                  marginBottom: 12,
                  fontSize: 12,
                  color: '#666',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                }}
              >
                <span>
                  最終更新: {new Date(localLastUpdated || lastUpdated!).toLocaleString('ja-JP')}
                </span>
                {(localLastUpdated ? localCached : cached) && (
                  <span style={{ color: '#52c41a' }}>(キャッシュ)</span>
                )}
              </div>
            )}
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
          textAlign: 'right',
        }}>
          Source: CME Group FedWatch Tool
        </div>
      </Modal>
    </div>
  )
}
