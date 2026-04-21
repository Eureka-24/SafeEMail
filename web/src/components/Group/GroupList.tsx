/** 群组列表组件 */
import { List, Tag, Empty } from 'antd'
import { TeamOutlined, UserOutlined } from '@ant-design/icons'
import type { Group } from '../../types/mail'

interface GroupListProps {
  groups: Group[]
  loading: boolean
  currentUserId?: string
}

export function GroupList({ groups, loading, currentUserId }: GroupListProps) {
  if (!loading && !groups.length) {
    return <Empty description="暂无群组" style={{ padding: '40px 0' }} />
  }

  return (
    <List
      loading={loading}
      dataSource={groups}
      renderItem={(group) => (
        <List.Item key={group.group_id}>
          <List.Item.Meta
            avatar={<TeamOutlined style={{ fontSize: 24, color: '#1677ff' }} />}
            title={
              <span>
                {group.group_name}
                <Tag style={{ marginLeft: 8 }}>{group.members.length} 人</Tag>
                {group.owner_id === currentUserId && (
                  <Tag color="blue">我创建的</Tag>
                )}
              </span>
            }
            description={
              <div style={{ marginTop: 4 }}>
                {group.members.map((m) => (
                  <Tag key={m} icon={<UserOutlined />} style={{ marginBottom: 4 }}>
                    {m}
                  </Tag>
                ))}
              </div>
            }
          />
        </List.Item>
      )}
    />
  )
}
