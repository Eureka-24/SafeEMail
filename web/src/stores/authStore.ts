/** 认证状态管理 */
import { create } from 'zustand'
import { wsClient } from '../api/ws'
import { apiLogin, apiRegister, apiLogout, injectAuthMethods } from '../api/client'
import { config } from '../config'
import type { LoginPayload } from '../types/auth'

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  username: string | null
  domain: string | null
  userId: string | null
  isAuthenticated: boolean
  wsConnected: boolean

  init(): Promise<void>
  login(payload: LoginPayload): Promise<Record<string, unknown>>
  register(username: string, password: string): Promise<void>
  logout(): Promise<void>
  setTokens(access: string, refresh?: string): void
  clearAuth(): void
  setWsConnected(connected: boolean): void
  parseTokenExp(): number
}

/** 解析 JWT payload */
function decodeJwt(token: string): Record<string, unknown> {
  try {
    return JSON.parse(atob(token.split('.')[1]))
  } catch {
    return {}
  }
}

export const useAuthStore = create<AuthState>((set, get) => {
  // 注入 auth 方法到 client 层
  injectAuthMethods({
    getToken: () => get().accessToken,
    getRefreshToken: () => get().refreshToken,
    setTokens: (access, refresh) => get().setTokens(access, refresh),
    onAuthExpired: () => get().clearAuth(),
  })

  return {
    accessToken: null,
    refreshToken: null,
    username: null,
    domain: null,
    userId: null,
    isAuthenticated: false,
    wsConnected: false,

    async init() {
      // 建立 WebSocket 连接
      try {
        await wsClient.connect(config.wsUrl)
        set({ wsConnected: true })
      } catch {
        set({ wsConnected: false })
      }
      // 监听连接状态
      wsClient.onConnectionChange((connected) => {
        set({ wsConnected: connected })
      })
    },

    async login(payload: LoginPayload) {
      const result = await apiLogin(payload)
      const decoded = decodeJwt(result.access_token)
      set({
        accessToken: result.access_token,
        refreshToken: result.refresh_token,
        username: result.username || (decoded.username as string),
        domain: result.domain || (decoded.domain as string),
        userId: result.user_id || (decoded.sub as string),
        isAuthenticated: true,
      })
      return result as unknown as Record<string, unknown>
    },

    async register(username: string, password: string) {
      await apiRegister(username, password)
    },

    async logout() {
      try {
        await apiLogout()
      } catch {
        // 忽略登出错误
      }
      get().clearAuth()
    },

    setTokens(access: string, refresh?: string) {
      const update: Partial<AuthState> = { accessToken: access }
      if (refresh) update.refreshToken = refresh
      set(update)
    },

    clearAuth() {
      set({
        accessToken: null,
        refreshToken: null,
        username: null,
        domain: null,
        userId: null,
        isAuthenticated: false,
      })
    },

    setWsConnected(connected: boolean) {
      set({ wsConnected: connected })
    },

    parseTokenExp(): number {
      const token = get().accessToken
      if (!token) return 0
      const payload = decodeJwt(token)
      return (payload.exp as number) || 0
    },
  }
})
