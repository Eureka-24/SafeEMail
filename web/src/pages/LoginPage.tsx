/** 登录/注册页面 — Tab 切换 */
import { useState } from 'react'
import { Card, Tabs, Typography } from 'antd'
import { MailOutlined } from '@ant-design/icons'
import { Navigate, useLocation } from 'react-router-dom'
import { LoginForm } from '../components/Auth/LoginForm'
import { RegisterForm } from '../components/Auth/RegisterForm'
import { useAuthStore } from '../stores/authStore'
import { config } from '../config'

const { Title, Text } = Typography

export default function LoginPage() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const location = useLocation()
  const isRegisterRoute = location.pathname === '/register'
  const [activeTab, setActiveTab] = useState(isRegisterRoute ? 'register' : 'login')

  // 已登录用户重定向到收件箱
  if (isAuthenticated) {
    return <Navigate to="/inbox" replace />
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      }}
    >
      <Card
        style={{ width: 420, boxShadow: '0 8px 32px rgba(0, 0, 0, 0.15)' }}
        bordered={false}
      >
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <MailOutlined style={{ fontSize: 48, color: '#1677ff' }} />
          <Title level={3} style={{ marginTop: 12, marginBottom: 4 }}>
            SafeEmail
          </Title>
          <Text type="secondary">{config.domain} 邮箱</Text>
        </div>

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          centered
          items={[
            {
              key: 'login',
              label: '登录',
              children: <LoginForm />,
            },
            {
              key: 'register',
              label: '注册',
              children: <RegisterForm onSuccess={() => setActiveTab('login')} />,
            },
          ]}
        />
      </Card>
    </div>
  )
}
