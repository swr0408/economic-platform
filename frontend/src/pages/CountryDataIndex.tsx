import { Link } from 'react-router-dom'
import { Card, Row, Col, Typography, Space } from 'antd'

const { Title, Text } = Typography

type Country = {
  code: string
  isoCode: string
  name: string
  description: string
}

const COUNTRIES: Country[] = [
  {
    code: 'usa',
    isoCode: 'us',
    name: 'アメリカ',
    description: '世界最大の経済大国',
  },
  {
    code: 'japan',
    isoCode: 'jp',
    name: '日本',
    description: '技術革新と製造業の中心地',
  },
  {
    code: 'eurozone',
    isoCode: 'eu',
    name: 'ユーロ圏',
    description: '統合された欧州経済圏',
  },
  {
    code: 'uk',
    isoCode: 'gb',
    name: 'イギリス',
    description: '金融サービスの国際的中心地',
  },
  {
    code: 'china',
    isoCode: 'cn',
    name: '中国',
    description: '世界第2位の経済大国',
  },
  {
    code: 'australia',
    isoCode: 'au',
    name: 'オーストラリア',
    description: '資源豊富な先進国',
  },
  {
    code: 'newzealand',
    isoCode: 'nz',
    name: 'ニュージーランド',
    description: '農業と観光の島国',
  },
  {
    code: 'canada',
    isoCode: 'ca',
    name: 'カナダ',
    description: '資源と安定した経済',
  },
  {
    code: 'switzerland',
    isoCode: 'ch',
    name: 'スイス',
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
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  <span
                    className={`fi fi-${country.isoCode}`}
                    style={{
                      fontSize: 48,
                      borderRadius: 4,
                      boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                    }}
                  />
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
