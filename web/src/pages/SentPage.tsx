/** 发件箱页面 */
import { useEffect } from 'react'
import { Typography } from 'antd'
import { MailList } from '../components/Mail/MailList'
import { useMailStore } from '../stores/mailStore'

const { Title } = Typography

export default function SentPage() {
  const mails = useMailStore((s) => s.sentMails)
  const loading = useMailStore((s) => s.loading)
  const page = useMailStore((s) => s.sentPage)
  const total = useMailStore((s) => s.sentTotal)
  const pageSize = useMailStore((s) => s.pageSize)
  const fetchSent = useMailStore((s) => s.fetchSent)

  useEffect(() => {
    fetchSent(1)
  }, [fetchSent])

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>发件箱</Title>
      <MailList
        mails={mails}
        loading={loading}
        total={total}
        page={page}
        pageSize={pageSize}
        showField="to"
        emptyText="发件箱是空的"
        onPageChange={(p) => fetchSent(p)}
      />
    </div>
  )
}
