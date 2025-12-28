import React from 'react'
import { Card, Typography } from 'antd'
import PeriodSelector, { type PeriodValue } from './PeriodSelector'

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
}: ChartContainerProps) {
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
    <Card style={cardStyle}>
      <Title level={titleLevel} style={{ marginBottom: 8, textAlign: 'center', color: DARK_THEME.textPrimary }}>
        {title}
      </Title>

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
