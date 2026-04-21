/** 邮件列表组件 + 分页器 + 骨架屏 + 空状态 */
import { List, Pagination, Skeleton } from 'antd'
import { MailListItem } from './MailListItem'
import { EmptyState } from '../Common/EmptyState'
import type { Mail } from '../../types/mail'

interface MailListProps {
  mails: Mail[]
  loading: boolean
  total: number
  page: number
  pageSize: number
  showField: 'from' | 'to'
  emptyText?: string
  onPageChange: (page: number) => void
}

export function MailList({
  mails, loading, total, page, pageSize,
  showField, emptyText = '暂无邮件', onPageChange,
}: MailListProps) {
  if (loading) {
    return (
      <div style={{ padding: '16px 0' }}>
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} active paragraph={{ rows: 1 }} style={{ marginBottom: 16 }} />
        ))}
      </div>
    )
  }

  if (!mails.length) {
    return <EmptyState description={emptyText} />
  }

  return (
    <>
      <List
        dataSource={mails}
        renderItem={(mail) => (
          <MailListItem key={mail.email_id} mail={mail} showField={showField} />
        )}
        split
      />
      {total > pageSize && (
        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <Pagination
            current={page}
            total={total}
            pageSize={pageSize}
            onChange={onPageChange}
            showSizeChanger={false}
          />
        </div>
      )}
    </>
  )
}
