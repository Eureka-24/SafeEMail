/** 邮件状态管理 */
import { create } from 'zustand'
import {
  apiListInbox, apiListSent, apiListDrafts,
  apiReadMail, apiSendMail, apiSaveDraft,
  apiRecallMail, apiSearchMail, apiQuickReply,
  apiExecAction,
} from '../api/client'
import type { Mail, MailDetail, SearchResult, DraftPayload } from '../types/mail'
import type { ProtocolResponse } from '../types/protocol'

interface MailState {
  inboxMails: Mail[]
  sentMails: Mail[]
  drafts: Mail[]
  currentMail: MailDetail | null
  searchResults: SearchResult[]
  inboxPage: number
  inboxTotal: number
  sentPage: number
  sentTotal: number
  pageSize: number
  loading: boolean

  fetchInbox(page?: number): Promise<void>
  fetchSent(page?: number): Promise<void>
  fetchDrafts(): Promise<void>
  readMail(emailId: string): Promise<void>
  sendMail(to: string[], subject: string, body: string, attachmentIds?: string[]): Promise<ProtocolResponse>
  saveDraft(draft: DraftPayload): Promise<ProtocolResponse>
  recallMail(emailId: string, signature: string): Promise<ProtocolResponse>
  searchMail(query: string): Promise<void>
  getQuickReplies(emailId: string): Promise<string[]>
  execAction(emailId: string, actionIndex: number, confirm?: boolean): Promise<ProtocolResponse>
  clearCurrentMail(): void
}

export const useMailStore = create<MailState>((set, get) => ({
  inboxMails: [],
  sentMails: [],
  drafts: [],
  currentMail: null,
  searchResults: [],
  inboxPage: 1,
  inboxTotal: 0,
  sentPage: 1,
  sentTotal: 0,
  pageSize: 20,
  loading: false,

  async fetchInbox(page = 1) {
    set({ loading: true })
    try {
      const data = await apiListInbox(page, get().pageSize)
      set({
        inboxMails: data.emails,
        inboxPage: data.page,
        inboxTotal: data.total,
      })
    } finally {
      set({ loading: false })
    }
  },

  async fetchSent(page = 1) {
    set({ loading: true })
    try {
      const data = await apiListSent(page, get().pageSize)
      set({
        sentMails: data.emails,
        sentPage: data.page,
        sentTotal: data.total,
      })
    } finally {
      set({ loading: false })
    }
  },

  async fetchDrafts() {
    set({ loading: true })
    try {
      const data = await apiListDrafts()
      set({ drafts: data.emails })
    } finally {
      set({ loading: false })
    }
  },

  async readMail(emailId: string) {
    set({ loading: true })
    try {
      const mail = await apiReadMail(emailId)
      set({ currentMail: mail })
    } finally {
      set({ loading: false })
    }
  },

  async sendMail(to, subject, body, attachmentIds) {
    return apiSendMail(to, subject, body, attachmentIds)
  },

  async saveDraft(draft) {
    return apiSaveDraft(draft)
  },

  async recallMail(emailId, signature) {
    return apiRecallMail(emailId, signature)
  },

  async searchMail(query) {
    set({ loading: true })
    try {
      const results = await apiSearchMail(query)
      set({ searchResults: results })
    } finally {
      set({ loading: false })
    }
  },

  async getQuickReplies(emailId) {
    return apiQuickReply(emailId)
  },

  async execAction(emailId, actionIndex, confirm) {
    return apiExecAction(emailId, actionIndex, confirm)
  },

  clearCurrentMail() {
    set({ currentMail: null })
  },
}))
