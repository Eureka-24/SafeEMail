/** 顶栏（搜索框/用户信息/登出） */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Layout, Input, Button, Space, Typography, Alert } from 'antd'
import { SearchOutlined, LogoutOutlined } from '@ant-design/icons'
import { useAuthStore } from '../../stores/authStore'
import { useUIStore } from '../../stores/uiStore'

const { Header: AntHeader } = Layout
const { Text } = Typography

export function Header() {
  const navigate = useNavigate()
  const username = useAuthStore((s) => s.username)
  const domain = useAuthStore((s) => s.domain)
  const logout = useAuthStore((s) => s.logout)
  const wsConnected = useAuthStore((s) => s.wsConnected)
  const wsReconnecting = useUIStore((s) => s.wsReconnecting)
  const [searchValue, setSearchValue] = useState('')

  const handleSearch = () => {
    const q = searchValue.trim()
    if (q) {
      navigate(`/search?q=${encodeURIComponent(q)}`)
    }
  }

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <>
      {/* 网络断开警告条 */}
      {!wsConnected && (
        <Alert
          message={wsReconnecting ? '网络连接已断开，正在重连...' : '网络连接已断开'}
          type="warning"
          banner
          showIcon
        />
      )}

      <AntHeader
        style={{
          background: '#fff',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid #f0f0f0',
        }}
      >
        {/* 搜索框 */}
        <Input
          placeholder="搜索邮件..."
          prefix={<SearchOutlined />}
          value={searchValue}
          onChange={(e) => setSearchValue(e.target.value)}
          onPressEnter={handleSearch}
          style={{ maxWidth: 400 }}
          allowClear
        />

        {/* 用户信息 + 登出 */}
        <Space>
          <Text>
            {username}@{domain}
          </Text>
          <Button
            type="text"
            icon={<LogoutOutlined />}
            onClick={handleLogout}
          >
            登出
          </Button>
        </Space>
      </AntHeader>
    </>
  )
}
