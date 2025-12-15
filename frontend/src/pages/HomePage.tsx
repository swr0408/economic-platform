import { Card, Typography, Button, Row, Col } from 'antd'
import { LineChartOutlined, GlobalOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'

const { Title, Paragraph } = Typography

function HomePage() {
  const navigate = useNavigate()

  return (
    <div
      style={{
        maxWidth: '1200px',
        margin: '0 auto',
        padding: '48px 24px',
      }}
    >
      <div style={{ textAlign: 'center', marginBottom: '48px' }}>
        <Title level={1} style={{ marginBottom: '16px' }}>
          EconomicPlatform
        </Title>
        <Paragraph
          style={{
            fontSize: '16px',
            color: '#666',
          }}
        >
          金融市場の季節性分析とマクロ経済データを可視化するダッシュボードです
        </Paragraph>
      </div>

      <Row gutter={[24, 24]} justify="center">
        <Col xs={24} sm={12} md={10} lg={8}>
          <Card
            hoverable
            style={{
              textAlign: 'center',
              height: '100%',
            }}
          >
            <div
              style={{
                width: '80px',
                height: '80px',
                margin: '0 auto 24px',
                background: '#e6f7ff',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <LineChartOutlined style={{ fontSize: '36px', color: '#1890ff' }} />
            </div>
            <Title level={4}>シーズナリティ分析</Title>
            <Paragraph style={{ color: '#666', marginBottom: '24px' }}>
              金利・株式・商品・為替の季節性パターンを分析
            </Paragraph>
            <Button type="primary" onClick={() => navigate('/seasonality')}>
              分析を開始
            </Button>
          </Card>
        </Col>

        <Col xs={24} sm={12} md={10} lg={8}>
          <Card
            hoverable
            style={{
              textAlign: 'center',
              height: '100%',
            }}
          >
            <div
              style={{
                width: '80px',
                height: '80px',
                margin: '0 auto 24px',
                background: '#e6f7ff',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <GlobalOutlined style={{ fontSize: '36px', color: '#1890ff' }} />
            </div>
            <Title level={4}>各国データ</Title>
            <Paragraph style={{ color: '#666', marginBottom: '24px' }}>
              主要各国の経済データを分析
            </Paragraph>
            <Button type="primary" onClick={() => navigate('/country')}>
              分析を開始
            </Button>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default HomePage
