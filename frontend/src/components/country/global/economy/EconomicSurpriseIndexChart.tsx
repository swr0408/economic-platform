/**
 * エコノミックサプライズ指数（Economic Surprise Index）チャートコンポーネント
 *
 * 手動配置されたPNG画像を表示。ファイル更新日時で自動キャッシュバスティング。
 * 地域切替: グローバル / 日本 / 中国
 * データソース: MacroMicro (Citi Economic Surprise Index)
 */

import { useState, useEffect, useCallback } from 'react'
import { Card, Spin, Typography, Image } from 'antd'
import { ViewModeButtonGroup } from '../../usa/common/ChartComponents'

const { Text } = Typography

import { fetchWithTimeout } from '../../../../utils/apiConfig'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

type Region = 'global' | 'japan' | 'china'

const REGION_OPTIONS: { mode: Region; label: string }[] = [
  { mode: 'global', label: 'グローバル' },
  { mode: 'japan', label: '日本' },
  { mode: 'china', label: '中国' },
]

const REGION_SOURCE_URLS: Record<Region, string> = {
  global: 'https://en.macromicro.me/charts/45866/global-citi-surprise-index',
  japan: 'https://en.macromicro.me/charts/55983/japan-citi-surprise-index-earning',
  china: 'https://en.macromicro.me/charts/55758/cn-citi-surprise-index-earning',
}

interface ScreenshotData {
  screenshot_url: string | null
  last_updated: string | null
}

export default function EconomicSurpriseIndexChart() {
  const [region, setRegion] = useState<Region>('global')
  const [loading, setLoading] = useState(true)
  const [dataMap, setDataMap] = useState<Record<Region, ScreenshotData | null>>({
    global: null,
    japan: null,
    china: null,
  })
  const [error, setError] = useState<string | null>(null)

  const loadScreenshotUrl = useCallback(async (r: Region) => {
    try {
      setLoading(true)
      setError(null)
      const response = await fetchWithTimeout(`${API_BASE_URL}/api/global/economic-surprise-index-screenshot?region=${r}`, undefined, 30_000)
      if (!response.ok) {
        throw new Error('Failed to load screenshot URL')
      }
      const result = await response.json()
      setDataMap(prev => ({ ...prev, [r]: result }))
    } catch (err) {
      console.error('Failed to load screenshot URL:', err)
      setError('画像の読み込みに失敗しました')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadScreenshotUrl(region)
  }, [region, loadScreenshotUrl])

  const currentData = dataMap[region]

  // ファイルの更新日時をキャッシュバスティングキーに使用
  const cacheKey = currentData?.last_updated
    ? new Date(currentData.last_updated).getTime()
    : 0

  const cardTitle = (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
      <span>エコノミックサプライズ指数</span>
    </div>
  )

  if (loading && !currentData) {
    return (
      <Card title={cardTitle}>
        <div style={{ textAlign: 'center', padding: '60px 0' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16, color: '#666' }}>読み込み中...</div>
        </div>
      </Card>
    )
  }

  if (error && !currentData) {
    return (
      <Card title={cardTitle}>
        <ViewModeButtonGroup options={REGION_OPTIONS} currentMode={region} onChange={setRegion} />
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          {error}
        </div>
      </Card>
    )
  }

  return (
    <div id="economic-surprise-index">
      <Card title={cardTitle}>
        {/* 地域切替 */}
        <ViewModeButtonGroup options={REGION_OPTIONS} currentMode={region} onChange={setRegion} />

        {/* 画像表示 */}
        <div style={{ textAlign: 'center' }}>
          {currentData?.screenshot_url ? (
            <Image
              key={`economic-surprise-${region}-${cacheKey}`}
              src={`${API_BASE_URL}/api/global/economic-surprise-index-screenshot/image?region=${region}&t=${cacheKey}`}
              alt={`Economic Surprise Index - ${region}`}
              style={{ maxWidth: '100%', height: 'auto' }}
              preview={true}
              placeholder={
                <div style={{ padding: '40px', background: '#f5f5f5' }}>
                  <Spin />
                </div>
              }
            />
          ) : (
            <div style={{ padding: '60px 0', color: '#999', background: '#f5f5f5', borderRadius: 8 }}>
              {loading ? (
                <>
                  <Spin />
                  <div style={{ marginTop: 8 }}>読み込み中...</div>
                </>
              ) : (
                '画像が配置されていません'
              )}
            </div>
          )}
        </div>

        {/* ソース情報 */}
        <div style={{ marginTop: 16, textAlign: 'center' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Data Source:{' '}
            <a
              href={REGION_SOURCE_URLS[region]}
              target="_blank"
              rel="noopener noreferrer"
            >
              MacroMicro
            </a>
            {currentData?.last_updated && (
              <span style={{ marginLeft: 16 }}>
                Last Updated: {new Date(currentData.last_updated).toLocaleString('ja-JP')}
              </span>
            )}
          </Text>
        </div>
      </Card>
    </div>
  )
}
