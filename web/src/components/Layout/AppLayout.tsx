/** 整体布局（侧边栏 + 顶栏 + 内容区） */
import { Outlet } from 'react-router-dom'
import { Layout } from 'antd'
import { Sidebar } from './Sidebar'
import { Header } from './Header'

const { Content } = Layout

export function AppLayout() {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sidebar />
      <Layout>
        <Header />
        <Content style={{ margin: 16, padding: 24, background: '#fff', borderRadius: 8, overflow: 'auto' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
