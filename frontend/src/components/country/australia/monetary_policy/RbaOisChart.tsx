/**
 * RBA OIS スクリーンショットチャートコンポーネント
 *
 * MacroMicroからキャプチャした OIS 1M / 3M / 6M の3枚を
 * 左右ボタンで切り替えて表示
 *
 * データソース:
 * - MacroMicro (https://en.macromicro.me/charts/14092/australia-overnight-indexed-swaps-spread)
 */
import { useState, useEffect } from 'react'
import { Card, Button, Spin, Typography, Image } from 'antd'
import { ReloadOutlined, LeftOutlined, RightOutlined } from '@ant-design/icons'
import { useIsMaster } from '../../../../hooks/useIsMaster'
import { withVisibility } from '../../../common/withVisibility'

const { Text } = Typography

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

interface ScreenshotItem {
  key: string
  label: string
  url: string | null
  exists: boolean
}

interface ScreenshotData {
  screenshots: ScreenshotItem[]
  last_updated: string | null
  refreshed?: boolean
}

function RbaOisChart() {
  const isMaster = useIsMaster()
  const [imageKey, setImageKey] = useState(Date.now())
  const [refreshing, setRefreshing] = useState(false)
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<ScreenshotData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [currentIndex, setCurrentIndex] = useState(0)

  useEffect(() => {
    loadScreenshotUrls()
  }, [])

  const loadScreenshotUrls = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await fetch(`${API_BASE_URL}/api/australia/rba-ois-screenshot`)
      if (!response.ok) {
        throw new Error('Failed to load screenshot URLs')
      }
      const result: ScreenshotData = await response.json()
      setData(result)
    } catch (err) {
      console.error('Failed to load screenshot URLs:', err)
      setError('スクリーンショットの読み込みに失敗しました')
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/australia/rba-ois-screenshot?force_refresh=true`
      )
      if (!response.ok) {
        throw new Error('Failed to refresh screenshots')
      }
      const result: ScreenshotData = await response.json()
      setData(result)
      setImageKey(Date.now())
    } catch (err) {
      console.error('Failed to refresh screenshots:', err)
      setError('スクリーンショットの更新に失敗しました')
    } finally {
      setRefreshing(false)
    }
  }

  const screenshots = data?.screenshots ?? []
  const totalCount = screenshots.length

  const handlePrev = () => {
    setCurrentIndex((prev) => (prev - 1 + totalCount) % totalCount)
  }

  const handleNext = () => {
    setCurrentIndex((prev) => (prev + 1) % totalCount)
  }

  const currentScreenshot = screenshots[currentIndex]

  // ローディング
  if (loading) {
    return (
      <Card title="OIS (Overnight Indexed Swaps)">
        <div style={{ textAlign: 'center', padding: '60px 0' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16, color: '#666' }}>読み込み中...</div>
        </div>
      </Card>
    )
  }

  // エラー
  if (error) {
    return (
      <Card
        title={
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', position: 'relative' }}>
            <span>OIS (Overnight Indexed Swaps)</span>
            {isMaster && (
              <Button size="small" icon={<ReloadOutlined />} onClick={handleRefresh} loading={refreshing} style={{ position: 'absolute', right: 0 }}>
                再取得
              </Button>
            )}
          </div>
        }
      >
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>{error}</div>
      </Card>
    )
  }

  return (
    <Card
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>OIS (Overnight Indexed Swaps)</span>
          {isMaster && (
            <Button size="small" icon={<ReloadOutlined />} onClick={handleRefresh} loading={refreshing}>
              更新
            </Button>
          )}
        </div>
      }
    >
      {/* ナビゲーションコントロール */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: 16,
          marginBottom: 16,
        }}
      >
        <Button
          icon={<LeftOutlined />}
          onClick={handlePrev}
          disabled={totalCount <= 1}
          size="small"
        />
        <Text strong style={{ fontSize: 15, minWidth: 80, textAlign: 'center' }}>
          {currentScreenshot?.label ?? '-'}
        </Text>
        <Button
          icon={<RightOutlined />}
          onClick={handleNext}
          disabled={totalCount <= 1}
          size="small"
        />
      </div>

      {/* ページインジケーター */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: 6, marginBottom: 12 }}>
        {screenshots.map((_, index) => (
          <div
            key={index}
            onClick={() => setCurrentIndex(index)}
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: index === currentIndex ? '#00BFFF' : '#555',
              cursor: 'pointer',
              transition: 'background-color 0.2s',
            }}
          />
        ))}
      </div>

      {/* スクリーンショット表示 */}
      <div style={{ textAlign: 'center' }}>
        {currentScreenshot?.url ? (
          <Image
            key={`${currentScreenshot.key}-${imageKey}`}
            src={`${API_BASE_URL}/api/australia/rba-ois-screenshot/${currentScreenshot.key}?t=${imageKey}`}
            alt={`RBA ${currentScreenshot.label}`}
            style={{ maxWidth: '100%', height: 'auto' }}
            preview={true}
            placeholder={
              <div style={{ padding: '40px', background: '#f5f5f5' }}>
                <Spin />
              </div>
            }
          />
        ) : (
          <div
            style={{
              padding: '60px 0',
              color: '#999',
              background: '#f5f5f5',
              borderRadius: 8,
            }}
          >
            スクリーンショットが利用できません
          </div>
        )}
      </div>

      {/* ソース情報 */}
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

// special 限定 (一般ユーザには非表示)
export default withVisibility(RbaOisChart, 'special')
