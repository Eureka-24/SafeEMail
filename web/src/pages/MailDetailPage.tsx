/** 邮件详情/阅读页 */
import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button, Space, Spin, Divider, Typography } from 'antd'
import { ArrowLeftOutlined, SendOutlined } from '@ant-design/icons'
import { useMailStore } from '../stores/mailStore'
import { useAuthStore } from '../stores/authStore'
import { MailViewer } from '../components/Mail/MailViewer'
import { AttachmentBar } from '../components/Mail/AttachmentBar'
import { RecallButton } from '../components/Common/RecallButton'
import { ActionButtons } from '../components/Mail/ActionButtons'
import { QuickReplyBar } from '../components/Mail/QuickReplyBar'

const { Title } = Typography

export default function MailDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const mail = useMailStore((s) => s.currentMail)
  const loading = useMailStore((s) => s.loading)
  const readMail = useMailStore((s) => s.readMail)
  const clearCurrentMail = useMailStore((s) => s.clearCurrentMail)
  const username = useAuthStore((s) => s.username)
  const domain = useAuthStore((s) => s.domain)

  useEffect(() => {
    if (id) readMail(id)
    return () => clearCurrentMail()
  }, [id, readMail, clearCurrentMail])

  if (loading || !mail) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Spin size="large" />
      </div>
    )
  }

  const currentUser = `${username}@${domain}`
  const isSender = mail.from_user === currentUser

  return (
    <div>
      {/* 顶栏操作 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
          返回
        </Button>
        <Space>
          {/* 撤回按钮 */}
          {isSender && (
            <RecallButton
              emailId={mail.email_id}
              sentAt={mail.sent_at || mail.created_at}
              recallSignature={mail.recall_signature}
              status={mail.status}
              onRecalled={() => { if (id) readMail(id) }}
            />
          )}
          <Button
            icon={<SendOutlined />}
            onClick={() => navigate(`/compose?reply=${mail.email_id}`)}
          >
            回复
          </Button>
          <Button
            onClick={() => navigate(`/compose?forward=${mail.email_id}`)}
          >
            转发
          </Button>
        </Space>
      </div>

      {/* 主题 */}
      <Title level={4}>{mail.subject || '(无主题)'}</Title>

      {/* 邮件正文 */}
      <MailViewer mail={mail} />

      {/* 快捷操作按钮 */}
      {mail.actions && mail.actions.length > 0 && (
        <ActionButtons emailId={mail.email_id} actions={mail.actions} />
      )}

      {/* 附件区域 */}
      {mail.attachments && mail.attachments.length > 0 && (
        <>
          <Divider />
          <AttachmentBar mode="read" attachments={mail.attachments} />
        </>
      )}

      {/* 快速回复建议 */}
      <QuickReplyBar emailId={mail.email_id} />
    </div>
  )
}
