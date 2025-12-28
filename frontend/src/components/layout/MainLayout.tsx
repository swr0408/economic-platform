import { useMemo, useState, useCallback, useEffect, useRef } from 'react'
import { Layout, Menu } from 'antd'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import {
  HomeOutlined,
  LineChartOutlined,
  GlobalOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons'
import SidebarNavigation from './SidebarNavigation'

const { Header, Content, Sider } = Layout

// サイドバー幅の設定
const DEFAULT_SIDEBAR_WIDTH = 250
const MIN_SIDEBAR_WIDTH = 180
const MAX_SIDEBAR_WIDTH = 400
const STORAGE_KEY = 'sidebar-width'

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
      key: '/seasonality',
      icon: <LineChartOutlined />,
      label: 'シーズナリティ',
    },
    {
      key: '/country',
      icon: <GlobalOutlined />,
      label: '各国データ',
    },
  ]

  const selectedKey = useMemo(() => {
    const path = location.pathname
    if (path === '/') return '/'
    if (path.startsWith('/seasonality')) return '/seasonality'
    if (path.startsWith('/country')) return '/country'
    return path
  }, [location.pathname])

  const showSidebar = location.pathname.startsWith('/country')

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
          background: '#001529',
          padding: '0 24px',
        }}
      >
        <div
          style={{
            color: '#fff',
            fontSize: '20px',
            fontWeight: 'bold',
            marginRight: '48px',
            cursor: 'pointer',
          }}
          onClick={() => navigate('/')}
        >
          EconomicPlatform
        </div>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ flex: 1, minWidth: 0 }}
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
                background: '#fff',
                borderRight: '1px solid #f0f0f0',
                position: 'sticky',
                top: 0,
                height: 'calc(100vh - 64px)',
                overflow: 'auto',
              }}
            >
              <div
                style={{
                  padding: '16px',
                  borderBottom: '1px solid #f0f0f0',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                {!collapsed && (
                  <span style={{ fontWeight: 'bold', color: '#1890ff' }}>
                    各国データ
                  </span>
                )}
                <span
                  onClick={() => setCollapsed(!collapsed)}
                  style={{ cursor: 'pointer', fontSize: '16px' }}
                >
                  {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
                </span>
              </div>
              <SidebarNavigation />
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
                  backgroundColor: isResizing ? '#1890ff' : 'transparent',
                  transition: 'background-color 0.2s',
                  zIndex: 10,
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
            )}
          </div>
        )}
        <Content
          style={{
            padding: '24px',
            background: '#f5f5f5',
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
