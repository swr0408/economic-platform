import { useEffect, useState, useCallback } from 'react'
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
  CalendarOutlined,
  MenuFoldOutlined,
} from '@ant-design/icons'
import USAPolicyCharts from '../components/country/usa/USAPolicyCharts'
import USAEconomyCharts from '../components/country/usa/USAEconomyCharts'
import USAConsumerCharts from '../components/country/usa/USAConsumerCharts'
import USAEmploymentCharts from '../components/country/usa/USAEmploymentCharts'
import USAInflationCharts from '../components/country/usa/USAInflationCharts'
import EconomicCalendarWidgets from '../components/country/usa/EconomicCalendarWidgets'
import { COUNTRIES_DATA, type IndicatorItem } from '../constants/countryData'

const { Title, Text } = Typography

// EconAlpha ダークテーマカラー
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

type Indicator = IndicatorItem

const COUNTRY_INFO: Record<string, { name: string; isoCode: string }> = Object.fromEntries(
  COUNTRIES_DATA.map((country) => [
    country.code,
    { name: country.name, isoCode: country.isoCode },
  ])
)

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
const INDICATORS_BY_COUNTRY_CATEGORY = COUNTRIES_DATA.reduce<
  Record<string, Record<string, Indicator[]>>
>((acc, country) => {
  acc[country.code] = country.categories.reduce<Record<string, Indicator[]>>(
    (categoryAcc, category) => {
      categoryAcc[category.code] = category.indicators
      return categoryAcc
    },
    {}
  )
  return acc
}, {})

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

// 右サイドバー（経済カレンダー）のデフォルト幅と範囲
const CALENDAR_SIDEBAR_DEFAULT_WIDTH = 500
const CALENDAR_SIDEBAR_MIN_WIDTH = 300
const CALENDAR_SIDEBAR_MAX_WIDTH = 800

function CountryDataCategory() {
  const { countryCode, categoryCode } = useParams()
  const location = useLocation()
  const [calendarOpen, setCalendarOpen] = useState(true)
  const [sidebarWidth, setSidebarWidth] = useState(CALENDAR_SIDEBAR_DEFAULT_WIDTH)
  const [isResizing, setIsResizing] = useState(false)

  // リサイズハンドラー（左サイドバーと同じ方式）
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

  // 全ての国でカレンダーを表示
  const showCalendar = !!countryCode && !!COUNTRY_INFO[countryCode]

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

  // USA金融政策・経済・消費・雇用・物価の場合はチャートを表示
  const isUSAPolicy = countryCode === 'usa' && categoryCode === 'policy'
  const isUSAEconomy = countryCode === 'usa' && categoryCode === 'economy'
  const isUSAConsumer = countryCode === 'usa' && categoryCode === 'consumer'
  const isUSAEmployment = countryCode === 'usa' && categoryCode === 'employment'
  const isUSAInflation = countryCode === 'usa' && categoryCode === 'inflation'

  // メインコンテンツ
  const mainContent = (
    <>
      {isUSAPolicy ? (
        <USAPolicyCharts />
      ) : isUSAEconomy ? (
        <USAEconomyCharts />
      ) : isUSAConsumer ? (
        <USAConsumerCharts />
      ) : isUSAEmployment ? (
        <USAEmploymentCharts />
      ) : isUSAInflation ? (
        <USAInflationCharts />
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
    </>
  )

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* メインコンテンツエリア */}
      <div
        style={{
          flex: 1,
          padding: '24px',
          marginRight: showCalendar && calendarOpen ? sidebarWidth : 0,
          transition: 'margin-right 0.3s ease',
        }}
      >
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

        {mainContent}
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
      {showCalendar && calendarOpen && (
        <div
          style={{
            position: 'fixed',
            right: 0,
            top: 64, // ヘッダーの高さ分オフセット
            width: sidebarWidth,
            height: 'calc(100vh - 56px)',
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
          <div style={{ padding: '16px' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 16,
                paddingBottom: 12,
                borderBottom: `1px solid ${colors.border}`,
              }}
            >
              <Space>
                <CalendarOutlined style={{ fontSize: 18, color: colors.accent }} />
                <Text strong style={{ fontSize: 16, color: colors.textPrimary }}>
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
            <EconomicCalendarWidgets countryCode={countryCode} />
          </div>
        </div>
      )}

      {/* カレンダーが閉じている時の開くボタン */}
      {showCalendar && !calendarOpen && (
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

export default CountryDataCategory
