/**
 * レストラン予約件数前年比（OpenTable）チャートコンポーネント
 *
 * 手動配置された複数画像をタブで切り替え表示
 * - 週次チャート (Weekly)
 * - 月次テーブル (Monthly)
 */
import { useState } from 'react'
import { Tabs, Button, Modal, Upload, message, Space } from 'antd'
import type { UploadFile } from 'antd'
import { ExpandOutlined, ZoomInOutlined, ZoomOutOutlined, UploadOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import type { OpenTableData, OpenTableImage } from '../../../../hooks/useDashboardData'
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../common/chartConstants'
import { apiUrl } from '../../../../utils/apiConfig'
import { useAuth } from '../../../../contexts/AuthContext'

interface OpenTableChartProps {
  data: OpenTableData | null
}

export default function OpenTableChart({ data }: OpenTableChartProps) {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [zoomLevel, setZoomLevel] = useState(1)
  const [activeTab, setActiveTab] = useState('0')

  // 管理者(master)向け: スクショ手動アップロード
  const { hasRole } = useAuth()
  const isMaster = hasRole('master')
  const [uploadOpen, setUploadOpen] = useState(false)
  const [weekFile, setWeekFile] = useState<UploadFile | null>(null)
  const [monthFile, setMonthFile] = useState<UploadFile | null>(null)
  const [uploading, setUploading] = useState(false)
  // アップロード後に画像URLをキャッシュバスターで即時更新するためのトークン
  const [cacheBust, setCacheBust] = useState(0)

  const openModal = () => { setZoomLevel(1); setIsModalOpen(true) }
  const closeModal = () => { setIsModalOpen(false); setZoomLevel(1) }
  const zoomIn = () => setZoomLevel(prev => Math.min(prev + 0.25, 3))
  const zoomOut = () => setZoomLevel(prev => Math.max(prev - 0.25, 0.5))
  const resetZoom = () => setZoomLevel(1)

  const bustUrl = (url: string) => {
    const full = apiUrl(url)
    if (!cacheBust) return full
    return `${full}${full.includes('?') ? '&' : '?'}v=${cacheBust}`
  }

  const handleUpload = async () => {
    if (!weekFile && !monthFile) {
      message.warning('週次または月次の画像を選択してください')
      return
    }
    const form = new FormData()
    if (weekFile) form.append('week', weekFile as unknown as Blob)
    if (monthFile) form.append('month', monthFile as unknown as Blob)

    setUploading(true)
    try {
      const res = await fetch(apiUrl('/api/usa/opentable/upload'), {
        method: 'POST',
        body: form,
      })
      if (!res.ok) {
        const text = await res.text().catch(() => '')
        throw new Error(`${res.status} ${text}`.trim())
      }
      message.success('OpenTableのスクショを更新しました')
      setUploadOpen(false)
      setWeekFile(null)
      setMonthFile(null)
      setCacheBust(Date.now())
    } catch (e) {
      message.error(`アップロードに失敗しました: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setUploading(false)
    }
  }

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
          src={bustUrl(img.url)}
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
          <Space size={8}>
            {isMaster && (
              <Button
                icon={<UploadOutlined />}
                onClick={() => setUploadOpen(true)}
                size="small"
                title="スクショを差し替えて更新（管理者）"
              >
                更新
              </Button>
            )}
            <Button
              icon={<ExpandOutlined />}
              onClick={openModal}
              size="small"
              title="拡大表示"
            >
              拡大
            </Button>
          </Space>
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
            src={bustUrl(currentImage.url)}
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

      {/* 管理者用: スクショ差し替えアップロード */}
      {isMaster && (
        <Modal
          title="OpenTableスクショを更新"
          open={uploadOpen}
          onCancel={() => setUploadOpen(false)}
          onOk={handleUpload}
          okText="アップロード"
          cancelText="キャンセル"
          confirmLoading={uploading}
          width={520}
        >
          <div style={{ fontSize: 12, color: '#666', marginBottom: 12, lineHeight: 1.6 }}>
            OpenTableの{' '}
            <a href="https://www.opentable.com/state-of-industry" target="_blank" rel="noopener noreferrer">
              State of the Industry
            </a>
            {' '}ページ（Global選択）から、週次チャート／月次テーブルのスクショを取得して差し替えます。
            片方だけの更新も可能です。
            <br />
            ※ このサイトはボット遮断のため自動取得できません。手動で画像を貼り付けてください。
          </div>

          <div style={{ marginBottom: 16 }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>週次チャート (Weekly)</div>
            <Upload
              maxCount={1}
              accept="image/png,image/jpeg,image/webp"
              beforeUpload={(file) => { setWeekFile(file); return false }}
              onRemove={() => setWeekFile(null)}
              fileList={weekFile ? [weekFile] : []}
            >
              <Button icon={<UploadOutlined />} size="small">週次画像を選択</Button>
            </Upload>
          </div>

          <div>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>月次テーブル (Monthly)</div>
            <Upload
              maxCount={1}
              accept="image/png,image/jpeg,image/webp"
              beforeUpload={(file) => { setMonthFile(file); return false }}
              onRemove={() => setMonthFile(null)}
              fileList={monthFile ? [monthFile] : []}
            >
              <Button icon={<UploadOutlined />} size="small">月次画像を選択</Button>
            </Upload>
          </div>
        </Modal>
      )}
    </div>
  )
}
