/**
 * BOJ展望レポートコンポーネント
 *
 * データソース: 日本銀行
 * URL: https://www.boj.or.jp/mopo/outlook/gor{YYMM}a.pdf
 * 発表月: 1月、4月、7月、10月（年4回）
 *
 * 表示内容:
 * - 政策委員の大勢見通し（PDF最終2ページ目）
 * - 政策委員の経済・物価見通しとリスク評価（PDF最終ページ）
 */
import { useEffect, useState } from 'react'
import { Card, Spin, Alert, Typography, Modal } from 'antd'
import {
  fetchBOJOutlook,
  formatReportDate,
  getOutlookImageUrl,
  type BOJOutlookData,
} from '../../../../utils/japan/bojOutlookApi'

const { Title, Link, Text } = Typography

const BOJOutlookReport: React.FC = () => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<BOJOutlookData | null>(null)
  const [modalVisible, setModalVisible] = useState(false)
  const [modalImage, setModalImage] = useState<{ src: string; title: string } | null>(null)

  useEffect(() => {
    let isSubscribed = true

    fetchBOJOutlook()
      .then((result) => {
        if (isSubscribed) {
          setData(result)
          setError(null)
        }
      })
      .catch((err) => {
        if (isSubscribed) {
          setError('BOJ展望レポートの取得に失敗しました')
          console.error('Error fetching BOJ outlook:', err)
        }
      })
      .finally(() => {
        if (isSubscribed) {
          setLoading(false)
        }
      })

    return () => {
      isSubscribed = false
    }
  }, [])

  const handleImageClick = (imageSrc: string, title: string) => {
    setModalImage({ src: imageSrc, title })
    setModalVisible(true)
  }

  const handleModalClose = () => {
    setModalVisible(false)
    setModalImage(null)
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
        <Card style={{ flex: '1 1 calc(50% - 8px)', minWidth: '400px' }}>
          <div style={{ textAlign: 'center', padding: '50px 0' }}>
            <Spin size="large" />
          </div>
        </Card>
        <Card style={{ flex: '1 1 calc(50% - 8px)', minWidth: '400px' }}>
          <div style={{ textAlign: 'center', padding: '50px 0' }}>
            <Spin size="large" />
          </div>
        </Card>
      </div>
    )
  }

  if (error || !data || data.error) {
    return (
      <Alert
        message="データ取得エラー"
        description={error || data?.error || 'データの読み込みに失敗しました'}
        type="error"
        showIcon
      />
    )
  }

  if (!data.report_date || !data.pdf_url) {
    return (
      <Alert
        message="データなし"
        description="BOJ展望レポートが見つかりませんでした"
        type="warning"
        showIcon
      />
    )
  }

  const forecastsImageUrl = getOutlookImageUrl('forecasts')
  const risksImageUrl = getOutlookImageUrl('risks')

  return (
    <Card>
      <div style={{ marginBottom: '16px', textAlign: 'center' }}>
        <Title level={4} style={{ marginBottom: 8 }}>
          経済・物価情勢の展望（{formatReportDate(data.report_date)}）
        </Title>
        <Link href={data.pdf_url} target="_blank" rel="noopener noreferrer">
          PDF全文を見る
        </Link>
      </div>

      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
        {/* Forecasts Table Card */}
        <Card
          title="政策委員の大勢見通し"
          style={{ flex: '1 1 calc(50% - 8px)', minWidth: '400px' }}
        >
          <img
            src={forecastsImageUrl}
            alt="BOJ Policy Board Forecasts"
            style={{ width: '100%', height: 'auto', cursor: 'pointer' }}
            onClick={() => handleImageClick(forecastsImageUrl, '政策委員の大勢見通し')}
          />
        </Card>

        {/* Risk Assessment Card */}
        <Card
          title="政策委員の経済・物価見通しとリスク評価"
          style={{ flex: '1 1 calc(50% - 8px)', minWidth: '400px' }}
        >
          <img
            src={risksImageUrl}
            alt="BOJ Risk Assessment"
            style={{ width: '100%', height: 'auto', cursor: 'pointer' }}
            onClick={() => handleImageClick(risksImageUrl, '政策委員の経済・物価見通しとリスク評価')}
          />
        </Card>
      </div>

      <div style={{ marginTop: 16, textAlign: 'center' }}>
        <Text type="secondary" style={{ fontSize: 14 }}>
          Data source: 日本銀行
        </Text>
      </div>

      {/* Image Preview Modal */}
      <Modal
        open={modalVisible}
        title={modalImage?.title}
        onCancel={handleModalClose}
        footer={null}
        width="90%"
        style={{ top: 20 }}
        styles={{ body: { padding: '10px' } }}
      >
        {modalImage && (
          <img
            src={modalImage.src}
            alt={modalImage.title}
            style={{ width: '100%', height: 'auto' }}
          />
        )}
      </Modal>
    </Card>
  )
}

export default BOJOutlookReport
