import { useState, useEffect, useCallback } from 'react'
import { Card, Typography, Button, Row, Col, Space, Divider } from 'antd'
import {
  LineChartOutlined,
  GlobalOutlined,
  CalendarOutlined,
  MenuFoldOutlined,
  RiseOutlined,
  FallOutlined,
  StockOutlined,
  PercentageOutlined,
  ThunderboltOutlined,
  AreaChartOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import EconomicCalendarWidgets from '../components/country/usa/EconomicCalendarWidgets'

const { Title, Text } = Typography

// 右サイドバー（経済カレンダー）のデフォルト幅と範囲
const CALENDAR_SIDEBAR_DEFAULT_WIDTH = 380
const CALENDAR_SIDEBAR_MIN_WIDTH = 320
const CALENDAR_SIDEBAR_MAX_WIDTH = 600

// EconAlpha カラーパレット
const colors = {
  bgPrimary: '#0f172a',
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  accent: '#10b981',
  accentHover: '#34d399',
  accentMuted: 'rgba(16, 185, 129, 0.15)',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textTertiary: '#64748b',
  border: '#334155',
  success: '#10b981',
  error: '#ef4444',
  warning: '#f59e0b',
  info: '#3b82f6',
  gold: '#f59e0b',
}

// マーケットデータ（デモ用）
const marketData = [
  { symbol: 'S&P 500', value: '5,998.45', change: '+0.85%', positive: true },
  { symbol: 'NASDAQ', value: '19,234.12', change: '+1.12%', positive: true },
  { symbol: 'USD/JPY', value: '157.82', change: '-0.23%', positive: false },
  { symbol: 'EUR/USD', value: '1.0423', change: '+0.15%', positive: true },
  { symbol: 'US 10Y', value: '4.58%', change: '+0.02', positive: false },
  { symbol: 'Gold', value: '2,635.40', change: '+0.45%', positive: true },
]

// シーズナリティシグナル（デモ用）
const seasonalitySignals = [
  { asset: 'S&P 500', signal: '12月は歴史的に強気', trend: 'bullish', strength: 78 },
  { asset: 'Gold', signal: '年末にかけて上昇傾向', trend: 'bullish', strength: 65 },
  { asset: 'USD/JPY', signal: '1月は円高傾向', trend: 'bearish', strength: 72 },
]

// 注目経済指標（デモ用）
const upcomingEvents = [
  { time: '22:30', event: '米雇用統計', importance: 'high', country: 'us' },
  { time: '24:00', event: 'ISM製造業景況指数', importance: 'high', country: 'us' },
  { time: '08:50', event: '日銀短観', importance: 'medium', country: 'jp' },
]

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
    <div style={{ display: 'flex', minHeight: 'calc(100vh - 64px)' }}>
      {/* メインコンテンツエリア */}
      <div
        style={{
          flex: 1,
          maxWidth: calendarOpen ? `calc(100% - ${sidebarWidth}px)` : '100%',
          padding: '0',
          transition: 'max-width 0.3s ease',
          overflow: 'auto',
        }}
      >
        {/* マーケットティッカー */}
        <div
          style={{
            background: colors.bgSecondary,
            borderBottom: `1px solid ${colors.border}`,
            padding: '10px 16px',
            display: 'flex',
            gap: '24px',
            overflowX: 'auto',
          }}
        >
          {marketData.map((item) => (
            <div
              key={item.symbol}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                whiteSpace: 'nowrap',
              }}
            >
              <Text style={{ color: colors.textSecondary, fontSize: '12px' }}>
                {item.symbol}
              </Text>
              <Text
                strong
                style={{ color: colors.textPrimary, fontSize: '13px' }}
                className="tabular-nums"
              >
                {item.value}
              </Text>
              <Text
                style={{
                  color: item.positive ? colors.success : colors.error,
                  fontSize: '12px',
                }}
                className="tabular-nums"
              >
                {item.positive ? <RiseOutlined /> : <FallOutlined />} {item.change}
              </Text>
            </div>
          ))}
        </div>

        {/* ヘッダーセクション */}
        <div style={{ padding: '20px 24px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '4px' }}>
            <img
              src="/econAlpha_icon.svg"
              alt="EconAlpha"
              style={{
                width: '40px',
                height: '40px',
                borderRadius: '10px',
                boxShadow: '0 0 24px rgba(16, 185, 129, 0.4)',
              }}
            />
            <div>
              <Title
                level={3}
                style={{ margin: 0, color: colors.textPrimary, fontWeight: 600 }}
              >
                Econ<span style={{ color: colors.accent }}>Alpha</span>
              </Title>
              <Text style={{ color: colors.textSecondary, fontSize: '12px' }}>
                MARKET GEOMETRY
              </Text>
            </div>
          </div>
        </div>

        {/* メインダッシュボード */}
        <div style={{ padding: '0 24px 24px' }}>
          <Row gutter={[16, 16]}>
            {/* 左側: 機能カード */}
            <Col xs={24} lg={14}>
              <Row gutter={[16, 16]}>
                {/* シーズナリティ分析カード */}
                <Col xs={24} sm={12}>
                  <Card
                    hoverable
                    style={{
                      background: colors.bgSecondary,
                      border: `1px solid ${colors.border}`,
                      height: '100%',
                    }}
                    bodyStyle={{ padding: '16px' }}
                    onClick={() => navigate('/seasonality')}
                  >
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                      <div
                        style={{
                          width: '44px',
                          height: '44px',
                          background: colors.accentMuted,
                          borderRadius: '10px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                        }}
                      >
                        <LineChartOutlined style={{ fontSize: '22px', color: colors.accent }} />
                      </div>
                      <div style={{ flex: 1 }}>
                        <Text strong style={{ color: colors.textPrimary, fontSize: '15px' }}>
                          シーズナリティ分析
                        </Text>
                        <Text
                          style={{
                            color: colors.textSecondary,
                            fontSize: '12px',
                            display: 'block',
                            marginTop: '4px',
                          }}
                        >
                          金利・株式・商品・為替の季節性パターンを分析
                        </Text>
                      </div>
                    </div>
                  </Card>
                </Col>

                {/* マクロデータカード */}
                <Col xs={24} sm={12}>
                  <Card
                    hoverable
                    style={{
                      background: colors.bgSecondary,
                      border: `1px solid ${colors.border}`,
                      height: '100%',
                    }}
                    bodyStyle={{ padding: '16px' }}
                    onClick={() => navigate('/country')}
                  >
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                      <div
                        style={{
                          width: '44px',
                          height: '44px',
                          background: 'rgba(59, 130, 246, 0.15)',
                          borderRadius: '10px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                        }}
                      >
                        <GlobalOutlined style={{ fontSize: '22px', color: colors.info }} />
                      </div>
                      <div style={{ flex: 1 }}>
                        <Text strong style={{ color: colors.textPrimary, fontSize: '15px' }}>
                          マクロデータ
                        </Text>
                        <Text
                          style={{
                            color: colors.textSecondary,
                            fontSize: '12px',
                            display: 'block',
                            marginTop: '4px',
                          }}
                        >
                          主要各国の経済指標をリアルタイムで分析
                        </Text>
                      </div>
                    </div>
                  </Card>
                </Col>

                {/* マーケットデータカード */}
                <Col xs={24} sm={12}>
                  <Card
                    hoverable
                    style={{
                      background: colors.bgSecondary,
                      border: `1px solid ${colors.border}`,
                      height: '100%',
                    }}
                    bodyStyle={{ padding: '16px' }}
                    onClick={() => navigate('/markets')}
                  >
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                      <div
                        style={{
                          width: '44px',
                          height: '44px',
                          background: 'rgba(16, 185, 129, 0.15)',
                          borderRadius: '10px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                        }}
                      >
                        <StockOutlined style={{ fontSize: '22px', color: colors.accent }} />
                      </div>
                      <div style={{ flex: 1 }}>
                        <Text strong style={{ color: colors.textPrimary, fontSize: '15px' }}>
                          マーケットデータ
                        </Text>
                        <Text
                          style={{
                            color: colors.textSecondary,
                            fontSize: '12px',
                            display: 'block',
                            marginTop: '4px',
                          }}
                        >
                          株式・コモディティ・エネルギー市場の分析
                        </Text>
                      </div>
                    </div>
                  </Card>
                </Col>

                {/* データ比較カード */}
                <Col xs={24} sm={12}>
                  <Card
                    hoverable
                    style={{
                      background: colors.bgSecondary,
                      border: `1px solid ${colors.border}`,
                      height: '100%',
                    }}
                    bodyStyle={{ padding: '16px' }}
                    onClick={() => window.open('/compare', '_blank')}
                  >
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                      <div
                        style={{
                          width: '44px',
                          height: '44px',
                          background: 'rgba(245, 158, 11, 0.15)',
                          borderRadius: '10px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                        }}
                      >
                        <AreaChartOutlined style={{ fontSize: '22px', color: colors.gold }} />
                      </div>
                      <div style={{ flex: 1 }}>
                        <Text strong style={{ color: colors.textPrimary, fontSize: '15px' }}>
                          データ比較
                        </Text>
                        <Text
                          style={{
                            color: colors.textSecondary,
                            fontSize: '12px',
                            display: 'block',
                            marginTop: '4px',
                          }}
                        >
                          複数の経済指標を重ねて相関を分析
                        </Text>
                      </div>
                    </div>
                  </Card>
                </Col>

                {/* シーズナリティシグナル */}
                <Col xs={24}>
                  <Card
                    style={{
                      background: colors.bgSecondary,
                      border: `1px solid ${colors.border}`,
                    }}
                    bodyStyle={{ padding: '16px' }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        marginBottom: '12px',
                      }}
                    >
                      <Space>
                        <ThunderboltOutlined style={{ color: colors.gold }} />
                        <Text strong style={{ color: colors.textPrimary, fontSize: '14px' }}>
                          シーズナリティシグナル
                        </Text>
                      </Space>
                      <Text style={{ color: colors.textTertiary, fontSize: '11px' }}>
                        過去20年データに基づく
                      </Text>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {seasonalitySignals.map((item, index) => (
                        <div
                          key={index}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '10px 12px',
                            background: colors.bgTertiary,
                            borderRadius: '8px',
                            borderLeft: `3px solid ${
                              item.trend === 'bullish' ? colors.success : colors.error
                            }`,
                          }}
                        >
                          <div>
                            <Text
                              strong
                              style={{ color: colors.textPrimary, fontSize: '13px' }}
                            >
                              {item.asset}
                            </Text>
                            <Text
                              style={{
                                color: colors.textSecondary,
                                fontSize: '12px',
                                marginLeft: '12px',
                              }}
                            >
                              {item.signal}
                            </Text>
                          </div>
                          <div
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px',
                            }}
                          >
                            <div
                              style={{
                                width: '60px',
                                height: '4px',
                                background: colors.bgPrimary,
                                borderRadius: '2px',
                                overflow: 'hidden',
                              }}
                            >
                              <div
                                style={{
                                  width: `${item.strength}%`,
                                  height: '100%',
                                  background:
                                    item.trend === 'bullish' ? colors.success : colors.error,
                                }}
                              />
                            </div>
                            <Text
                              style={{
                                color:
                                  item.trend === 'bullish' ? colors.success : colors.error,
                                fontSize: '12px',
                                fontWeight: 600,
                              }}
                              className="tabular-nums"
                            >
                              {item.strength}%
                            </Text>
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>
                </Col>
              </Row>
            </Col>

            {/* 右側: 本日の注目イベント */}
            <Col xs={24} lg={10}>
              <Card
                style={{
                  background: colors.bgSecondary,
                  border: `1px solid ${colors.border}`,
                  height: '100%',
                }}
                bodyStyle={{ padding: '16px' }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '16px',
                  }}
                >
                  <Space>
                    <CalendarOutlined style={{ color: colors.accent }} />
                    <Text strong style={{ color: colors.textPrimary, fontSize: '14px' }}>
                      本日の注目イベント
                    </Text>
                  </Space>
                  <Button
                    type="link"
                    size="small"
                    style={{ color: colors.accent, padding: 0 }}
                    onClick={() => navigate('/country/usa/economy')}
                  >
                    すべて見る
                  </Button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {upcomingEvents.map((event, index) => (
                    <div
                      key={index}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                        padding: '10px 12px',
                        background: colors.bgTertiary,
                        borderRadius: '8px',
                      }}
                    >
                      <span
                        className={`fi fi-${event.country}`}
                        style={{ fontSize: '16px', borderRadius: '2px' }}
                      />
                      <Text
                        style={{ color: colors.textSecondary, fontSize: '12px', width: '45px' }}
                        className="tabular-nums"
                      >
                        {event.time}
                      </Text>
                      <Text style={{ color: colors.textPrimary, fontSize: '13px', flex: 1 }}>
                        {event.event}
                      </Text>
                      <div
                        style={{
                          width: '8px',
                          height: '8px',
                          borderRadius: '50%',
                          background:
                            event.importance === 'high' ? colors.error : colors.warning,
                        }}
                      />
                    </div>
                  ))}
                </div>

                <Divider style={{ margin: '16px 0', borderColor: colors.border }} />

                {/* クイック統計 */}
                <Row gutter={[12, 12]}>
                  <Col span={8}>
                    <div style={{ textAlign: 'center' }}>
                      <StockOutlined style={{ fontSize: '20px', color: colors.accent }} />
                      <div style={{ marginTop: '4px' }}>
                        <Text
                          style={{ color: colors.textPrimary, fontSize: '18px', fontWeight: 600 }}
                          className="tabular-nums"
                        >
                          156
                        </Text>
                      </div>
                      <Text style={{ color: colors.textTertiary, fontSize: '11px' }}>
                        資産分析
                      </Text>
                    </div>
                  </Col>
                  <Col span={8}>
                    <div style={{ textAlign: 'center' }}>
                      <GlobalOutlined style={{ fontSize: '20px', color: colors.info }} />
                      <div style={{ marginTop: '4px' }}>
                        <Text
                          style={{ color: colors.textPrimary, fontSize: '18px', fontWeight: 600 }}
                          className="tabular-nums"
                        >
                          9
                        </Text>
                      </div>
                      <Text style={{ color: colors.textTertiary, fontSize: '11px' }}>
                        対象国
                      </Text>
                    </div>
                  </Col>
                  <Col span={8}>
                    <div style={{ textAlign: 'center' }}>
                      <PercentageOutlined style={{ fontSize: '20px', color: colors.gold }} />
                      <div style={{ marginTop: '4px' }}>
                        <Text
                          style={{ color: colors.textPrimary, fontSize: '18px', fontWeight: 600 }}
                          className="tabular-nums"
                        >
                          80+
                        </Text>
                      </div>
                      <Text style={{ color: colors.textTertiary, fontSize: '11px' }}>
                        経済指標
                      </Text>
                    </div>
                  </Col>
                </Row>
              </Card>
            </Col>
          </Row>
        </div>
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

export default HomePage
