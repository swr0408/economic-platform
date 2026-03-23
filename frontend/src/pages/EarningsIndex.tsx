import React from 'react'
import { Link } from 'react-router-dom'
import { Card, Row, Col, Typography, Space, Tag } from 'antd'
import { GlobalOutlined } from '@ant-design/icons'
import { EARNINGS_CATEGORIES_DATA, EARNINGS_COUNTRIES } from '../constants/earningsData'
import type { EarningsCategoryItem } from '../constants/earningsData'

const { Title, Text } = Typography

const colors = {
  bgSecondary:  '#1e293b',
  textPrimary:  '#f1f5f9',
  textSecondary:'#94a3b8',
  border:       '#334155',
  accent:       '#10b981',
}

function EarningsIndex() {
  const totalCompanies = EARNINGS_COUNTRIES.reduce((s, c) => s + c.companies.length, 0)

  return (
    <div style={{ padding: '20px 24px' }}>
      <Title level={3} style={{ marginBottom: 4, color: colors.textPrimary }}>
        決算
      </Title>
      <Text style={{ fontSize: 13, color: colors.textSecondary, marginBottom: 24, display: 'block' }}>
        世界 {EARNINGS_COUNTRIES.length} カ国・{totalCompanies} 社の企業決算カレンダー・決算データ
      </Text>

      {/* カテゴリカード */}
      <Row gutter={[16, 16]} style={{ marginTop: 20 }}>
        {EARNINGS_CATEGORIES_DATA.map((category) => {
          // カレンダーは /all (全国)、データは国選択へ
          const to = category.code === 'calendar' ? '/earnings/calendar/all' : `/earnings/${category.code}`
          return (
            <Col xs={24} sm={12} md={8} key={category.code}>
              <Link to={to} style={{ textDecoration: 'none' }}>
                <CategoryCard category={category} />
              </Link>
            </Col>
          )
        })}
      </Row>

      {/* 対応国一覧 */}
      <div style={{ marginTop: 40 }}>
        <Space align="center" style={{ marginBottom: 12 }}>
          <GlobalOutlined style={{ color: colors.accent, fontSize: 16 }} />
          <Title level={5} style={{ margin: 0, color: colors.textPrimary }}>
            対応国一覧
          </Title>
        </Space>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {EARNINGS_COUNTRIES.map((country) => (
            <Tag
              key={country.code}
              style={{
                background: `${country.color}15`,
                border: `1px solid ${country.color}40`,
                color: colors.textPrimary,
                fontSize: 13,
                padding: '4px 10px',
                borderRadius: 6,
              }}
            >
              {country.flag} {country.nameJa}
              <span style={{ color: colors.textSecondary, marginLeft: 4, fontSize: 11 }}>
                {country.companies.length}社
              </span>
            </Tag>
          ))}
        </div>
      </div>
    </div>
  )
}

function CategoryCard({ category }: { category: EarningsCategoryItem }) {
  return (
    <Card
      hoverable
      style={{
        borderRadius: 10,
        border: `1px solid ${colors.border}`,
        background: colors.bgSecondary,
        transition: 'all 0.2s ease',
      }}
      styles={{ body: { padding: 20, textAlign: 'center' } }}
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
            {category.nameJa}
          </Title>
          <Text style={{ fontSize: 12, marginTop: 4, display: 'block', color: colors.textSecondary }}>
            {category.description}
          </Text>
          <Text style={{ fontSize: 11, marginTop: 8, display: 'block', color: colors.textSecondary }}>
            {EARNINGS_COUNTRIES.length} カ国
          </Text>
        </div>
      </Space>
    </Card>
  )
}

export default EarningsIndex
