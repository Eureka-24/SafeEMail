/** UI 状态管理 */
import { create } from 'zustand'

interface UIState {
  sidebarCollapsed: boolean
  loading: boolean
  wsConnected: boolean
  wsReconnecting: boolean

  toggleSidebar(): void
  setLoading(val: boolean): void
  setWsStatus(connected: boolean, reconnecting?: boolean): void
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  loading: false,
  wsConnected: false,
  wsReconnecting: false,

  toggleSidebar() {
    set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed }))
  },

  setLoading(val: boolean) {
    set({ loading: val })
  },

  setWsStatus(connected: boolean, reconnecting = false) {
    set({ wsConnected: connected, wsReconnecting: reconnecting })
  },
}))
