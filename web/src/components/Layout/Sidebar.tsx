/** 侧边导航 */
import { useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu } from 'antd'
import {
  InboxOutlined,
  SendOutlined,
  FileTextOutlined,
  TeamOutlined,
  EditOutlined,
  MailOutlined,
} from '@ant-design/icons'
import { useUIStore } from '../../stores/uiStore'
import { config } from '../../config'

const { Sider } = Layout

const menuItems = [
  { key: '/inbox', icon: <InboxOutlined />, label: '收件箱' },
  { key: '/sent', icon: <SendOutlined />, label: '发件箱' },
  { key: '/drafts', icon: <FileTextOutlined />, label: '草稿箱' },
  { key: '/groups', icon: <TeamOutlined />, label: '群组' },
  { key: '/compose', icon: <EditOutlined />, label: '写邮件' },
]

export function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const collapsed = useUIStore((s) => s.sidebarCollapsed)

  const selectedKey = menuItems.find((item) =>
    location.pathname.startsWith(item.key),
  )?.key || '/inbox'

  return (
    <Sider
      collapsible
      collapsed={collapsed}
      onCollapse={() => useUIStore.getState().toggleSidebar()}
      theme="dark"
      width={200}
      style={{ minHeight: '100vh' }}
    >
      {/* Logo + 域名标识 */}
      <div
        style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
        }}
      >
        <MailOutlined style={{ fontSize: collapsed ? 24 : 20, color: '#1677ff' }} />
        {!collapsed && (
          <span style={{ color: '#fff', marginLeft: 8, fontSize: 14, fontWeight: 600 }}>
            {config.domain}
          </span>
        )}
      </div>

      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[selectedKey]}
        items={menuItems}
        onClick={({ key }) => navigate(key)}
        style={{ marginTop: 8 }}
      />
    </Sider>
  )
}
