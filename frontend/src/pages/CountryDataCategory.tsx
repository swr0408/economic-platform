import { useEffect } from 'react'
import { useParams, Link, useLocation } from 'react-router-dom'
import { Card, Typography, Space, Button, Empty } from 'antd'
import {
  ArrowLeftOutlined,
  BankOutlined,
  DollarOutlined,
  TeamOutlined,
  RiseOutlined,
  HomeOutlined,
  ShoppingOutlined,
  BarChartOutlined,
} from '@ant-design/icons'
import USAPolicyCharts from '../components/country/usa/USAPolicyCharts'
import USAEconomyCharts from '../components/country/usa/USAEconomyCharts'
import USAConsumerCharts from '../components/country/usa/USAConsumerCharts'
import USAEmploymentCharts from '../components/country/usa/USAEmploymentCharts'

const { Title, Text } = Typography

const COUNTRY_INFO: Record<string, { name: string; isoCode: string }> = {
  usa: { name: 'アメリカ', isoCode: 'us' },
  japan: { name: '日本', isoCode: 'jp' },
  eurozone: { name: 'ユーロ圏', isoCode: 'eu' },
  uk: { name: 'イギリス', isoCode: 'gb' },
  china: { name: '中国', isoCode: 'cn' },
  australia: { name: 'オーストラリア', isoCode: 'au' },
  newzealand: { name: 'ニュージーランド', isoCode: 'nz' },
  canada: { name: 'カナダ', isoCode: 'ca' },
  switzerland: { name: 'スイス', isoCode: 'ch' },
}

type Indicator = {
  code: string
  name: string
}

const CATEGORY_INFO: Record<
  string,
  { name: string; icon: React.ReactNode; color: string; description: string }
> = {
  policy: {
    name: '金融政策',
    icon: <BankOutlined />,
    color: '#1890ff',
    description: '金融政策・政策金利・マネーサプライ・流動性',
  },
  economy: {
    name: '経済',
    icon: <DollarOutlined />,
    color: '#52c41a',
    description: 'GDP・景気指標・生産・貿易データ',
  },
  consumer: {
    name: '消費',
    icon: <ShoppingOutlined />,
    color: '#13c2c2',
    description: '小売売上高・消費者信頼感・個人所得・個人支出',
  },
  employment: {
    name: '雇用',
    icon: <TeamOutlined />,
    color: '#faad14',
    description: '雇用統計・失業率・賃金データ',
  },
  inflation: {
    name: '物価',
    icon: <RiseOutlined />,
    color: '#ff4d4f',
    description: '消費者物価・生産者物価・インフレ率',
  },
  housing: {
    name: '住宅',
    icon: <HomeOutlined />,
    color: '#722ed1',
    description: '住宅価格・建設許可・住宅販売',
  },
}

// 各国・カテゴリごとの経済指標リスト
const INDICATORS_BY_COUNTRY_CATEGORY: Record<string, Record<string, Indicator[]>> = {
  usa: {
    policy: [
      { code: 'policy-rate', name: '政策金利' },
      { code: 'fed-watch', name: 'Fed Watch' },
      { code: 'term-premium', name: 'タームプレミアム' },
      { code: 'dot-plot', name: 'Dot Plot' },
      { code: 'fomc-projections', name: 'FOMC経済見通し' },
    ],
    economy: [
      { code: 'gdp-growth', name: 'GDP成長率（前期比年率）' },
      { code: 'pmi', name: 'PMI' },
      { code: 'trade-balance', name: '貿易収支' },
    ],
    consumer: [
      { code: 'retail-sales', name: '小売売上高' },
      { code: 'consumer-confidence', name: '消費者信頼感' },
      { code: 'personal-income', name: '個人所得' },
    ],
    employment: [
      { code: 'nfp', name: '非農業部門雇用者数' },
      { code: 'unemployment', name: '失業率' },
      { code: 'jobless-claims', name: '新規失業保険申請件数' },
    ],
    inflation: [
      { code: 'cpi', name: 'CPI' },
      { code: 'pce', name: 'PCE' },
      { code: 'ppi', name: 'PPI' },
    ],
    housing: [
      { code: 'housing-starts', name: '住宅着工件数' },
      { code: 'existing-home-sales', name: '中古住宅販売' },
      { code: 'new-home-sales', name: '新築住宅販売' },
    ],
  },
  japan: {
    policy: [
      { code: 'policy-rate', name: '政策金利' },
      { code: 'boj-statement', name: '日銀声明' },
      { code: 'tankan', name: '短観' },
    ],
    economy: [
      { code: 'gdp', name: 'GDP' },
      { code: 'pmi', name: 'PMI' },
      { code: 'trade-balance', name: '貿易収支' },
    ],
    consumer: [
      { code: 'retail-sales', name: '小売売上高' },
      { code: 'consumer-confidence', name: '消費者信頼感' },
    ],
    employment: [
      { code: 'unemployment', name: '失業率' },
      { code: 'job-offers', name: '有効求人倍率' },
    ],
    inflation: [
      { code: 'cpi', name: 'CPI' },
      { code: 'cgpi', name: 'CGPI' },
    ],
    housing: [
      { code: 'housing-starts', name: '住宅着工件数' },
    ],
  },
}

