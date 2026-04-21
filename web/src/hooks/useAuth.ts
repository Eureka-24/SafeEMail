/** 认证相关 Hook — Token 自动续期 */
import { useEffect, useRef } from 'react'
import { useAuthStore } from '../stores/authStore'
import { apiRefresh } from '../api/client'

/** 自动续期：过期前 2 分钟刷新 Token */
export function useTokenAutoRefresh() {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const accessToken = useAuthStore((s) => s.accessToken)
  const refreshToken = useAuthStore((s) => s.refreshToken)
  const setTokens = useAuthStore((s) => s.setTokens)
  const clearAuth = useAuthStore((s) => s.clearAuth)
  const parseTokenExp = useAuthStore((s) => s.parseTokenExp)

  useEffect(() => {
    if (!accessToken || !refreshToken) {
      if (timerRef.current) clearTimeout(timerRef.current)
      return
    }

    const exp = parseTokenExp()
    if (!exp) return

    const now = Math.floor(Date.now() / 1000)
    const timeUntilRefresh = (exp - now - 120) * 1000  // 过期前 2 分钟

    if (timeUntilRefresh <= 0) {
      // 已经需要续期
      doRefresh()
    } else {
      timerRef.current = setTimeout(doRefresh, timeUntilRefresh)
    }

    async function doRefresh() {
      try {
        const result = await apiRefresh(refreshToken!)
        setTokens(result.access_token)
      } catch {
        clearAuth()
      }
    }

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [accessToken, refreshToken, setTokens, clearAuth, parseTokenExp])
}
