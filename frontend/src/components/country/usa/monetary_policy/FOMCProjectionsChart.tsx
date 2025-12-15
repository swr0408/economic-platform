import { useState, useEffect, useRef } from 'react'
import { Spin, Select, Button, Modal } from 'antd'
import { ExpandOutlined, ZoomInOutlined, ZoomOutOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import { fetchFOMCProjectionsFigure2, fetchFOMCSEPDates, type FOMCSEPDate } from '../../../../utils/usa/monetary_policyApi'

const { Option } = Select

// 選択肢のラベル
const DATE_LABELS: Record<string, string> = {
  '0': '最新',
  '1': '前回',
  '2': '前々回',
  '3': '3回前',
}

export default function FOMCProjectionsChart() {
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedIndex, setSelectedIndex] = useState<string>('0') // 0=最新, 1=前回, 2=前々回, 3=3回前
  const [sepDates, setSepDates] = useState<FOMCSEPDate[]>([])

  // 拡大表示用のstate
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [zoomLevel, setZoomLevel] = useState(1)
  const imageRef = useRef<HTMLImageElement>(null)

  // SEP日付を取得
  useEffect(() => {
    const loadSepDates = async () => {
      try {
        const dates = await fetchFOMCSEPDates(4)
        setSepDates(dates)
      } catch (err) {
        console.error('Error loading SEP dates:', err)
        // フォールバック用の日付（APIが失敗した場合）
        setSepDates([
          { date: '20251218', label: '2025年12月18日' },
          { date: '20250918', label: '2025年9月18日' },
          { date: '20250618', label: '2025年6月18日' },
          { date: '20250319', label: '2025年3月19日' },
        ])
      }
    }
    loadSepDates()
  }, [])

  // 画像を取得
  useEffect(() => {
    if (sepDates.length === 0) return

    const loadImage = async () => {
      setLoading(true)
      setError(null)

      // 以前のURLオブジェクトを解放
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl)
      }

      try {
        // 選択されたインデックスに対応する日付を取得
        const index = parseInt(selectedIndex, 10)
        const selectedDateInfo = sepDates[index]

        if (!selectedDateInfo) {
          throw new Error('Invalid selection')
        }

        const url = await fetchFOMCProjectionsFigure2(selectedDateInfo.date)
        setImageUrl(url)
      } catch (err) {
        console.error('Error loading FOMC Projections:', err)

        // エラーメッセージを解析
        const error = err as Error
        if (error.message && error.message.includes('404')) {
          setError('選択された日付のドットプロットはまだ公開されていません。')
        } else if (error.message) {
          setError(error.message)
        } else {
          setError('ドットプロットの読み込みに失敗しました')
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

  if (loading) {
    return (
      <div id="fomc-projections-chart">
        <ChartContainer
          title="Dot Plot"
          showPeriodSelector={false}
          source="Federal Reserve"
        >
          <div style={{ textAlign: 'center', padding: '60px 0' }}>
            <Spin size="large" />
            <div style={{ marginTop: 16, color: '#666' }}>ドットプロットを読み込み中...</div>
          </div>
        </ChartContainer>
      </div>
    )
  }

  return (
    <div id="fomc-projections-chart">
      <ChartContainer
        title="Dot Plot"
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
        {error ? (
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
                alt="FOMC Economic Projections - Figure 2"
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
                  setError('ドットプロット画像を読み込めませんでした')
                }}
              />
            </div>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
            ドットプロットが見つかりません
          </div>
        )}
      </ChartContainer>

      {/* 拡大モーダル */}
      <Modal
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingRight: 32 }}>
            <span>Dot Plot</span>
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
              alt="FOMC Economic Projections - Figure 2"
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
