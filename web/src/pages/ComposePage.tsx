/** 写邮件页面（新邮件/回复/转发/编辑草稿） */
import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Typography, Spin } from 'antd'
import { ComposeForm } from '../components/Mail/ComposeForm'
import { useMailStore } from '../stores/mailStore'
import type { MailDetail } from '../types/mail'

const { Title } = Typography

export default function ComposePage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const readMail = useMailStore((s) => s.readMail)
  const currentMail = useMailStore((s) => s.currentMail)
  const clearCurrentMail = useMailStore((s) => s.clearCurrentMail)

  const draftId = params.get('draft')
  const replyId = params.get('reply')
  const forwardId = params.get('forward')

  const [contextMail, setContextMail] = useState<MailDetail | null>(null)
  const [loading, setLoading] = useState(false)

  // 加载草稿/回复/转发的原始邮件
  useEffect(() => {
    const mailId = draftId || replyId || forwardId
    if (mailId) {
      setLoading(true)
      readMail(mailId).then(() => setLoading(false))
    }
    return () => clearCurrentMail()
  }, [draftId, replyId, forwardId, readMail, clearCurrentMail])

  useEffect(() => {
    if (currentMail) setContextMail(currentMail)
  }, [currentMail])

  const getTitle = () => {
    if (draftId) return '编辑草稿'
    if (replyId) return '回复邮件'
    if (forwardId) return '转发邮件'
    return '写邮件'
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>{getTitle()}</Title>
      <ComposeForm
        draft={draftId ? contextMail : null}
        replyTo={replyId ? contextMail : null}
        forwardFrom={forwardId ? contextMail : null}
        onSuccess={() => navigate('/sent')}
      />
    </div>
  )
}
