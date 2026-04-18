/**
 * レストラン予約件数前年比（OpenTable）チャートコンポーネント
 *
 * 手動配置された複数画像をタブで切り替え表示
 * - 週次チャート (Weekly)
 * - 月次テーブル (Monthly)
 */
import { useState } from 'react'
import { Tabs, Button, Modal } from 'antd'
import { ExpandOutlined, ZoomInOutlined, ZoomOutOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import type { OpenTableData, OpenTableImage } from '../../../../hooks/useDashboardData'
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../common/chartConstants'
import { apiUrl } from '../../../../utils/apiConfig'

interface OpenTableChartProps {
  data: OpenTableData | null
}

export default function OpenTableChart({ data }: OpenTableChartProps) {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [zoomLevel, setZoomLevel] = useState(1)
  const [activeTab, setActiveTab] = useState('0')

  const openModal = () => { setZoomLevel(1); setIsModalOpen(true) }
  const closeModal = () => { setIsModalOpen(false); setZoomLevel(1) }
  const zoomIn = () => setZoomLevel(prev => Math.min(prev + 0.25, 3))
  const zoomOut = () => setZoomLevel(prev => Math.max(prev - 0.25, 0.5))
  const resetZoom = () => setZoomLevel(1)

  if (data === null) {
    return <LoadingChart title="レストラン予約件数前年比（OpenTable）" />
  }

  // images 配列があればタブ切替モード、なければ後方互換
  const images: OpenTableImage[] = data.images && data.images.length > 0
    ? data.images
    : data.image_url
      ? [{ label: 'Chart', url: data.image_url }]
      : []

  if (images.length === 0) {
    return (
      <ChartContainer title="レストラン予約件数前年比（OpenTable）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  const currentImage = images[parseInt(activeTab)] || images[0]

  const tabItems = images.map((img, idx) => ({
    key: String(idx),
    label: img.label,
    children: (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          padding: '16px 0',
          cursor: 'zoom-in',
        }}
        onClick={openModal}
      >
        <img
          src={apiUrl(img.url)}
          alt={`OpenTable ${img.label}`}
          style={{
            maxWidth: '100%',
            height: 'auto',
            borderRadius: 8,
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
          }}
          onError={(e) => {
            const target = e.target as HTMLImageElement
            target.style.display = 'none'
            const parent = target.parentElement
            if (parent) {
              parent.innerHTML = '<div style="text-align: center; padding: 40px 0; color: #999;">画像の読み込みに失敗しました</div>'
            }
          }}
        />
      </div>
    ),
  }))

  return (
    <div id="opentable-chart">
      <ChartContainer
        title="レストラン予約件数前年比"
        showPeriodSelector={false}
        dataSource="OpenTable"
        sourceUrl="https://www.opentable.com/c/state-of-industry/"
        handbookId="bank-lending"
      >
        {/* ヘッダー情報 */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>データ: </span>
            {data.latest && (
              <span
                style={{
                  fontSize: 16,
                  fontWeight: 'bold',
                  color: '#1890ff',
                }}
              >
                {data.latest.description}
              </span>
            )}
          </div>
          <Button
            icon={<ExpandOutlined />}
            onClick={openModal}
            size="small"
            title="拡大表示"
          >
            拡大
          </Button>
        </div>

        {/* タブ切替 or 単一画像 */}
        {images.length > 1 ? (
          <Tabs
            activeKey={activeTab}
            onChange={(key) => { setActiveTab(key); setZoomLevel(1) }}
            items={tabItems}
            size="small"
            style={{ marginTop: 8 }}
          />
        ) : (
          tabItems[0]?.children
        )}

        {/* 説明文 */}
        <div
          style={{
            fontSize: 11,
            color: '#888',
            textAlign: 'center',
            marginTop: 8,
          }}
        >
          米国レストラン予約件数の前年比推移
        </div>
      </ChartContainer>

      {/* 拡大モーダル */}
      <Modal
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingRight: 32 }}>
            <span>レストラン予約件数前年比</span>
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
            src={apiUrl(currentImage.url)}
            alt={`OpenTable ${currentImage.label}`}
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
        }}>
          <div>
            {data.latest && <span>{currentImage.label} — {data.latest.description}</span>}
          </div>
          <div>
            Source: OpenTable State of Industry
          </div>
        </div>
      </Modal>
    </div>
  )
}
