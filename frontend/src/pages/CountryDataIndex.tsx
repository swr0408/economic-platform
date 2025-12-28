import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Card, Row, Col, Typography, Space, Button } from 'antd'
import { CalendarOutlined, MenuFoldOutlined } from '@ant-design/icons'
import EconomicCalendarWidgets from '../components/country/usa/EconomicCalendarWidgets'

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

// 右サイドバー（経済カレンダー）のデフォルト幅と範囲
const CALENDAR_SIDEBAR_DEFAULT_WIDTH = 350
const CALENDAR_SIDEBAR_MIN_WIDTH = 300
const CALENDAR_SIDEBAR_MAX_WIDTH = 800

function CountryDataIndex() {
  const [calendarOpen, setCalendarOpen] = useState(true)
  const [sidebarWidth, setSidebarWidth] = useState(CALENDAR_SIDEBAR_DEFAULT_WIDTH)
  const [isResizing, setIsResizing] = useState(false)

  // リサイズハンドラー
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsResizing(true)
  }, [])

  // マウス移動でサイドバー幅を変更
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return
      const newWidth = window.innerWidth - e.clientX
      if (newWidth >= CALENDAR_SIDEBAR_MIN_WIDTH && newWidth <= CALENDAR_SIDEBAR_MAX_WIDTH) {
        setSidebarWidth(newWidth)
      }
    }

    const handleMouseUp = () => {
      if (isResizing) {
        setIsResizing(false)
      }
    }

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
      document.body.style.userSelect = 'none'
      document.body.style.cursor = 'col-resize'
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.body.style.userSelect = ''
      document.body.style.cursor = ''
    }
  }, [isResizing])

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* メインコンテンツエリア */}
      <div
        style={{
          flex: 1,
          padding: '24px',
          marginRight: calendarOpen ? sidebarWidth : 0,
          transition: 'margin-right 0.3s ease',
        }}
      >
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

      {/* リサイズ中のオーバーレイ（iframeがマウスイベントを奪うのを防ぐ） */}
      {isResizing && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            zIndex: 9999,
            cursor: 'col-resize',
          }}
        />
      )}

      {/* 右サイドバー：経済カレンダー */}
      {calendarOpen && (
        <div
          style={{
            position: 'fixed',
            right: 0,
            top: 64,
            width: sidebarWidth,
            height: 'calc(100vh - 56px)',
            background: '#fff',
            borderLeft: '1px solid #f0f0f0',
            boxShadow: '-2px 0 8px rgba(0,0,0,0.1)',
            overflowY: 'auto',
            zIndex: 100,
          }}
        >
          {/* リサイズハンドル */}
          <div
            onMouseDown={handleMouseDown}
            style={{
              position: 'absolute',
              left: -3,
              top: 0,
              width: 8,
              height: '100%',
              cursor: 'col-resize',
              backgroundColor: isResizing ? '#1890ff' : 'transparent',
              transition: 'background-color 0.2s',
              zIndex: 101,
            }}
            onMouseEnter={(e) => {
              if (!isResizing) {
                e.currentTarget.style.backgroundColor = '#e6f7ff'
              }
            }}
            onMouseLeave={(e) => {
              if (!isResizing) {
                e.currentTarget.style.backgroundColor = 'transparent'
              }
            }}
          />
          <div style={{ padding: '16px' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 16,
                paddingBottom: 12,
                borderBottom: '1px solid #f0f0f0',
              }}
            >
              <Space>
                <CalendarOutlined style={{ fontSize: 18, color: '#1890ff' }} />
                <Text strong style={{ fontSize: 16 }}>
                  経済カレンダー
                </Text>
              </Space>
              <Button
                type="text"
                icon={<MenuFoldOutlined />}
                onClick={() => setCalendarOpen(false)}
                size="small"
              />
            </div>
            <EconomicCalendarWidgets countryCode="all" />
          </div>
        </div>
      )}

      {/* カレンダーが閉じている時の開くボタン */}
      {!calendarOpen && (
        <Button
          type="primary"
          icon={<CalendarOutlined />}
          style={{
            position: 'fixed',
            right: 16,
            top: 80,
            zIndex: 101,
          }}
          onClick={() => setCalendarOpen(true)}
        >
          カレンダー
        </Button>
      )}
    </div>
  )
}

export default CountryDataIndex
