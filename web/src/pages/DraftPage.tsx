/** 草稿箱页面 */
import { useEffect } from 'react'
import { List, Typography, Skeleton } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useMailStore } from '../stores/mailStore'
import { EmptyState } from '../components/Common/EmptyState'
import { formatDate } from '../utils/format'

const { Title, Text } = Typography

export default function DraftPage() {
  const drafts = useMailStore((s) => s.drafts)
  const loading = useMailStore((s) => s.loading)
  const fetchDrafts = useMailStore((s) => s.fetchDrafts)
  const navigate = useNavigate()

  useEffect(() => {
    fetchDrafts()
  }, [fetchDrafts])

  if (loading) {
    return (
      <div>
        <Title level={4} style={{ marginBottom: 16 }}>草稿箱</Title>
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} active paragraph={{ rows: 1 }} style={{ marginBottom: 16 }} />
        ))}
      </div>
    )
  }

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>草稿箱</Title>
      {!drafts.length ? (
        <EmptyState description="没有草稿" />
      ) : (
        <List
          dataSource={drafts}
          renderItem={(draft) => (
            <List.Item
              key={draft.email_id}
              onClick={() => navigate(`/compose?draft=${draft.email_id}`)}
              style={{ cursor: 'pointer', padding: '12px 16px' }}
            >
              <div style={{ display: 'flex', width: '100%', alignItems: 'center', gap: 12 }}>
                <Text style={{ width: 180, flexShrink: 0 }} ellipsis>
                  {Array.isArray(draft.to_users) ? draft.to_users.join(', ') : '(无收件人)'}
                </Text>
                <Text ellipsis style={{ flex: 1 }}>
                  {draft.subject || '(无主题)'}
                </Text>
                <Text type="secondary" style={{ flexShrink: 0, fontSize: 13 }}>
                  {formatDate(draft.created_at)}
                </Text>
              </div>
            </List.Item>
          )}
          split
        />
      )}
    </div>
  )
}
