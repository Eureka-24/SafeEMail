/** 高层 API 封装 — 业务级请求方法 */
import { wsClient } from './ws'
import type { ProtocolResponse } from '../types/protocol'
import type { LoginPayload, LoginResponse, RefreshResponse, RegisterResponse } from '../types/auth'
import type { MailListResponse, MailDetail, DraftPayload, SearchResult, Group, Attachment } from '../types/mail'

/** 获取当前 token（由 authStore 注入） */
let getToken: () => string | null = () => null
let getRefreshToken: () => string | null = () => null
let setTokens: (access: string, refresh?: string) => void = () => {}
let onAuthExpired: () => void = () => {}

/** 由 authStore 初始化时注入 */
export function injectAuthMethods(methods: {
  getToken: () => string | null
  getRefreshToken: () => string | null
  setTokens: (access: string, refresh?: string) => void
  onAuthExpired: () => void
}) {
  getToken = methods.getToken
  getRefreshToken = methods.getRefreshToken
  setTokens = methods.setTokens
  onAuthExpired = methods.onAuthExpired
}

/** 解析 JWT payload 获取 exp */
function parseJwtExp(token: string): number {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.exp as number
  } catch {
    return 0
  }
}

/** Token 续期拦截：过期前 2 分钟自动 REFRESH */
async function ensureValidToken(): Promise<string | null> {
  const token = getToken()
  if (!token) return null

  const exp = parseJwtExp(token)
  const now = Math.floor(Date.now() / 1000)

  // 过期前 2 分钟续期
  if (exp - now < 120) {
    const refreshToken = getRefreshToken()
    if (!refreshToken) {
      onAuthExpired()
      return null
    }
    try {
      const resp = await wsClient.send('REFRESH', { refresh_token: refreshToken })
      if (resp.status === 200) {
        const data = resp.payload as unknown as RefreshResponse
        setTokens(data.access_token)
        return data.access_token
      } else {
        onAuthExpired()
        return null
      }
    } catch {
      onAuthExpired()
      return null
    }
  }

  return token
}

/** 带 Token 续期拦截的请求方法 */
async function authenticatedSend(
  action: Parameters<typeof wsClient.send>[0],
  payload: Record<string, unknown> = {},
): Promise<ProtocolResponse> {
  const token = await ensureValidToken()
  if (!token) throw new Error('未登录')
  return wsClient.send(action, payload, token)
}

// ── 认证 API ──

export async function apiLogin(payload: LoginPayload): Promise<LoginResponse> {
  const resp = await wsClient.send('LOGIN', payload as unknown as Record<string, unknown>)
  if (resp.status !== 200) {
    throw Object.assign(new Error(resp.message), { status: resp.status, payload: resp.payload })
  }
  return resp.payload as unknown as LoginResponse
}

export async function apiRegister(username: string, password: string): Promise<RegisterResponse> {
  const resp = await wsClient.send('REGISTER', { username, password })
  if (resp.status !== 201 && resp.status !== 200) {
    throw Object.assign(new Error(resp.message), { status: resp.status, payload: resp.payload })
  }
  return resp.payload as unknown as RegisterResponse
}

export async function apiLogout(): Promise<void> {
  const token = getToken()
  await wsClient.send('LOGOUT', {}, token)
}

export async function apiRefresh(refreshToken: string): Promise<RefreshResponse> {
  const resp = await wsClient.send('REFRESH', { refresh_token: refreshToken })
  if (resp.status !== 200) {
    throw Object.assign(new Error(resp.message), { status: resp.status })
  }
  return resp.payload as unknown as RefreshResponse
}

// ── 邮件 API ──

export async function apiListInbox(page = 1, pageSize = 20): Promise<MailListResponse> {
  const resp = await authenticatedSend('LIST_INBOX', { page, page_size: pageSize })
  if (resp.status !== 200) throw new Error(resp.message)
  return resp.payload as unknown as MailListResponse
}

export async function apiListSent(page = 1, pageSize = 20): Promise<MailListResponse> {
  const resp = await authenticatedSend('LIST_SENT', { page, page_size: pageSize })
  if (resp.status !== 200) throw new Error(resp.message)
  return resp.payload as unknown as MailListResponse
}

