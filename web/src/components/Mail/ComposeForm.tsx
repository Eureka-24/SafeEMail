/** 写邮件/回复/转发表单组件 */
import { useEffect, useRef, useCallback, useState } from 'react'
import { Form, Input, Button, Space, message, Select, Modal } from 'antd'
import { SendOutlined, SaveOutlined, TeamOutlined } from '@ant-design/icons'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import LinkExt from '@tiptap/extension-link'
import DOMPurify from 'dompurify'
import { apiSendMail, apiSaveDraft } from '../../api/client'
import { GroupSelector } from '../Group/GroupSelector'
import type { DraftPayload, MailDetail } from '../../types/mail'

interface ComposeFormProps {
  /** 编辑草稿时传入 */
  draft?: MailDetail | null
  /** 回复时传入原始邮件 */
  replyTo?: MailDetail | null
  /** 转发时传入原始邮件 */
  forwardFrom?: MailDetail | null
  /** 发送/保存成功后的回调 */
  onSuccess?: () => void
}

interface FormValues {
  to: string[]
  subject: string
}

const AUTOSAVE_INTERVAL = 30_000 // 30 秒自动保存

export function ComposeForm({ draft, replyTo, forwardFrom, onSuccess }: ComposeFormProps) {
  const [form] = Form.useForm<FormValues>()
  const draftIdRef = useRef<string | undefined>(draft?.email_id)
  const autoSaveTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const sendingRef = useRef(false)
  const [groupSelectorOpen, setGroupSelectorOpen] = useState(false)

  // TipTap 编辑器
  const editor = useEditor({
    extensions: [StarterKit, Underline, LinkExt.configure({ openOnClick: false })],
    content: '',
  })

  // 初始化表单
  useEffect(() => {
    if (draft) {
      form.setFieldsValue({
        to: Array.isArray(draft.to_users) ? draft.to_users : [],
        subject: draft.subject || '',
      })
      editor?.commands.setContent(draft.body || '')
      draftIdRef.current = draft.email_id
    } else if (replyTo) {
      const replyAddr = replyTo.from_user
      form.setFieldsValue({
        to: replyAddr ? [replyAddr] : [],
        subject: `Re: ${replyTo.subject || ''}`,
      })
      editor?.commands.setContent(
        `<br/><blockquote><p>${DOMPurify.sanitize(replyTo.body || '')}</p></blockquote>`,
      )
    } else if (forwardFrom) {
      form.setFieldsValue({
        to: [],
        subject: `Fwd: ${forwardFrom.subject || ''}`,
      })
      editor?.commands.setContent(
        `<br/><p>---------- 转发邮件 ----------</p>${DOMPurify.sanitize(forwardFrom.body || '')}`,
      )
    }
  }, [draft, replyTo, forwardFrom, form, editor])

  // 自动保存草稿
  const saveDraft = useCallback(async () => {
    if (sendingRef.current) return
    const values = form.getFieldsValue()
    const html = editor?.getHTML() || ''
    const payload: DraftPayload = {
      to_users: values.to || [],
      subject: values.subject || '',
      body: html,
      draft_id: draftIdRef.current,
    }
    try {
      const res = await apiSaveDraft(payload)
      const emailId = (res?.payload as Record<string, unknown>)?.email_id
      if (typeof emailId === 'string') {
        draftIdRef.current = emailId
      }
    } catch {
      // 自动保存失败静默忽略
    }
  }, [form, editor])

  useEffect(() => {
    autoSaveTimerRef.current = setInterval(saveDraft, AUTOSAVE_INTERVAL)
    return () => {
      if (autoSaveTimerRef.current) clearInterval(autoSaveTimerRef.current)
    }
  }, [saveDraft])

  // 发送
  const handleSend = async () => {
    try {
      const values = await form.validateFields()
      sendingRef.current = true
      if (autoSaveTimerRef.current) clearInterval(autoSaveTimerRef.current)
      const html = DOMPurify.sanitize(editor?.getHTML() || '')
      await apiSendMail(values.to, values.subject, html)
      message.success('邮件已发送')
      onSuccess?.()
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'errorFields' in err) return // 表单校验未通过
      const errObj = err as { status?: number; payload?: Record<string, unknown>; message?: string }
      if (errObj.status === 429) {
        message.error('发送过于频繁，请稍后再试')
      } else if (errObj.payload?.spam_warning) {
        Modal.warning({
          title: '垃圾邮件警告',
          content: `此邮件被检测为可疑内容：${(errObj.payload.spam_reasons as string[])?.join(', ') || '未知原因'}`
        })
      } else {
        message.error(errObj.message || '发送失败，请重试')
      }
    } finally {
      sendingRef.current = false
    }
  }

  // 手动保存草稿
  const handleSaveDraft = async () => {
    await saveDraft()
    message.success('草稿已保存')
  }

  return (
    <Form form={form} layout="vertical" style={{ maxWidth: 800 }}>
      <Form.Item
        name="to"
        label={
          <span>
            收件人
            <Button
              type="link"
              size="small"
              icon={<TeamOutlined />}
              onClick={() => setGroupSelectorOpen(true)}
              style={{ marginLeft: 8 }}
            >
              从群组选择
            </Button>
          </span>
        }
        rules={[{ required: true, message: '请输入收件人' }]}
      >
        <Select
          mode="tags"
          placeholder="输入邮箱地址，按回车添加"
          tokenSeparators={[',', ';', ' ']}
          style={{ width: '100%' }}
        />
      </Form.Item>

      <Form.Item
        name="subject"
        label="主题"
        rules={[{ required: true, message: '请输入主题' }]}
      >
        <Input placeholder="邮件主题" />
      </Form.Item>

      {/* TipTap 编辑器 */}
      <Form.Item label="正文">
        <div
          style={{
            border: '1px solid #d9d9d9',
            borderRadius: 6,
            padding: 12,
            minHeight: 200,
          }}
        >
          <EditorContent editor={editor} />
        </div>
      </Form.Item>

      {/* 附件 — 待集成 AttachmentBar compose 模式 */}

      <Form.Item>
        <Space>
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
          >
            发送
          </Button>
          <Button icon={<SaveOutlined />} onClick={handleSaveDraft}>
            保存草稿
          </Button>
        </Space>
      </Form.Item>

      {/* 群组选择器 */}
      <GroupSelector
        open={groupSelectorOpen}
        onClose={() => setGroupSelectorOpen(false)}
        onSelect={(members) => {
          const current = form.getFieldValue('to') as string[] || []
          const merged = Array.from(new Set([...current, ...members]))
          form.setFieldsValue({ to: merged })
        }}
      />
    </Form>
  )
}
