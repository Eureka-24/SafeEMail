/** 环境配置 — 读取 Vite 环境变量 */
export const config = {
  wsUrl: import.meta.env.VITE_WS_URL as string || 'ws://localhost:3001',
  domain: import.meta.env.VITE_DOMAIN as string || 'alpha.local',
  appTitle: import.meta.env.VITE_APP_TITLE as string || 'SafeEmail',
} as const
