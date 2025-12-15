import { Link } from 'react-router-dom'
import { Card, Row, Col, Typography, Space } from 'antd'
import {
  GlobalOutlined,
  DollarOutlined,
  BankOutlined,
  LineChartOutlined,
  HomeOutlined,
  TrophyOutlined,
  CrownOutlined,
  StarOutlined,
  FlagOutlined,
} from '@ant-design/icons'

const { Title, Text } = Typography

type Country = {
  code: string
  name: string
  flag: string
  icon: React.ReactNode
  description: string
}

const COUNTRIES: Country[] = [
  {
    code: 'usa',
    name: 'アメリカ',
    flag: '🇺🇸',
    icon: <DollarOutlined style={{ fontSize: 24, color: '#1890ff' }} />,
    description: '世界最大の経済大国',
  },
  {
    code: 'japan',
    name: '日本',
    flag: '🇯🇵',
    icon: <TrophyOutlined style={{ fontSize: 24, color: '#ff4d4f' }} />,
    description: '技術革新と製造業の中心地',
  },
  {
    code: 'eurozone',
    name: 'ユーロ圏',
    flag: '🇪🇺',
    icon: <CrownOutlined style={{ fontSize: 24, color: '#faad14' }} />,
    description: '統合された欧州経済圏',
  },
  {
    code: 'uk',
    name: 'イギリス',
    flag: '🇬🇧',
    icon: <BankOutlined style={{ fontSize: 24, color: '#722ed1' }} />,
    description: '金融サービスの国際的中心地',
  },
  {
    code: 'china',
    name: '中国',
    flag: '🇨🇳',
    icon: <StarOutlined style={{ fontSize: 24, color: '#f5222d' }} />,
    description: '世界第2位の経済大国',
  },
  {
    code: 'australia',
    name: 'オーストラリア',
    flag: '🇦🇺',
    icon: <GlobalOutlined style={{ fontSize: 24, color: '#52c41a' }} />,
    description: '資源豊富な先進国',
  },
  {
    code: 'newzealand',
    name: 'ニュージーランド',
    flag: '🇳🇿',
    icon: <LineChartOutlined style={{ fontSize: 24, color: '#13c2c2' }} />,
    description: '農業と観光の島国',
  },
  {
    code: 'canada',
    name: 'カナダ',
    flag: '🇨🇦',
    icon: <HomeOutlined style={{ fontSize: 24, color: '#eb2f96' }} />,
    description: '資源と安定した経済',
  },
  {
    code: 'switzerland',
    name: 'スイス',
    flag: '🇨🇭',
    icon: <FlagOutlined style={{ fontSize: 24, color: '#fa541c' }} />,
    description: '金融と精密産業の中心地',
  },
]

function CountryDataIndex() {
  return (
    <div style={{ padding: '24px' }}>
      <Title level={2} style={{ marginBottom: 8 }}>
        各国データ
      </Title>
      <Text type="secondary" style={{ fontSize: 16, marginBottom: 32, display: 'block' }}>
        主要国の経済指標とデータを国別に閲覧できます
      </Text>

      <Row gutter={[24, 24]} style={{ marginTop: 24 }}>
        {COUNTRIES.map((country) => (
          <Col xs={24} sm={12} md={8} lg={6} key={country.code}>
            <Link to={`/country/${country.code}`} style={{ textDecoration: 'none' }}>
              <Card
                hoverable
                style={{
                  borderRadius: 12,
                  border: '1px solid #f0f0f0',
                  height: '100%',
                  transition: 'all 0.3s ease',
                }}
                styles={{
                  body: { padding: 24, textAlign: 'center' },
                }}
              >
                <Space direction="vertical" size={16} style={{ width: '100%' }}>
                  <div style={{ fontSize: 48 }}>{country.flag}</div>
                  <div>{country.icon}</div>
                  <div>
                    <Title level={4} style={{ margin: 0, color: '#1a1a1a' }}>
                      {country.name}
                    </Title>
                    <Text
                      type="secondary"
                      style={{ fontSize: 14, marginTop: 8, display: 'block' }}
                    >
                      {country.description}
                    </Text>
                  </div>
                </Space>
              </Card>
            </Link>
          </Col>
        ))}
      </Row>
    </div>
  )
}

export default CountryDataIndex
