/**
 * NZ ANZ企業景況感物価関連（PDFスクリーンショット表示）
 * ANZ Business Outlook - Price Related Charts (PDF Page 2 Screenshot)
 *
 * PDFのPage 2を1枚の画像として表示
 *
 * データソース: ANZ Business Outlook PDF
 */

import { useState } from 'react'
import { Card, Button, Spin, Typography, Image, Tabs } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import type { NzAnzBusinessOutlookPriceData } from '../../../../hooks/useDashboardData'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

const { Text } = Typography

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

interface Props {
  data: NzAnzBusinessOutlookPriceData | null
}

export default function NzAnzBusinessSentimentPriceChart({ data }: Props) {
  const [imageKey, setImageKey] = useState(Date.now())
  const [refreshing, setRefreshing] = useState(false)
  const [activeTab, setActiveTab] = useState('chart')

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await fetch(`${API_BASE_URL}/api/newzealand/anz/business-outlook-price/refresh`, { method: 'POST' })
      setImageKey(Date.now())
    } catch (err) {
      console.error('Failed to refresh ANZ Business Outlook:', err)
    } finally {
      setRefreshing(false)
    }
  }

  // ローディング
  if (data === null) {
    return (
      <Card title="ANZ企業景況感（物価関連）">
        <div style={{ textAlign: 'center', padding: '60px 0' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16, color: '#666' }}>読み込み中...</div>
        </div>
      </Card>
    )
  }

  return (
    <Card
      id="anz-business-sentiment-price"
      title={
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', position: 'relative' }}>
          <span>ANZ企業景況感（物価関連）</span>
          <Button size="small" icon={<ReloadOutlined />} onClick={handleRefresh} loading={refreshing} style={{ position: 'absolute', right: 0 }}>
            更新
          </Button>
        </div>
      }
    >
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        size="small"
        items={[
          {
            key: 'chart',
            label: '時系列',
            children: (
              <>
                {/* スクリーンショット表示 */}
                <div style={{ textAlign: 'center' }}>
                  {data.page2_exists ? (
                    <Image
                      key={`page2-${imageKey}`}
                      src={`${API_BASE_URL}/api/newzealand/anz/business-outlook-price/page2?t=${imageKey}`}
                      alt="ANZ Business Outlook Price Related Charts"
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
                    <a
                      href="https://www.anz.co.nz/about-us/economic-markets-research/business-outlook/"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      ANZ Business Outlook
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
              </>
            ),
          },
          {
            key: 'impact',
            label: 'マーケットインパクト',
            children: (
              <MarketImpactTab indicatorId="nz_anz_corporate business_sentiment" />
            ),
          },
        ]}
      />
    </Card>
  )
}
