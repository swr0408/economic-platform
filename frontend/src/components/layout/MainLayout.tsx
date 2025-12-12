import { Layout, Menu } from 'antd'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { HomeOutlined, LineChartOutlined, GlobalOutlined } from '@ant-design/icons'

const { Header, Content } = Layout

function MainLayout() {
  const navigate = useNavigate()
  const location = useLocation()

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
      key: '/country-data',
      icon: <GlobalOutlined />,
      label: '各国データ',
    },
  ]

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
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ flex: 1, minWidth: 0 }}
        />
      </Header>
      <Content style={{ padding: '24px', background: '#f5f5f5' }}>
        <Outlet />
      </Content>
    </Layout>
  )
}

export default MainLayout
