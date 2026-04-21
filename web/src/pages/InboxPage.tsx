/** 收件箱页面 */
import { useEffect } from 'react'
import { Typography } from 'antd'
import { MailList } from '../components/Mail/MailList'
import { useMailStore } from '../stores/mailStore'

const { Title } = Typography

export default function InboxPage() {
  const mails = useMailStore((s) => s.inboxMails)
  const loading = useMailStore((s) => s.loading)
  const page = useMailStore((s) => s.inboxPage)
  const total = useMailStore((s) => s.inboxTotal)
  const pageSize = useMailStore((s) => s.pageSize)
  const fetchInbox = useMailStore((s) => s.fetchInbox)

  useEffect(() => {
    fetchInbox(1)
  }, [fetchInbox])

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>收件箱</Title>
      <MailList
        mails={mails}
        loading={loading}
        total={total}
        page={page}
        pageSize={pageSize}
        showField="from"
        emptyText="收件箱是空的"
        onPageChange={(p) => fetchInbox(p)}
      />
    </div>
  )
}
