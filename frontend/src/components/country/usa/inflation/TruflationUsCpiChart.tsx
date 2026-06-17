/**
 * Truflation US CPI Inflation Index チャートコンポーネント
 *
 * 静的PNG画像（1Y / 3Y / Max）をカルーセルで切り替え表示
 *
 * データソース:
 * - Truflation (https://truflation.com/)
 */
import { useState, useEffect } from 'react'
import { Button, Spin, Image } from 'antd'
import { LeftOutlined, RightOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import { withVisibility } from '../../../common/withVisibility'

import { fetchWithTimeout } from '../../../../utils/apiConfig'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

interface ScreenshotItem {
  key: string
  label: string
  url: string | null
  exists: boolean
  version?: number
}

interface ScreenshotData {
  screenshots: ScreenshotItem[]
}

function TruflationUsCpiChart() {
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
      const response = await fetchWithTimeout(`${API_BASE_URL}/api/usa/truflation-screenshot`, undefined, 30_000)
      if (!response.ok) {
        throw new Error('Failed to load screenshot URLs')
      }
      const result: ScreenshotData = await response.json()
      setData(result)
    } catch (err) {
      console.error('Failed to load Truflation screenshot URLs:', err)
      setError('スクリーンショットの読み込みに失敗しました')
    } finally {
      setLoading(false)
    }
  }

  const screenshots = data?.screenshots ?? []
  const totalCount = screenshots.length
  const currentScreenshot = screenshots[currentIndex]

  const handlePrev = () => {
    setCurrentIndex((prev) => (prev - 1 + totalCount) % totalCount)
  }

  const handleNext = () => {
    setCurrentIndex((prev) => (prev + 1) % totalCount)
  }

  return (
    <ChartContainer
      title="Truflation US CPI Inflation Index"
      dataSource="Truflation"
      sourceUrl="https://truflation.com/marketplace/us-inflation-rate"
      showPeriodSelector={false}
      handbookId="truflation-us-cpi"
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px 0' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16, color: '#666' }}>読み込み中...</div>
        </div>
      ) : error ? (
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>{error}</div>
      ) : (
        <>
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
            <span style={{ fontSize: 15, fontWeight: 600, minWidth: 60, textAlign: 'center' }}>
              {currentScreenshot?.label ?? '-'}
            </span>
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
            {currentScreenshot?.exists && currentScreenshot?.url ? (
              <Image
                key={`${currentScreenshot.key}-${currentScreenshot.version ?? 0}`}
                src={`${API_BASE_URL}${currentScreenshot.url}?v=${currentScreenshot.version ?? 0}`}
                alt={`Truflation ${currentScreenshot.label}`}
                style={{ maxWidth: '100%', height: 'auto' }}
                preview={true}
                placeholder={
                  <div style={{ padding: '40px', background: '#1a1a2e' }}>
                    <Spin />
                  </div>
                }
              />
            ) : (
              <div
                style={{
                  padding: '60px 0',
                  color: '#999',
                  background: '#1a1a2e',
                  borderRadius: 8,
                }}
              >
                スクリーンショットが利用できません
              </div>
            )}
          </div>
        </>
      )}
    </ChartContainer>
  )
}

// special 限定 (一般ユーザには非表示)
export default withVisibility(TruflationUsCpiChart, 'special')
