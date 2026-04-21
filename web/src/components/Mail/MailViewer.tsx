/** 邮件正文查看组件 */
import { Typography, Descriptions, Alert, Divider } from 'antd'
import DOMPurify from 'dompurify'
import { formatDate } from '../../utils/format'
import type { MailDetail } from '../../types/mail'

const { Text } = Typography

interface MailViewerProps {
  mail: MailDetail
}

export function MailViewer({ mail }: MailViewerProps) {
  const toList = Array.isArray(mail.to_users) ? mail.to_users.join(', ') : String(mail.to_users)
  const sanitizedBody = DOMPurify.sanitize(mail.body || '')
  const isSpam = mail.is_spam === 1 || mail.is_spam === true

  return (
    <div>
      {/* 垃圾邮件警告 */}
      {isSpam && (
        <Alert
          message="此邮件被检测为垃圾/钓鱼邮件，请谨慎操作"
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {/* 邮件头 */}
      <Descriptions column={1} size="small" style={{ marginBottom: 16 }}>
        <Descriptions.Item label="发件人">
          <Text strong>{mail.from_user}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="收件人">{toList}</Descriptions.Item>
        <Descriptions.Item label="时间">
          {formatDate(mail.sent_at || mail.created_at)}
        </Descriptions.Item>
        {mail.category && (
          <Descriptions.Item label="分类">{mail.category}</Descriptions.Item>
        )}
      </Descriptions>

      <Divider style={{ margin: '12px 0' }} />

      {/* 正文 — DOMPurify 清洗后渲染 */}
      <div
        style={{ lineHeight: 1.8, minHeight: 100 }}
        dangerouslySetInnerHTML={{ __html: sanitizedBody }}
      />
    </div>
  )
}
