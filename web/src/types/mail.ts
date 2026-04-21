/** 邮件/附件/群组相关类型 */

export interface Mail {
  email_id: string
  from_user: string
  to_users: string[]
  subject: string
  body: string
  status: 'SENT' | 'DRAFT' | 'RECALLED'
  category?: string
  keywords?: string[]
  actions?: MailAction[]
  created_at: string
  sent_at?: string
  is_read: boolean
  is_spam: boolean | number
  spam_score?: number
  recall_signature?: string
}

export interface MailDetail extends Mail {
  attachments?: Attachment[]
}

export interface Attachment {
  attachment_id: string
  filename: string
  content_type: string
  file_size: number
  data?: string  // Base64，仅下载时填充
}

export interface MailAction {
  type: 'schedule' | 'confirm' | 'reject' | 'safe_link' | 'summary'
  label: string
  data?: Record<string, unknown>
  signature?: string
}

export interface SearchResult {
  email_id: string
  from_user: string
  subject: string
  sent_at: string
  match_type: string
  score: number
}

export interface DraftPayload {
  draft_id?: string
  to_users: string[]
  subject: string
  body: string
}

export interface Group {
  group_id: string
  group_name: string
  members: string[]
  owner_id: string
}

export interface MailListResponse {
  emails: Mail[]
  total: number
  page: number
  page_size: number
}
