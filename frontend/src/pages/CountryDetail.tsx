import { useParams, Link, Navigate } from 'react-router-dom'
import { Card, Row, Col, Typography, Space, Button } from 'antd'
import {
  ArrowLeftOutlined,
  BankOutlined,
  DollarOutlined,
  TeamOutlined,
  RiseOutlined,
  HomeOutlined,
  ShoppingOutlined,
  GlobalOutlined,
} from '@ant-design/icons'

const { Title, Text } = Typography

// EconAlpha カラーパレット
const colors = {
  bgPrimary: '#0f172a',
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  accent: '#10b981',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  border: '#334155',
}

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
    color: '#3b82f6',
  },
  {
    code: 'economy',
    name: '経済',
    icon: <DollarOutlined style={{ fontSize: 28 }} />,
    description: 'GDP・景気指標・生産・貿易データ',
    color: '#10b981',
  },
  {
    code: 'consumer',
    name: '消費',
    icon: <ShoppingOutlined style={{ fontSize: 28 }} />,
    description: '小売売上高・消費者信頼感・個人所得・個人支出',
    color: '#06b6d4',
  },
  {
    code: 'employment',
    name: '雇用',
    icon: <TeamOutlined style={{ fontSize: 28 }} />,
    description: '雇用統計・失業率・賃金データ',
    color: '#f59e0b',
  },
  {
    code: 'inflation',
    name: '物価',
    icon: <RiseOutlined style={{ fontSize: 28 }} />,
    description: '消費者物価・生産者物価・インフレ率',
    color: '#ef4444',
  },
  {
    code: 'housing',
    name: '住宅',
    icon: <HomeOutlined style={{ fontSize: 28 }} />,
    description: '住宅価格・建設許可・住宅販売',
    color: '#a855f7',
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
  global: {
    name: 'グローバル',
    isoCode: 'globe',
    description: 'グローバル先行指標・韓国・台湾。世界経済の方向性を示す主要指標。',
  },
}

function CountryDetail() {
  const { countryCode } = useParams()

  if (!countryCode || !COUNTRY_INFO[countryCode]) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Text style={{ color: colors.textSecondary }}>国が見つかりませんでした。</Text>
        <br />
        <Link to="/country">
          <Button type="link" icon={<ArrowLeftOutlined />} style={{ color: colors.accent }}>
            マクロデータ一覧へ戻る
          </Button>
        </Link>
      </div>
    )
  }

  // グローバルはカテゴリが1つだけなので直接チャートページへ
  if (countryCode === 'global') {
    return <Navigate to="/country/global/economy" replace />
  }

  const country = COUNTRY_INFO[countryCode]

  return (
    <div style={{ padding: '20px 24px' }}>
      <Space style={{ marginBottom: 20 }}>
        <Link to="/country">
          <Button
            type="default"
            icon={<ArrowLeftOutlined />}
            style={{
              background: colors.bgSecondary,
              borderColor: colors.border,
              color: colors.textSecondary,
            }}
          >
            マクロデータ一覧へ戻る
          </Button>
        </Link>
      </Space>

      <div style={{ marginBottom: 28 }}>
        <Space size={16} align="center">
          {country.isoCode === 'globe' ? (
            <GlobalOutlined style={{ fontSize: 48, color: '#10b981' }} />
          ) : (
            <span
              className={`fi fi-${country.isoCode}`}
              style={{
                fontSize: 48,
                borderRadius: 4,
                boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
              }}
            />
          )}
          <div>
            <Title level={3} style={{ margin: 0, color: colors.textPrimary }}>
              {country.name}のデータ
            </Title>
            <Text style={{ fontSize: 14, color: colors.textSecondary }}>
              {country.description}
            </Text>
          </div>
        </Space>
      </div>

      <Title level={4} style={{ marginBottom: 20, color: colors.textPrimary }}>
        データカテゴリ
      </Title>

      <Row gutter={[16, 16]}>
        {DATA_CATEGORIES.map((category) => (
          <Col xs={24} sm={12} md={8} key={category.code}>
            <Link
              to={`/country/${countryCode}/${category.code}`}
              style={{ textDecoration: 'none' }}
            >
              <Card
                hoverable
                style={{
                  borderRadius: 10,
                  border: `1px solid ${colors.border}`,
                  background: colors.bgSecondary,
                  height: '100%',
                  transition: 'all 0.2s ease',
                }}
                styles={{
                  body: { padding: 20 },
                }}
              >
                <Space direction="vertical" size={10} style={{ width: '100%' }}>
                  <div
                    style={{
                      color: category.color,
                      background: `${category.color}15`,
                      width: 48,
                      height: 48,
                      borderRadius: 10,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {category.icon}
                  </div>
                  <div>
                    <Title level={5} style={{ margin: 0, color: colors.textPrimary }}>
                      {category.name}
                    </Title>
                    <Text
                      style={{ fontSize: 13, marginTop: 6, display: 'block', color: colors.textSecondary }}
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
