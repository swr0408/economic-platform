import { useState, useEffect, useRef } from 'react'
import { Spin, Button, Modal, Select } from 'antd'
import { ExpandOutlined, ZoomInOutlined, ZoomOutOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'

const { Option } = Select

// Props型定義
interface SEPDateItem {
  date: string
  label: string
}

interface FOMCTable1ChartProps {
  sepDates: SEPDateItem[] | null
}

// 選択肢のラベル
const DATE_LABELS: Record<string, string> = {
  '0': '最新',
  '1': '前回',
  '2': '前々回',
  '3': '3回前',
}

export default function FOMCTable1Chart({ sepDates }: FOMCTable1ChartProps) {
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedIndex, setSelectedIndex] = useState<string>('0')

  // 拡大表示用のstate
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [zoomLevel, setZoomLevel] = useState(1)
  const imageRef = useRef<HTMLImageElement>(null)

  // 画像を取得
  useEffect(() => {
    if (!sepDates || sepDates.length === 0) return

    const loadImage = async () => {
      setLoading(true)
      setError(null)

      // 以前のURLオブジェクトを解放
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl)
      }

      try {
        const index = parseInt(selectedIndex, 10)
        const selectedDateInfo = sepDates[index]

        if (!selectedDateInfo) {
          throw new Error('Invalid selection')
        }

        // Table1用のAPI呼び出し
        const response = await fetch(`/api/fomc-projections/table1/${selectedDateInfo.date}`)
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }
        const blob = await response.blob()
        const url = URL.createObjectURL(blob)
        setImageUrl(url)
      } catch (err) {
        console.error('Error loading FOMC Table1:', err)

        const errorObj = err as Error
        if (errorObj.message && errorObj.message.includes('404')) {
          setError('選択された日付のFOMC経済見通しはまだ公開されていません。')
        } else if (errorObj.message) {
          setError(errorObj.message)
        } else {
          setError('FOMC経済見通しの読み込みに失敗しました')
        }
      } finally {
        setLoading(false)
      }
    }

    loadImage()

    // クリーンアップ: URLオブジェクトを解放
    return () => {
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl)
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedIndex, sepDates])

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

  // sepDatesがnullの場合はローディング表示
  if (sepDates === null) {
    return (
      <div id="fomc-table1-chart">
        <ChartContainer
          title="FOMC経済見通し"
          showPeriodSelector={false}
          source="Federal Reserve"
        >
          <div style={{ textAlign: 'center', padding: '60px 0' }}>
            <Spin size="large" />
            <div style={{ marginTop: 16, color: '#666' }}>FOMC経済見通しを読み込み中...</div>
          </div>
        </ChartContainer>
      </div>
    )
  }

  // sepDatesが空の場合
  if (sepDates.length === 0) {
    return (
      <div id="fomc-table1-chart">
        <ChartContainer
          title="FOMC経済見通し"
          showPeriodSelector={false}
          source="Federal Reserve"
        >
          <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
            SEP日付データが利用できません
          </div>
        </ChartContainer>
      </div>
    )
  }

  return (
    <div id="fomc-table1-chart">
      <ChartContainer
        title="FOMC経済見通し"
        showPeriodSelector={false}
        source="Federal Reserve"
        extra={
          <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginBottom: 16 }}>
            <Select
              value={selectedIndex}
              onChange={setSelectedIndex}
              style={{ width: 220 }}
              size="small"
              disabled={sepDates.length === 0}
            >
              {sepDates.map((item, index) => (
                <Option key={index} value={String(index)}>
                  {DATE_LABELS[String(index)] || `${index}回前`}（{item.label}）
                </Option>
              ))}
            </Select>
            <Button
              icon={<ExpandOutlined />}
              onClick={openModal}
              size="small"
              title="拡大表示"
              disabled={!imageUrl}
            >
              拡大
            </Button>
          </div>
        }
      >
        {loading ? (
          <div style={{ textAlign: 'center', padding: '60px 0' }}>
            <Spin size="large" />
            <div style={{ marginTop: 16, color: '#666' }}>FOMC経済見通しを読み込み中...</div>
          </div>
        ) : error ? (
          <div style={{
            textAlign: 'center',
            padding: '40px 0',
            color: error.includes('公開されていません') ? '#faad14' : '#ff4d4f'
          }}>
            {error}
          </div>
        ) : imageUrl ? (
          <div style={{ position: 'relative' }}>
            {/* 画像表示（クリックで拡大） */}
            <div
              style={{
                width: '100%',
                overflow: 'auto',
                backgroundColor: '#fff',
                borderRadius: 4,
                cursor: 'zoom-in',
                textAlign: 'center',
              }}
              onClick={openModal}
            >
              <img
                ref={imageRef}
                src={imageUrl}
                alt="FOMC Economic Projections - Table 1"
                style={{
                  maxWidth: '100%',
                  height: 'auto',
                  display: 'inline-block',
                  border: '1px solid #d9d9d9',
                  borderRadius: 4,
                }}
                onError={(e) => {
                  const target = e.target as HTMLImageElement
                  target.style.display = 'none'
                  setError('FOMC経済見通し画像を読み込めませんでした')
                }}
              />
            </div>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
            FOMC経済見通しが見つかりません
          </div>
        )}
      </ChartContainer>

      {/* 拡大モーダル */}
      <Modal
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingRight: 32 }}>
            <span>FOMC経済見通し</span>
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
          {imageUrl && (
            <img
              src={imageUrl}
              alt="FOMC Economic Projections - Table 1"
              style={{
                transform: `scale(${zoomLevel})`,
                transformOrigin: 'top left',
                maxWidth: zoomLevel === 1 ? '100%' : 'none',
                height: 'auto',
                display: 'inline-block',
                transition: 'transform 0.2s ease',
              }}
            />
          )}
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
          <span>
            {DATE_LABELS[selectedIndex]}（{sepDates[parseInt(selectedIndex, 10)]?.label}）
          </span>
          <span>
            Source: Federal Reserve
          </span>
        </div>
      </Modal>
    </div>
  )
}
