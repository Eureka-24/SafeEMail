/** 协议类型定义 — 与 PROTOCOL.md 对齐 */

export interface ProtocolRequest {
  version: '1.0'
  type: 'REQUEST'
  action: string
  request_id: string
  token: string | null
  payload: Record<string, unknown>
}

export interface ProtocolResponse {
  version: '1.0'
  type: 'RESPONSE'
  request_id: string
  status: number
  message: string
  payload: Record<string, unknown>
}

/** 所有支持的 Action */
export type Action =
  // 认证类
  | 'REGISTER'
  | 'LOGIN'
  | 'LOGOUT'
  | 'REFRESH'
  // 邮件类
  | 'SEND_MAIL'
  | 'LIST_INBOX'
  | 'READ_MAIL'
  | 'LIST_SENT'
  | 'SAVE_DRAFT'
  | 'LIST_DRAFTS'
  | 'RECALL_MAIL'
  | 'SEARCH_MAIL'
  | 'QUICK_REPLY'
  // 群组类
  | 'CREATE_GROUP'
  | 'LIST_GROUPS'
  // 附件类
  | 'UPLOAD_ATTACH'
  | 'DOWNLOAD_ATTACH'
  // 快捷操作类
  | 'EXEC_ACTION'
  // 系统类
  | 'PING'

/** HTTP 风格状态码 */
export type StatusCode = 200 | 201 | 400 | 401 | 403 | 404 | 409 | 429 | 500