export async function apiListDrafts(): Promise<MailListResponse> {
  const resp = await authenticatedSend('LIST_DRAFTS', {})
  if (resp.status !== 200) throw new Error(resp.message)
  return resp.payload as unknown as MailListResponse
}

export async function apiReadMail(emailId: string): Promise<MailDetail> {
  const resp = await authenticatedSend('READ_MAIL', { email_id: emailId })
  if (resp.status !== 200) throw new Error(resp.message)
  return resp.payload as unknown as MailDetail
}

export async function apiSendMail(
  to: string[], subject: string, body: string, attachmentIds?: string[],
): Promise<ProtocolResponse> {
  const payload: Record<string, unknown> = { to, subject, body }
  if (attachmentIds?.length) payload.attachment_ids = attachmentIds
  const resp = await authenticatedSend('SEND_MAIL', payload)
  if (resp.status !== 200 && resp.status !== 201) {
    throw Object.assign(new Error(resp.message), { status: resp.status, payload: resp.payload })
  }
  return resp
}

export async function apiSaveDraft(draft: DraftPayload): Promise<ProtocolResponse> {
  const resp = await authenticatedSend('SAVE_DRAFT', draft as unknown as Record<string, unknown>)
  if (resp.status !== 200 && resp.status !== 201) throw new Error(resp.message)
  return resp
}

export async function apiRecallMail(emailId: string, signature: string): Promise<ProtocolResponse> {
  const resp = await authenticatedSend('RECALL_MAIL', { email_id: emailId, signature })
  if (resp.status !== 200) {
    throw Object.assign(new Error(resp.message), { status: resp.status, payload: resp.payload })
  }
  return resp
}

export async function apiSearchMail(query: string, limit = 20): Promise<SearchResult[]> {
  const resp = await authenticatedSend('SEARCH_MAIL', { query, limit })
  if (resp.status !== 200) throw new Error(resp.message)
  return (resp.payload as unknown as { results: SearchResult[] }).results
}

export async function apiQuickReply(emailId: string): Promise<string[]> {
  const resp = await authenticatedSend('QUICK_REPLY', { email_id: emailId })
  if (resp.status !== 200) throw new Error(resp.message)
  return (resp.payload as unknown as { suggestions: string[] }).suggestions
}

// ── 群组 API ──

export async function apiCreateGroup(groupName: string, members: string[]): Promise<ProtocolResponse> {
  const resp = await authenticatedSend('CREATE_GROUP', { group_name: groupName, members })
  if (resp.status !== 200 && resp.status !== 201) throw new Error(resp.message)
  return resp
}

export async function apiListGroups(): Promise<Group[]> {
  const resp = await authenticatedSend('LIST_GROUPS', {})
  if (resp.status !== 200) throw new Error(resp.message)
  return (resp.payload as unknown as { groups: Group[] }).groups
}

// ── 附件 API ──

export async function apiUploadAttach(
  emailId: string, filename: string, contentType: string, data: string,
): Promise<Attachment> {
  const resp = await authenticatedSend('UPLOAD_ATTACH', {
    email_id: emailId, filename, content_type: contentType, data,
  })
  if (resp.status !== 200 && resp.status !== 201) throw new Error(resp.message)
  return resp.payload as unknown as Attachment
}

export async function apiDownloadAttach(attachmentId: string): Promise<Attachment> {
  const resp = await authenticatedSend('DOWNLOAD_ATTACH', { attachment_id: attachmentId })
  if (resp.status !== 200) throw new Error(resp.message)
  return resp.payload as unknown as Attachment
}

// ── 快捷操作 API ──

export async function apiExecAction(
  emailId: string, actionIndex: number, confirm?: boolean,
): Promise<ProtocolResponse> {
  const payload: Record<string, unknown> = { email_id: emailId, action_index: actionIndex }
  if (confirm !== undefined) payload.confirm = confirm
  const resp = await authenticatedSend('EXEC_ACTION', payload)
  if (resp.status !== 200) {
    throw Object.assign(new Error(resp.message), { status: resp.status, payload: resp.payload })
  }
  return resp
}
