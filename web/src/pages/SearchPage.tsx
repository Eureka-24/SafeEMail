/** 搜索结果页 */
import { useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Typography, List, Skeleton, Tag } from 'antd'
import { useMailStore } from '../stores/mailStore'
import { EmptyState } from '../components/Common/EmptyState'
import { formatDate } from '../utils/format'

const { Title, Text } = Typography

export default function SearchPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const query = params.get('q') || ''
  const results = useMailStore((s) => s.searchResults)
  const loading = useMailStore((s) => s.loading)
  const searchMail = useMailStore((s) => s.searchMail)

  useEffect(() => {
    if (query) searchMail(query)
  }, [query, searchMail])

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>
        搜索结果{query && `：${query}`}
      </Title>

      {loading ? (
        <div>
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} active paragraph={{ rows: 1 }} style={{ marginBottom: 16 }} />
          ))}
        </div>
      ) : !results.length ? (
        <EmptyState description={query ? `未找到与"${query}"相关的邮件` : '请输入搜索关键词'} />
      ) : (
        <List
          dataSource={results}
          renderItem={(item) => (
            <List.Item
              key={item.email_id}
              onClick={() => navigate(`/mail/${item.email_id}`)}
              style={{ cursor: 'pointer', padding: '12px 16px' }}
            >
              <div style={{ display: 'flex', width: '100%', alignItems: 'center', gap: 12 }}>
                <Text style={{ width: 180, flexShrink: 0 }} ellipsis>
                  {item.from_user}
                </Text>
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8, overflow: 'hidden' }}>
                  <Tag color="blue" style={{ flexShrink: 0 }}>{item.match_type}</Tag>
                  <Text ellipsis>{item.subject || '(无主题)'}</Text>
                </div>
                <Text type="secondary" style={{ flexShrink: 0, fontSize: 13 }}>
                  {formatDate(item.sent_at)}
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
