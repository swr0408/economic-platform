import React, { useRef, useState, useCallback } from 'react'
import { Card, Typography, Tooltip, message } from 'antd'
import { QuestionCircleOutlined, CameraOutlined, CheckOutlined } from '@ant-design/icons'
import html2canvas from 'html2canvas'
import PeriodSelector, { type PeriodValue } from './PeriodSelector'
import { useHandbook } from '../../contexts/HandbookContext'
import { HANDBOOK_MAP } from '../../content/handbookRegistry'

const { Title } = Typography

// EconAlpha ダークテーマカラー
const DARK_THEME = {
  bgPrimary: '#0f172a',      // ページ背景
  bgSecondary: '#1e293b',    // カード背景（ページより少し明るい）
  bgTertiary: '#334155',     // 強調エリア
  border: '#334155',
  borderLight: '#475569',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  accent: '#10b981',
}

interface ChartContainerProps {
  title: string
  children: React.ReactNode
  loading?: boolean
  dataSource?: string
  sourceUrl?: string  // 公式サイトへのリンクURL
  onPeriodChange?: (period: PeriodValue) => void
  selectedPeriod?: PeriodValue
  showPeriodSelector?: boolean
  titleLevel?: 1 | 2 | 3 | 4 | 5
  extra?: React.ReactNode
  showDataSource?: boolean
  description?: string
  source?: string
  /** ハンドブックの指標ID。指定するとタイトル横に?ボタンが表示される */
  handbookId?: string
}

export default function ChartContainer({
  title,
  children,
  loading = false,
  dataSource = 'Federal Reserve Economic Data (FRED)',
  sourceUrl,
  onPeriodChange,
  selectedPeriod,
  showPeriodSelector = true,
  titleLevel = 4,
  extra,
  showDataSource = true,
  description,
  source,
  handbookId,
}: ChartContainerProps) {
  const { openHandbook } = useHandbook()
  const hasHandbook = handbookId && HANDBOOK_MAP.has(handbookId)
  const cardRef = useRef<HTMLDivElement>(null)
  const [copying, setCopying] = useState(false)

  const handleCopyChart = useCallback(async () => {
    if (!cardRef.current || copying) return
    setCopying(true)
    try {
      const canvas = await html2canvas(cardRef.current, {
        backgroundColor: DARK_THEME.bgSecondary,
        scale: 2,
        useCORS: true,
        logging: false,
      })
      canvas.toBlob(async (blob) => {
        if (!blob) {
          message.error('画像の生成に失敗しました')
          setCopying(false)
          return
        }
        try {
          await navigator.clipboard.write([
            new ClipboardItem({ 'image/png': blob }),
          ])
          message.success('クリップボードにコピーしました')
        } catch {
          // クリップボードAPIが使えない場合はダウンロードにフォールバック
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `${title}.png`
          a.click()
          URL.revokeObjectURL(url)
          message.success('画像をダウンロードしました')
        }
        setCopying(false)
      }, 'image/png')
    } catch {
      message.error('画像の生成に失敗しました')
      setCopying(false)
    }
  }, [copying, title])

  // チャートカードのスタイル（ダークテーマ・ページ背景より少し明るく階層感を出す）
  const cardStyle: React.CSSProperties = {
    background: DARK_THEME.bgSecondary,
    border: `1px solid ${DARK_THEME.borderLight}`,
    borderRadius: 12,
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
  }

  if (loading) {
    return (
      <Card style={cardStyle}>
        <Title level={titleLevel} style={{ marginBottom: 8, textAlign: 'center', color: DARK_THEME.textPrimary }}>
          {title}
        </Title>
        <div style={{ textAlign: 'center', padding: '40px', color: DARK_THEME.textSecondary }}>Loading...</div>
      </Card>
    )
  }

  return (
    <Card style={cardStyle} ref={cardRef}>
      <div style={{ position: 'relative', marginBottom: 8 }}>
        <Tooltip title={copying ? 'コピー中...' : '画像をコピー'}>
          <span
            onClick={handleCopyChart}
            style={{
              position: 'absolute',
              left: 0,
              top: '50%',
              transform: 'translateY(-50%)',
              fontSize: 16,
              color: copying ? DARK_THEME.accent : DARK_THEME.textSecondary,
              cursor: copying ? 'wait' : 'pointer',
              transition: 'color 0.2s',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}
            onMouseEnter={(e) => { if (!copying) (e.currentTarget as HTMLElement).style.color = DARK_THEME.accent }}
            onMouseLeave={(e) => { if (!copying) (e.currentTarget as HTMLElement).style.color = DARK_THEME.textSecondary }}
          >
            {copying ? <CheckOutlined /> : <CameraOutlined />}
          </span>
        </Tooltip>
        <Title level={titleLevel} style={{ marginBottom: 0, textAlign: 'center', color: DARK_THEME.textPrimary }}>
          {title}
        </Title>
        {hasHandbook && (
          <Tooltip title="データハンドブック">
            <QuestionCircleOutlined
              onClick={() => openHandbook(handbookId)}
              style={{
                position: 'absolute',
                right: 0,
                top: '50%',
                transform: 'translateY(-50%)',
                fontSize: 18,
                color: DARK_THEME.textSecondary,
                cursor: 'pointer',
                transition: 'color 0.2s',
              }}
              onMouseEnter={(e) => { (e.target as HTMLElement).style.color = DARK_THEME.accent }}
              onMouseLeave={(e) => { (e.target as HTMLElement).style.color = DARK_THEME.textSecondary }}
            />
          </Tooltip>
        )}
      </div>

      {description && (
        <div style={{ marginBottom: 12, fontSize: '13px', color: DARK_THEME.textSecondary, textAlign: 'center' }}>
          {description}
        </div>
      )}

      {showPeriodSelector && onPeriodChange && (
        <PeriodSelector onPeriodChange={onPeriodChange} selectedPeriod={selectedPeriod} />
      )}

      {extra}

      {children}

      <div style={{ marginTop: 16, fontSize: '12px', color: DARK_THEME.textSecondary }}>
        {showDataSource && (source || dataSource) && (
          <div>
            Data source:{' '}
            {sourceUrl ? (
              <a
                href={sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: DARK_THEME.accent }}
              >
                {source || dataSource}
              </a>
            ) : (
              source || dataSource
            )}
          </div>
        )}
      </div>
    </Card>
  )
}