// 準備中の指標用プレースホルダー
function IndicatorPlaceholder({ indicator }: { indicator: Indicator }) {
  return (
    <Card
      id={indicator.code}
      style={{
        marginBottom: 24,
        borderRadius: 12,
        scrollMarginTop: 24,
      }}
    >
      <Title level={4} style={{ marginBottom: 16 }}>
        {indicator.name}
      </Title>
      <Empty
        image={
          <BarChartOutlined
            style={{ fontSize: 48, color: '#d9d9d9' }}
          />
        }
        description={
          <Text type="secondary">
            データは準備中です
          </Text>
        }
      />
    </Card>
  )
}

function CountryDataCategory() {
  const { countryCode, categoryCode } = useParams()
  const location = useLocation()

  // ハッシュがある場合はスクロール
  useEffect(() => {
    if (location.hash) {
      const id = location.hash.replace('#', '')
      setTimeout(() => {
        const element = document.getElementById(id)
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }
      }, 100)
    }
  }, [location.hash])

  if (
    !countryCode ||
    !categoryCode ||
    !COUNTRY_INFO[countryCode] ||
    !CATEGORY_INFO[categoryCode]
  ) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Text>ページが見つかりませんでした。</Text>
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
  const category = CATEGORY_INFO[categoryCode]
  const indicators = INDICATORS_BY_COUNTRY_CATEGORY[countryCode]?.[categoryCode] || []

  // USA金融政策・経済・消費・雇用の場合はチャートを表示
  const isUSAPolicy = countryCode === 'usa' && categoryCode === 'policy'
  const isUSAEconomy = countryCode === 'usa' && categoryCode === 'economy'
  const isUSAConsumer = countryCode === 'usa' && categoryCode === 'consumer'
  const isUSAEmployment = countryCode === 'usa' && categoryCode === 'employment'

  return (
    <div style={{ padding: '24px' }}>
      <Space style={{ marginBottom: 24 }} wrap>
        <Link to="/country">
          <Button type="default" icon={<ArrowLeftOutlined />}>
            各国データ一覧
          </Button>
        </Link>
        <Link to={`/country/${countryCode}`}>
          <Button type="default">{country.name}データ一覧</Button>
        </Link>
      </Space>

      <div style={{ marginBottom: 32 }}>
        <Space size={16} align="center">
          <span
            className={`fi fi-${country.isoCode}`}
            style={{
              fontSize: 48,
              borderRadius: 4,
              boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
            }}
          />
          <div
            style={{
              color: category.color,
              fontSize: 32,
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
            <Title level={2} style={{ margin: 0 }}>
              {country.name} - {category.name}
            </Title>
            <Text type="secondary" style={{ fontSize: 16 }}>
              {category.description}
            </Text>
          </div>
        </Space>
      </div>

      {isUSAPolicy ? (
        <USAPolicyCharts />
      ) : isUSAEconomy ? (
        <USAEconomyCharts />
      ) : isUSAConsumer ? (
        <USAConsumerCharts />
      ) : isUSAEmployment ? (
        <USAEmploymentCharts />
      ) : indicators.length > 0 ? (
        <div>
          {indicators.map((indicator) => (
            <IndicatorPlaceholder key={indicator.code} indicator={indicator} />
          ))}
        </div>
      ) : (
        <Card
          style={{
            textAlign: 'center',
            minHeight: 400,
            borderRadius: 12,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Empty
            image={
              <BarChartOutlined
                style={{ fontSize: 80, color: '#d9d9d9', marginBottom: 16 }}
              />
            }
            description={
              <div>
                <Text type="secondary" style={{ fontSize: 18, display: 'block' }}>
                  {country.name}の{category.name}データは準備中です
                </Text>
                <Text
                  type="secondary"
                  style={{ fontSize: 14, display: 'block', marginTop: 8 }}
                >
                  近日中に公開予定です
                </Text>
              </div>
            }
          />
        </Card>
      )}
    </div>
  )
}

export default CountryDataCategory
