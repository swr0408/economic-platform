/**
 * 10年物価連動国債BEIチャートコンポーネント
 *
 * BEI (Break-Even Inflation): ブレークイーブン・インフレ率
 * 市場が予想する今後10年間の平均インフレ率を表す
 *
 * データソース:
 * - 財務省 (MOF)
 * - https://www.mof.go.jp/jgbs/topics/bond/10year_inflation-indexed/bei.pdf
 *
 * 発表スケジュール:
 * - 毎週土曜日 7:00 JST頃
 */
import { useEffect, useState } from 'react'
import { CalendarOutlined, ReloadOutlined } from '@ant-design/icons'
import { Button, Spin } from 'antd'
import ChartContainer from '../../../common/ChartContainer'
import { TEXT_COLORS } from '../../usa/common/chartConstants'

// 財務省のURL
const MOF_BEI_PAGE_URL = 'https://www.mof.go.jp/jgbs/topics/bond/10year_inflation-indexed/bei.htm'
// ローカルPDF API URL（バックエンドがダウンロードしたPDF）
const LOCAL_BEI_PDF_URL = '/api/japan/bei/pdf'

// 型定義
interface BEIDataPoint {
  date: string
  value: number
  fixed_rate_10y?: number
  inflation_indexed_10y?: number
}

interface NextRelease {
  date?: string
  time_jst?: string
  datetime_jst?: string
}

interface BEIData {
  data: BEIDataPoint[]
  latest?: BEIDataPoint | null
  next_release?: NextRelease | null
  last_updated?: string
  cached?: boolean
  source?: string
  error?: string
}

// 次回発表日時のフォーマット
const formatNextRelease = (nextRelease: NextRelease | null | undefined): string | null => {
  if (!nextRelease) return null
  if (nextRelease.datetime_jst) {
    const dt = new Date(nextRelease.datetime_jst)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    const hours = dt.getHours().toString().padStart(2, '0')
    const minutes = dt.getMinutes().toString().padStart(2, '0')
    return `${month}/${day} ${hours}:${minutes}`
  }
  if (nextRelease.time_jst && nextRelease.date) {
    const dt = new Date(nextRelease.date)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    return `${month}/${day} ${nextRelease.time_jst}`
  }
  if (nextRelease.date) {
    const dt = new Date(nextRelease.date)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    return `${month}/${day}`
  }
  return null
}

// 日付フォーマット
const formatDate = (dateStr: string): string => {
  const date = new Date(dateStr)
  const month = date.getMonth() + 1
  const day = date.getDate()
  return `${month}/${day}`
}

/**
 * Fetch BEI data from backend
 */
async function fetchBEIData(): Promise<BEIData> {
  const response = await fetch('/api/japan/bei')

  if (!response.ok) {
    throw new Error(`Failed to fetch BEI data: ${response.statusText}`)
  }

  const data: BEIData = await response.json()
  return data
}

export default function BEIChart() {
  const [beiData, setBeiData] = useState<BEIData | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [pdfKey, setPdfKey] = useState<number>(0)

  useEffect(() => {
    let isSubscribed = true

    const loadData = () => {
      setLoading(true)

      fetchBEIData()
        .then((data) => {
          if (isSubscribed) {
            setBeiData(data)
          }
        })
        .catch((err) => {
          console.error('Failed to load BEI data:', err)
        })
        .finally(() => {
          if (isSubscribed) {
            setLoading(false)
          }
        })
    }

    loadData()

    return () => {
      isSubscribed = false
    }
  }, [])

  const latestData = beiData?.latest || (beiData?.data?.length ? beiData.data[beiData.data.length - 1] : null)

  const handleRefresh = () => {
    setPdfKey(prev => prev + 1)
  }

  return (
    <div id="bei-chart">
      <ChartContainer
        title="10年物価連動国債BEI（ブレークイーブン・インフレ率）"
        dataSource="財務省"
        sourceUrl={MOF_BEI_PAGE_URL}
        showPeriodSelector={false}
      >
        {/* 最新値表示 */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 8,
          marginBottom: 8,
        }}>
          {/* 左側: 最新値 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {loading ? (
              <Spin size="small" />
            ) : (
              <>
                {latestData?.date && (
                  <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                    {formatDate(latestData.date)}
                  </span>
                )}
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ fontSize: 11, color: TEXT_COLORS.secondary }}>BEI:</span>
                  <span style={{ fontSize: 14, fontWeight: 'bold', color: '#52c41a' }}>
                    {latestData?.value?.toFixed(3) ?? '-'}%
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ fontSize: 11, color: TEXT_COLORS.secondary }}>10年固定利付債:</span>
                  <span style={{ fontSize: 14, fontWeight: 'bold', color: '#1890ff' }}>
                    {latestData?.fixed_rate_10y?.toFixed(3) ?? '-'}%
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ fontSize: 11, color: TEXT_COLORS.secondary }}>10年物価連動債:</span>
                  <span style={{ fontSize: 14, fontWeight: 'bold', color: '#722ed1' }}>
                    {latestData?.inflation_indexed_10y?.toFixed(3) ?? '-'}%
                  </span>
                </div>
              </>
            )}
          </div>

          {/* 右側: 次回発表 & 更新ボタン */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {beiData?.next_release && formatNextRelease(beiData.next_release) && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                fontSize: 11,
                color: TEXT_COLORS.secondary,
              }}>
                <CalendarOutlined />
                <span>次回: {formatNextRelease(beiData.next_release)}</span>
              </div>
            )}
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={handleRefresh}
              title="PDFを再読み込み"
            />
          </div>
        </div>

        {/* PDF埋め込み表示（ローカルサーバーからのPDF） */}
        <div style={{
          width: '100%',
          height: 580,
          overflow: 'hidden',
          backgroundColor: '#f5f5f5',
        }}>
          <iframe
            key={pdfKey}
            src={`${LOCAL_BEI_PDF_URL}#toolbar=0&navpanes=0&scrollbar=0&view=FitH`}
            width="100%"
            height="100%"
            style={{ border: 'none' }}
            title="10年物価連動国債BEI"
          />
        </div>
      </ChartContainer>
    </div>
  )
}
