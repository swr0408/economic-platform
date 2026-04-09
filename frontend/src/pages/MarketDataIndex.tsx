import React from 'react'
import { Link } from 'react-router-dom'
import { Card, Row, Col, Typography, Space, Tag, Tooltip } from 'antd'
import { QuestionCircleOutlined } from '@ant-design/icons'
import { MARKET_CATEGORIES_DATA } from '../constants/marketData'
import { useHandbook } from '../contexts/HandbookContext'

const { Title, Text } = Typography

const colors = {
  bgSecondary: '#1e293b',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  border: '#334155',
}

function MarketDataIndex() {
  const { openHandbook } = useHandbook()
  return (
    <div style={{ padding: '20px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
        <Title level={3} style={{ margin: 0, color: colors.textPrimary }}>
          マーケットデータ
        </Title>
        <Tooltip title="相関関係 - データハンドブック">
          <QuestionCircleOutlined
            onClick={() => openHandbook('correlation-guide')}
            style={{
              fontSize: 18,
              color: colors.textSecondary,
              cursor: 'pointer',
              transition: 'color 0.2s',
            }}
            onMouseEnter={(e) => {
              ;(e.target as HTMLElement).style.color = '#10b981'
            }}
            onMouseLeave={(e) => {
              ;(e.target as HTMLElement).style.color = colors.textSecondary
            }}
          />
        </Tooltip>
      </div>
      <Text style={{ fontSize: 13, color: colors.textSecondary, marginBottom: 24, display: 'block' }}>
        株式・コモディティ・エネルギー・投機筋ポジション・オプション市場の情報
      </Text>

      <Row gutter={[16, 16]} style={{ marginTop: 20 }}>
        {MARKET_CATEGORIES_DATA.map((category) => {
          const hasData = category.subCategories.some((sub) => sub.indicators.length > 0)
          const indicatorCount = category.subCategories.reduce(
            (sum, sub) => sum + sub.indicators.length,
            0
          )

          return (
            <Col xs={24} sm={12} md={8} lg={6} key={category.code}>
              {hasData ? (
                <Link to={`/markets/${category.code}`} style={{ textDecoration: 'none' }}>
                  <CategoryCard category={category} indicatorCount={indicatorCount} />
                </Link>
              ) : (
                <CategoryCard category={category} indicatorCount={indicatorCount} disabled />
              )}
            </Col>
          )
        })}
      </Row>
    </div>
  )
}

function CategoryCard({
  category,
  indicatorCount,
  disabled = false,
}: {
  category: (typeof MARKET_CATEGORIES_DATA)[number]
  indicatorCount: number
  disabled?: boolean
}) {
  return (
    <Card
      hoverable={!disabled}
      style={{
        borderRadius: 10,
        border: `1px solid ${colors.border}`,
        background: colors.bgSecondary,
        height: '100%',
        transition: 'all 0.2s ease',
        opacity: disabled ? 0.5 : 1,
        cursor: disabled ? 'default' : 'pointer',
      }}
      styles={{
        body: { padding: 20, textAlign: 'center' },
      }}
    >
      <Space direction="vertical" size={10} style={{ width: '100%' }}>
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: 12,
            background: `${category.color}20`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto',
          }}
        >
          {React.cloneElement(category.icon as React.ReactElement, {
            style: { fontSize: 28, color: category.color },
          })}
        </div>
        <div>
          <Title level={5} style={{ margin: 0, color: colors.textPrimary }}>
            {category.name}
          </Title>
          <Text
            style={{ fontSize: 12, marginTop: 4, display: 'block', color: colors.textSecondary }}
          >
            {category.description}
          </Text>
          {disabled ? (
            <Tag color="default" style={{ marginTop: 8 }}>
              準備中
            </Tag>
          ) : (
            <Text
              style={{ fontSize: 11, marginTop: 8, display: 'block', color: colors.textSecondary }}
            >
              {indicatorCount} 銘柄
            </Text>
          )}
        </div>
      </Space>
    </Card>
  )
}

export default MarketDataIndex
