import React from 'react'
import { Card, Typography } from 'antd'
import PeriodSelector, { type PeriodValue } from './PeriodSelector'

const { Title, Text } = Typography

interface ChartContainerProps {
  title: string
  children: React.ReactNode
  loading?: boolean
  dataSource?: string
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
  onPeriodChange,
  selectedPeriod,
  showPeriodSelector = true,
  titleLevel = 4,
  extra,
  showDataSource = true,
  description,
  source,
}: ChartContainerProps) {
  if (loading) {
    return (
      <Card>
        <Title level={titleLevel} style={{ marginBottom: 8, textAlign: 'center' }}>
          {title}
        </Title>
        <div style={{ textAlign: 'center', padding: '40px' }}>Loading...</div>
      </Card>
    )
  }

  return (
    <Card>
      <Title level={titleLevel} style={{ marginBottom: 8, textAlign: 'center' }}>
        {title}
      </Title>

      {description && (
        <div style={{ marginBottom: 12, fontSize: '13px', color: '#666', textAlign: 'center' }}>
          <Text type="secondary">{description}</Text>
        </div>
      )}

      {showPeriodSelector && onPeriodChange && (
        <PeriodSelector onPeriodChange={onPeriodChange} selectedPeriod={selectedPeriod} />
      )}

      {extra}

      {children}

      <div style={{ marginTop: 16, fontSize: '12px', color: '#666' }}>
        {showDataSource && source && (
          <div>
            <Text type="secondary">Data source: {source}</Text>
          </div>
        )}
        {showDataSource && !source && (
          <div>
            <Text type="secondary">Data source: {dataSource}</Text>
          </div>
        )}
      </div>
    </Card>
  )
}
