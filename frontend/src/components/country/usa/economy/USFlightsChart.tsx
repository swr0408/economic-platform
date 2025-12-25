import { useState } from 'react'
import { Button, Modal } from 'antd'
import { ExpandOutlined, ZoomInOutlined, ZoomOutOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import type { USFlightsData } from '../../../../hooks/useDashboardData'

interface USFlightsChartProps {
  data: USFlightsData | null
}

export default function USFlightsChart({ data }: USFlightsChartProps) {
  // モーダル用のstate
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [zoomLevel, setZoomLevel] = useState(1)

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
  if (data === null) {
    return <LoadingChart title="米国航空機便数（US Flights）" />
  }

  // 画像URLがない場合
  if (!data.image_url) {
    return (
      <ChartContainer title="米国航空機便数（US Flights）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  return (
    <div id="us-flights-chart">
      <ChartContainer
        title="米国航空機便数"
        showPeriodSelector={false}
        dataSource="Airportia"
        sourceUrl="https://www.airportia.com/flights-monitor/?country=US"

      >
        {/* ヘッダー情報 */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 12,
            padding: '12px 16px',
            background: '#f5f5f5',
            borderRadius: 8,
          }}
        >
          <div>
            <span style={{ fontSize: 12, color: '#666' }}>データ日付: </span>
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
        </div>

        <Button
          icon={<ExpandOutlined />}
          onClick={openModal}
          size="small"
          title="拡大表示"
        >
          拡大
        </Button>
        
        {/* スクリーンショット画像（クリックで拡大） */}
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
            src={data.image_url}
            alt="US Flights Monitor Chart"
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

        {/* 説明文 */}
        <div
          style={{
            fontSize: 11,
            color: '#888',
            textAlign: 'center',
            marginTop: 8,
          }}
        >
          フライト数の推移（過去1年間・前年比較）
        </div>
      </ChartContainer>

      {/* 拡大モーダル */}
      <Modal
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingRight: 32 }}>
            <span>米国航空機便数</span>
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
            src={data.image_url}
            alt="US Flights Monitor Chart"
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
            {data.latest && <span>データ日付: {data.latest.description}</span>}
          </div>
          <div>
            Source: Airportia Flight Monitor
          </div>
        </div>
      </Modal>
    </div>
  )
}
