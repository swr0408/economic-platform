import { useMemo, useState } from 'react'
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

function MainLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)

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

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header
        style={{
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
      <Layout>
        {showSidebar && (
          <Sider
            width={250}
            collapsible
            collapsed={collapsed}
            onCollapse={(value) => setCollapsed(value)}
            trigger={null}
            style={{
              background: '#fff',
              borderRight: '1px solid #f0f0f0',
              position: 'sticky',
              top: 64,
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
