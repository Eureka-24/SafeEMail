/** 单封邮件摘要行 */
import { List, Tag, Typography } from 'antd'
import { WarningOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { formatDate } from '../../utils/format'
import type { Mail } from '../../types/mail'

const { Text } = Typography

interface MailListItemProps {
  mail: Mail
  /** 显示收件人（发件箱模式）还是发件人（收件箱模式） */
  showField: 'from' | 'to'
}

export function MailListItem({ mail, showField }: MailListItemProps) {
  const navigate = useNavigate()

  const isUnread = !mail.is_read
  const isRecalled = mail.status === 'RECALLED'
  const isSpam = mail.is_spam

  const personField =
    showField === 'from'
      ? mail.from_user
      : Array.isArray(mail.to_users)
        ? mail.to_users.join(', ')
        : String(mail.to_users)

  return (
    <List.Item
      onClick={() => navigate(`/mail/${mail.email_id}`)}
      style={{
        cursor: 'pointer',
        padding: '12px 16px',
        background: isSpam ? '#fffbe6' : undefined,
        borderLeft: isUnread ? '3px solid #1677ff' : '3px solid transparent',
      }}
    >
      <div style={{ display: 'flex', width: '100%', alignItems: 'center', gap: 12 }}>
        {/* 发件人/收件人 */}
        <Text
          strong={isUnread}
          style={{
            width: 180,
            flexShrink: 0,
            color: isRecalled ? '#999' : undefined,
            fontStyle: isRecalled ? 'italic' : undefined,
          }}
          ellipsis
        >
          {personField}
        </Text>

        {/* 主题 + 标签 */}
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8, overflow: 'hidden' }}>
          {isSpam && (
            <Tag icon={<WarningOutlined />} color="warning" style={{ flexShrink: 0 }}>
              垃圾
            </Tag>
          )}
          {isRecalled && (
            <Tag color="default" style={{ flexShrink: 0, fontStyle: 'italic' }}>
              已撤回
            </Tag>
          )}
          <Text
            strong={isUnread}
            ellipsis
            style={{
              color: isRecalled ? '#999' : undefined,
              fontStyle: isRecalled ? 'italic' : undefined,
            }}
          >
            {mail.subject || '(无主题)'}
          </Text>
        </div>

        {/* 时间 */}
        <Text type="secondary" style={{ flexShrink: 0, fontSize: 13 }}>
          {formatDate(mail.sent_at || mail.created_at)}
        </Text>
      </div>
    </List.Item>
  )
}
