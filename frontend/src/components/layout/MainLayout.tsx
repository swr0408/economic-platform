import { useMemo, useState, useCallback, useEffect, useRef } from 'react'
import { Layout, Menu, Space } from 'antd'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import {
  HomeOutlined,
  LineChartOutlined,
  GlobalOutlined,
  AreaChartOutlined,
  StockOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons'
import SidebarNavigation from './SidebarNavigation'
import MarketSidebarNavigation from './MarketSidebarNavigation'

const { Header, Content, Sider } = Layout

// サイドバー幅の設定
const DEFAULT_SIDEBAR_WIDTH = 250
const MIN_SIDEBAR_WIDTH = 180
const MAX_SIDEBAR_WIDTH = 400
const STORAGE_KEY = 'sidebar-width'

// EconAlpha カラーパレット
const colors = {
  bgPrimary: '#0f172a',
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  accent: '#10b981',
  accentHover: '#34d399',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  border: '#334155',
}

function MainLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)

  // サイドバー幅をlocalStorageから復元、なければデフォルト
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const width = parseInt(saved, 10)
      if (!isNaN(width) && width >= MIN_SIDEBAR_WIDTH && width <= MAX_SIDEBAR_WIDTH) {
        return width
      }
    }
    return DEFAULT_SIDEBAR_WIDTH
  })

  const [isResizing, setIsResizing] = useState(false)
  const siderRef = useRef<HTMLDivElement>(null)

  const menuItems = [
    {
      key: '/',
      icon: <HomeOutlined />,
      label: 'ホーム',
    },
    {
      key: '/country',
      icon: <GlobalOutlined />,
      label: 'マクロデータ',
    },
    {
      key: '/markets',
      icon: <StockOutlined />,
      label: 'マーケットデータ',
    },
    {
      key: '/compare',
      icon: <AreaChartOutlined />,
      label: 'データ比較',
    },
    {
      key: '/seasonality',
      icon: <LineChartOutlined />,
      label: 'シーズナリティ',
    },
  ]

  const selectedKey = useMemo(() => {
    const path = location.pathname
    if (path === '/') return '/'
    if (path.startsWith('/seasonality')) return '/seasonality'
    if (path.startsWith('/country')) return '/country'
    if (path.startsWith('/markets')) return '/markets'
    if (path.startsWith('/compare')) return '/compare'
    return path
  }, [location.pathname])

  const showSidebar = location.pathname.startsWith('/country') || location.pathname.startsWith('/markets')

  // リサイズハンドラー
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsResizing(true)
  }, [])

  // マウス移動でサイドバー幅を変更
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return

      const newWidth = e.clientX
      if (newWidth >= MIN_SIDEBAR_WIDTH && newWidth <= MAX_SIDEBAR_WIDTH) {
        setSidebarWidth(newWidth)
      }
    }

    const handleMouseUp = () => {
      if (isResizing) {
        setIsResizing(false)
        // localStorageに保存
        localStorage.setItem(STORAGE_KEY, sidebarWidth.toString())
      }
    }

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
      // リサイズ中はテキスト選択を無効化
      document.body.style.userSelect = 'none'
      document.body.style.cursor = 'col-resize'
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.body.style.userSelect = ''
      document.body.style.cursor = ''
    }
  }, [isResizing, sidebarWidth])

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          background: colors.bgPrimary,
          padding: '0 24px',
          borderBottom: `1px solid ${colors.border}`,
        }}
      >
        {/* EconAlpha Logo */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            marginRight: '48px',
            cursor: 'pointer',
          }}
          onClick={() => navigate('/')}
        >
          <Space size={8} align="center" style={{ display: 'flex', alignItems: 'center' }}>
            {/* EconAlpha Icon */}
            <img
              src="/econAlpha_icon.svg"
              alt="EconAlpha"
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '8px',
                display: 'block',
                verticalAlign: 'middle',
              }}
            />
            <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.2, justifyContent: 'center' }}>
              <span
                style={{
                  color: colors.textPrimary,
                  fontSize: '18px',
                  fontWeight: 600,
                  letterSpacing: '0.5px',
                }}
              >
                Econ<span style={{ color: colors.accent }}>Alpha</span>
              </span>
              <span
                style={{
                  color: colors.textSecondary,
                  fontSize: '10px',
                  fontWeight: 400,
                  letterSpacing: '1px',
                  textTransform: 'uppercase',
                }}
              >
                Seasonal Analytics
              </span>
            </div>
          </Space>
        </div>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{
            flex: 1,
            minWidth: 0,
            background: 'transparent',
            borderBottom: 'none',
          }}
        />
      </Header>
      <Layout style={{ marginTop: 64 }}>
        {showSidebar && (
          <div
            ref={siderRef}
            style={{
              position: 'relative',
              display: 'flex',
            }}
          >
            <Sider
              width={collapsed ? 80 : sidebarWidth}
              collapsible
              collapsed={collapsed}
              onCollapse={(value) => setCollapsed(value)}
              trigger={null}
              style={{
                background: colors.bgSecondary,
                borderRight: `1px solid ${colors.border}`,
                position: 'sticky',
                top: 64,
                height: 'calc(100vh - 64px)',
                overflow: 'auto',
              }}
            >
              <div
                style={{
                  padding: '12px 16px',
                  borderBottom: `1px solid ${colors.border}`,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  background: colors.bgTertiary,
                }}
              >
                {!collapsed && (
                  <span style={{ fontWeight: 600, color: colors.accent, fontSize: '13px' }}>
                    {location.pathname.startsWith('/markets') ? 'マーケットデータ' : 'マクロデータ'}
                  </span>
                )}
                <span
                  onClick={() => setCollapsed(!collapsed)}
                  style={{ cursor: 'pointer', fontSize: '16px', color: colors.textSecondary }}
                >
                  {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
                </span>
              </div>
              {location.pathname.startsWith('/markets') ? <MarketSidebarNavigation /> : <SidebarNavigation />}
            </Sider>
            {/* リサイズハンドル */}
            {!collapsed && (
              <div
                onMouseDown={handleMouseDown}
                style={{
                  position: 'absolute',
                  right: 0,
                  top: 0,
                  bottom: 0,
                  width: 4,
                  cursor: 'col-resize',
                  backgroundColor: isResizing ? colors.accent : 'transparent',
                  transition: 'background-color 0.2s',
                  zIndex: 10,
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
            )}
          </div>
        )}
        <Content
          style={{
            padding: '16px',
            background: colors.bgPrimary,
            overflow: 'auto',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}

export default MainLayout
