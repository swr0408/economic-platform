import React from 'react'
import { useParams, Link } from 'react-router-dom'
import { Button, Space, Typography, Alert } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { getMarketCategory } from '../constants/marketData'
import EquitiesCharts from '../components/market/equities/EquitiesCharts'
import CommoditiesCharts from '../components/market/commodities/CommoditiesCharts'
import EnergyCharts from '../components/market/energy/EnergyCharts'
import ForexCharts from '../components/market/forex/ForexCharts'
import CotCharts from '../components/market/cot/CotCharts'
import OptionsCharts from '../components/market/options/OptionsCharts'

const { Title, Text } = Typography

const colors = {
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  bgSecondary: '#1e293b',
  border: '#334155',
  accent: '#10b981',
}

const CATEGORY_CHARTS: Record<string, React.ComponentType> = {
  equities: EquitiesCharts,
  commodities: CommoditiesCharts,
  energy: EnergyCharts,
  forex: ForexCharts,
  cot: CotCharts,
  options: OptionsCharts,
}

function MarketDataCategory() {
  const { categoryCode } = useParams<{ categoryCode: string }>()

  if (!categoryCode) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Text style={{ color: colors.textSecondary }}>カテゴリが指定されていません。</Text>
        <br />
        <Link to="/markets">
          <Button type="link" icon={<ArrowLeftOutlined />} style={{ color: colors.accent }}>
            マーケットデータ一覧へ戻る
          </Button>
        </Link>
      </div>
    )
  }

  const category = getMarketCategory(categoryCode)

  if (!category) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Text style={{ color: colors.textSecondary }}>カテゴリが見つかりませんでした。</Text>
        <br />
        <Link to="/markets">
          <Button type="link" icon={<ArrowLeftOutlined />} style={{ color: colors.accent }}>
            マーケットデータ一覧へ戻る
          </Button>
        </Link>
      </div>
    )
  }

  const ChartsComponent = CATEGORY_CHARTS[categoryCode]

  if (!ChartsComponent) {
    return (
      <div style={{ padding: '20px 24px' }}>
        <Space style={{ marginBottom: 24 }} wrap>
          <Link to="/markets">
            <Button type="default" icon={<ArrowLeftOutlined />}>
              マーケットデータ一覧
            </Button>
          </Link>
        </Space>
        <Alert
          type="info"
          message={`${category.name}は準備中です`}
          description="今後のアップデートで追加予定です。"
          showIcon
        />
      </div>
    )
  }

  return (
    <div style={{ padding: '20px 24px' }}>
      <Space style={{ marginBottom: 24 }} wrap>
        <Link to="/markets">
          <Button type="default" icon={<ArrowLeftOutlined />}>
            マーケットデータ一覧
          </Button>
        </Link>
      </Space>

      <div style={{ marginBottom: 24 }}>
        <Space size={12} align="center">
          {React.cloneElement(category.icon as React.ReactElement, {
            style: { fontSize: 24, color: category.color },
          })}
          <Title level={3} style={{ margin: 0, color: colors.textPrimary }}>
            {category.name}
          </Title>
        </Space>
        <Text
          style={{
            fontSize: 13,
            color: colors.textSecondary,
            display: 'block',
            marginTop: 4,
            marginLeft: 36,
          }}
        >
          {category.description}
        </Text>
      </div>

      <ChartsComponent />
    </div>
  )
}

export default MarketDataCategory
