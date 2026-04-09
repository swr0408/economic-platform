import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Card, Row, Col, Typography, Space, Button, Tooltip } from 'antd'
import {
  CalendarOutlined,
  MenuFoldOutlined,
  GlobalOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons'
import EconomicCalendarWidgets from '../components/country/usa/EconomicCalendarWidgets'
import { useHandbook } from '../contexts/HandbookContext'

// データハンドブックのヘルプアイコン（タイトル横に複数表示）
const PAGE_HANDBOOKS: { id: string; tooltip: string }[] = [
  { id: 'fundamentals-overview', tooltip: 'ファンダメンタルズ概要 - データハンドブック' },
  { id: 'market-cycle', tooltip: '相場サイクル - データハンドブック' },
  { id: 'economic-cycle-assets', tooltip: '経済サイクルと主要資産の関係 - データハンドブック' },
  { id: 'business-cycle', tooltip: '景気サイクル - データハンドブック' },
]

const { Title, Text } = Typography

// EconAlpha カラーパレット
const colors = {
  bgPrimary: '#0f172a',
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  accent: '#10b981',
  accentHover: '#34d399',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textTertiary: '#64748b',
  border: '#334155',
}

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
  {
    code: 'global',
    isoCode: 'globe',
    name: 'グローバル',
    description: 'グローバル先行指標・韓国・台湾',
  },
]

// 右サイドバー（経済カレンダー）のデフォルト幅と範囲
const CALENDAR_SIDEBAR_DEFAULT_WIDTH = 380
const CALENDAR_SIDEBAR_MIN_WIDTH = 320
const CALENDAR_SIDEBAR_MAX_WIDTH = 600

function CountryDataIndex() {
  const [calendarOpen, setCalendarOpen] = useState(true)
  const [sidebarWidth, setSidebarWidth] = useState(CALENDAR_SIDEBAR_DEFAULT_WIDTH)
  const [isResizing, setIsResizing] = useState(false)
  const { openHandbook } = useHandbook()

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
    <div style={{ display: 'flex', minHeight: 'calc(100vh - 64px)' }}>
      {/* メインコンテンツエリア */}
      <div
        style={{
          flex: 1,
          padding: '20px 24px',
          marginRight: calendarOpen ? sidebarWidth : 0,
          transition: 'margin-right 0.3s ease',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <Title level={3} style={{ margin: 0, color: colors.textPrimary }}>
            マクロデータ
          </Title>
          {PAGE_HANDBOOKS.map((entry) => (
            <Tooltip key={entry.id} title={entry.tooltip}>
              <QuestionCircleOutlined
                onClick={() => openHandbook(entry.id)}
                style={{
                  fontSize: 18,
                  color: colors.textSecondary,
                  cursor: 'pointer',
                  transition: 'color 0.2s',
                }}
                onMouseEnter={(e) => {
                  ;(e.target as HTMLElement).style.color = '#10b981'
                }}
                onMouseLeave={(e) => {
                  ;(e.target as HTMLElement).style.color = colors.textSecondary
                }}
              />
            </Tooltip>
          ))}
        </div>
        <Text style={{ fontSize: 13, color: colors.textSecondary, marginBottom: 24, display: 'block' }}>
          主要国の経済指標とデータを国別に閲覧できます
        </Text>

        <Row gutter={[16, 16]} style={{ marginTop: 20 }}>
          {COUNTRIES.map((country) => (
            <Col xs={24} sm={12} md={8} lg={6} key={country.code}>
              <Link to={`/country/${country.code}`} style={{ textDecoration: 'none' }}>
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
                    body: { padding: 20, textAlign: 'center' },
                  }}
                >
                  <Space direction="vertical" size={10} style={{ width: '100%' }}>
                    {country.isoCode === 'globe' ? (
                      <GlobalOutlined style={{ fontSize: 40, color: colors.accent }} />
                    ) : (
                      <span
                        className={`fi fi-${country.isoCode}`}
                        style={{
                          fontSize: 40,
                          borderRadius: 4,
                          boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
                        }}
                      />
                    )}
                    <div>
                      <Title level={5} style={{ margin: 0, color: colors.textPrimary }}>
                        {country.name}
                      </Title>
                      <Text
                        style={{ fontSize: 12, marginTop: 4, display: 'block', color: colors.textSecondary }}
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
            height: 'calc(100vh - 64px)',
            background: colors.bgSecondary,
            borderLeft: `1px solid ${colors.border}`,
            boxShadow: '-4px 0 16px rgba(0,0,0,0.2)',
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
              backgroundColor: isResizing ? colors.accent : 'transparent',
              transition: 'background-color 0.2s',
              zIndex: 101,
            }}
            onMouseEnter={(e) => {
              if (!isResizing) {
                e.currentTarget.style.backgroundColor = colors.bgTertiary
              }
            }}
            onMouseLeave={(e) => {
              if (!isResizing) {
                e.currentTarget.style.backgroundColor = 'transparent'
              }
            }}
          />
          <div style={{ padding: '12px 16px' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 12,
                paddingBottom: 10,
                borderBottom: `1px solid ${colors.border}`,
              }}
            >
              <Space>
                <CalendarOutlined style={{ fontSize: 16, color: colors.accent }} />
                <Text strong style={{ fontSize: 14, color: colors.textPrimary }}>
                  経済カレンダー
                </Text>
              </Space>
              <Button
                type="text"
                icon={<MenuFoldOutlined style={{ color: colors.textSecondary }} />}
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
            background: colors.accent,
            borderColor: colors.accent,
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
