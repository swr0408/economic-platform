import { useParams, Link } from 'react-router-dom'
import { Card, Row, Col, Typography, Space, Button } from 'antd'
import {
  ArrowLeftOutlined,
  BankOutlined,
  DollarOutlined,
  TeamOutlined,
  RiseOutlined,
  HomeOutlined,
  ShoppingOutlined,
} from '@ant-design/icons'

const { Title, Text } = Typography

type DataCategory = {
  code: string
  name: string
  icon: React.ReactNode
  description: string
  color: string
}

const DATA_CATEGORIES: DataCategory[] = [
  {
    code: 'policy',
    name: '金融政策',
    icon: <BankOutlined style={{ fontSize: 28 }} />,
    description: '金融政策・政策金利・マネーサプライ・流動性',
    color: '#1890ff',
  },
  {
    code: 'economy',
    name: '経済',
    icon: <DollarOutlined style={{ fontSize: 28 }} />,
    description: 'GDP・景気指標・生産・貿易データ',
    color: '#52c41a',
  },
  {
    code: 'consumer',
    name: '消費',
    icon: <ShoppingOutlined style={{ fontSize: 28 }} />,
    description: '小売売上高・消費者信頼感・個人所得・個人支出',
    color: '#13c2c2',
  },
  {
    code: 'employment',
    name: '雇用',
    icon: <TeamOutlined style={{ fontSize: 28 }} />,
    description: '雇用統計・失業率・賃金データ',
    color: '#faad14',
  },
  {
    code: 'inflation',
    name: '物価',
    icon: <RiseOutlined style={{ fontSize: 28 }} />,
    description: '消費者物価・生産者物価・インフレ率',
    color: '#ff4d4f',
  },
  {
    code: 'housing',
    name: '住宅',
    icon: <HomeOutlined style={{ fontSize: 28 }} />,
    description: '住宅価格・建設許可・住宅販売',
    color: '#722ed1',
  },
]

const COUNTRY_INFO: Record<string, { name: string; isoCode: string; description: string }> = {
  usa: {
    name: 'アメリカ',
    isoCode: 'us',
    description: '世界最大の経済大国。ドルは基軸通貨として国際金融システムの中心的役割を担う。',
  },
  japan: {
    name: '日本',
    isoCode: 'jp',
    description:
      '世界第3位の経済大国。製造業と技術革新で知られ、アジア経済の重要な牽引役。',
  },
  eurozone: {
    name: 'ユーロ圏',
    isoCode: 'eu',
    description: '19か国で構成される統一通貨圏。世界第2位の経済規模を持つ統合経済圏。',
  },
  uk: {
    name: 'イギリス',
    isoCode: 'gb',
    description:
      'ロンドンは世界有数の金融センター。Brexit後も重要な経済・金融の拠点。',
  },
  china: {
    name: '中国',
    isoCode: 'cn',
    description: '世界第2位の経済大国。製造業の中心地として「世界の工場」と呼ばれる。',
  },
  australia: {
    name: 'オーストラリア',
    isoCode: 'au',
    description: '資源豊富な先進国。鉄鉱石や石炭などの資源輸出国として重要な地位。',
  },
  newzealand: {
    name: 'ニュージーランド',
    isoCode: 'nz',
    description: '農業と観光が主要産業。安定した民主主義と経済運営で知られる。',
  },
  canada: {
    name: 'カナダ',
    isoCode: 'ca',
    description: '豊富な天然資源を持つ先進国。石油・鉱物資源の主要輸出国。',
  },
  switzerland: {
    name: 'スイス',
    isoCode: 'ch',
    description: '国際金融の中心地。銀行業と精密機械工業で世界的に有名。',
  },
}

function CountryDetail() {
  const { countryCode } = useParams()

  if (!countryCode || !COUNTRY_INFO[countryCode]) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Text>国が見つかりませんでした。</Text>
        <br />
        <Link to="/country">
          <Button type="link" icon={<ArrowLeftOutlined />}>
            各国データ一覧へ戻る
          </Button>
        </Link>
      </div>
    )
  }

  const country = COUNTRY_INFO[countryCode]

  return (
    <div style={{ padding: '24px' }}>
      <Space style={{ marginBottom: 24 }}>
        <Link to="/country">
          <Button type="default" icon={<ArrowLeftOutlined />}>
            各国データ一覧へ戻る
          </Button>
        </Link>
      </Space>

      <div style={{ marginBottom: 32 }}>
        <Space size={16} align="center">
          <span
            className={`fi fi-${country.isoCode}`}
            style={{
              fontSize: 56,
              borderRadius: 4,
              boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
            }}
          />
          <div>
            <Title level={2} style={{ margin: 0 }}>
              {country.name}のデータ
            </Title>
            <Text type="secondary" style={{ fontSize: 16 }}>
              {country.description}
            </Text>
          </div>
        </Space>
      </div>

      <Title level={3} style={{ marginBottom: 24 }}>
        データカテゴリ
      </Title>

      <Row gutter={[24, 24]}>
        {DATA_CATEGORIES.map((category) => (
          <Col xs={24} sm={12} md={8} key={category.code}>
            <Link
              to={`/country/${countryCode}/${category.code}`}
              style={{ textDecoration: 'none' }}
            >
              <Card
                hoverable
                style={{
                  borderRadius: 12,
                  border: `2px solid ${category.color}20`,
                  height: '100%',
                  transition: 'all 0.3s ease',
                }}
                styles={{
                  body: { padding: 24 },
                }}
              >
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  <div
                    style={{
                      color: category.color,
                      background: `${category.color}10`,
                      width: 56,
                      height: 56,
                      borderRadius: 12,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {category.icon}
                  </div>
                  <div>
                    <Title level={4} style={{ margin: 0, color: '#1a1a1a' }}>
                      {category.name}
                    </Title>
                    <Text
                      type="secondary"
                      style={{ fontSize: 14, marginTop: 8, display: 'block' }}
                    >
                      {category.description}
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

export default CountryDetail
