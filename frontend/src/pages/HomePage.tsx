import { useState, useEffect, useCallback } from 'react'
import { Card, Typography, Button, Row, Col, Space } from 'antd'
import { LineChartOutlined, GlobalOutlined, CalendarOutlined, MenuFoldOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import EconomicCalendarWidgets from '../components/country/usa/EconomicCalendarWidgets'

const { Title, Paragraph, Text } = Typography

// 右サイドバー（経済カレンダー）のデフォルト幅と範囲
const CALENDAR_SIDEBAR_DEFAULT_WIDTH = 350
const CALENDAR_SIDEBAR_MIN_WIDTH = 300
const CALENDAR_SIDEBAR_MAX_WIDTH = 800

function HomePage() {
  const navigate = useNavigate()
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
          maxWidth: calendarOpen ? `calc(100% - ${sidebarWidth}px)` : '100%',
          margin: '0 auto',
          padding: '48px 24px',
          transition: 'max-width 0.3s ease',
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

export default HomePage
