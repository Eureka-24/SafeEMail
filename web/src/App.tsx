/** SafeEmail 主应用 — 路由配置 */
import { useEffect, type ReactNode } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { useAuthStore } from './stores/authStore'
import { useTokenAutoRefresh } from './hooks/useAuth'
import { AppLayout } from './components/Layout/AppLayout'
import LoginPage from './pages/LoginPage'
import InboxPage from './pages/InboxPage'
import SentPage from './pages/SentPage'
import DraftPage from './pages/DraftPage'
import MailDetailPage from './pages/MailDetailPage'
import ComposePage from './pages/ComposePage'
import SearchPage from './pages/SearchPage'
import GroupPage from './pages/GroupPage'

/** 登录守卫 */
function RequireAuth({ children }: { children: ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

/** Token 续期组件 */
function TokenRefresher() {
  useTokenAutoRefresh()
  return null
}

function App() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const init = useAuthStore((s) => s.init)

  // 应用启动时立即建立 WebSocket 连接（注册/登录都需要）
  useEffect(() => {
    init()
  }, [init])

  return (
    <ConfigProvider locale={zhCN}>
      <BrowserRouter>
        {isAuthenticated && <TokenRefresher />}
        <Routes>
          {/* 公开路由 */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<LoginPage />} />

          {/* 需登录路由 */}
          <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
            <Route path="/inbox" element={<InboxPage />} />
            <Route path="/sent" element={<SentPage />} />
            <Route path="/drafts" element={<DraftPage />} />
            <Route path="/mail/:id" element={<MailDetailPage />} />
            <Route path="/compose" element={<ComposePage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/groups" element={<GroupPage />} />
          </Route>

          {/* 默认重定向 */}
          <Route path="*" element={<Navigate to="/inbox" replace />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  )
}

export default App
