/**
 * NAB企業調査 コスト・価格チャート（PDFスクリーンショット表示）
 * NAB Monthly Business Survey - Cost & Price Chart Screenshots
 *
 * PDFから切り出したChart 18 (Cost Growth) とChart 20 (Output Price Growth) を
 * 左右ボタンで切り替えて表示
 *
 * データソース: NAB Monthly Business Survey (PDF)
 */

import { useState } from 'react'
import { Card, Button, Spin, Typography, Image } from 'antd'
import { ReloadOutlined, LeftOutlined, RightOutlined } from '@ant-design/icons'
import type { NabCostPriceData } from '../../../../hooks/useDashboardData'
import { useIsMaster } from '../../../../hooks/useIsMaster'
import { withVisibility } from '../../../common/withVisibility'

const { Text } = Typography

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

interface Props {
  data: NabCostPriceData | null
}

function AuNabBusinessConfidenceIndexCostPriceChart({ data }: Props) {
  const isMaster = useIsMaster()
  const [imageKey, setImageKey] = useState(Date.now())
  const [refreshing, setRefreshing] = useState(false)
  const [currentIndex, setCurrentIndex] = useState(0)

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await fetch(`${API_BASE_URL}/api/australia/nab/cost-price/refresh`, { method: 'POST' })
      setImageKey(Date.now())
    } catch (err) {
      console.error('Failed to refresh NAB charts:', err)
    } finally {
      setRefreshing(false)
    }
  }

  // ローディング
  if (data === null) {
    return (
      <Card title="NAB企業調査（コスト・価格）">
        <div style={{ textAlign: 'center', padding: '60px 0' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16, color: '#666' }}>読み込み中...</div>
        </div>
      </Card>
    )
  }

  const screenshots = data.screenshots ?? []
  const totalCount = screenshots.length

  const handlePrev = () => {
    setCurrentIndex((prev) => (prev - 1 + totalCount) % totalCount)
  }

  const handleNext = () => {
    setCurrentIndex((prev) => (prev + 1) % totalCount)
  }

  const currentScreenshot = screenshots[currentIndex]

  return (
    <Card
      title={
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', position: 'relative' }}>
          <span>NAB企業調査（コスト・価格）</span>
          {isMaster && (
            <Button size="small" icon={<ReloadOutlined />} onClick={handleRefresh} loading={refreshing} style={{ position: 'absolute', right: 0 }}>
              更新
            </Button>
          )}
        </div>
      }
    >
      {/* ナビゲーションコントロール */}
      {totalCount > 0 && (
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
          <Text strong style={{ fontSize: 15, minWidth: 280, textAlign: 'center' }}>
            {currentScreenshot?.label_ja ?? currentScreenshot?.label ?? '-'}
          </Text>
          <Button
            icon={<RightOutlined />}
            onClick={handleNext}
            disabled={totalCount <= 1}
            size="small"
          />
        </div>
      )}

      {/* ページインジケーター */}
      {totalCount > 1 && (
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
      )}

      {/* スクリーンショット表示 */}
      <div style={{ textAlign: 'center' }}>
        {currentScreenshot?.exists ? (
          <Image
            key={`${currentScreenshot.key}-${imageKey}`}
            src={`${API_BASE_URL}/api/australia/nab/cost-price/${currentScreenshot.key}?t=${imageKey}`}
            alt={`NAB ${currentScreenshot.label}`}
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
            チャート画像が利用できません
          </div>
        )}
      </div>

      {/* ソース情報 */}
      <div style={{ marginTop: 16, textAlign: 'center' }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          Data Source:{' '}
          <a href="https://news.nab.com.au/tag/economic-market" target="_blank" rel="noopener noreferrer">
            NAB Monthly Business Survey
          </a>
          {data.last_updated && (
            <span style={{ marginLeft: 16 }}>
              Last Updated: {new Date(data.last_updated).toLocaleString('ja-JP')}
            </span>
          )}
          {data.next_release && (
            <span style={{ marginLeft: 16 }}>
              次回発表: {data.next_release.date}
            </span>
          )}
        </Text>
      </div>
    </Card>
  )
}

// special 限定 (一般ユーザには非表示)
export default withVisibility(AuNabBusinessConfidenceIndexCostPriceChart, 'special')
