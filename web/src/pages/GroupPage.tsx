/** 群组管理页面 */
import { useEffect, useState } from 'react'
import { Typography, Button } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { apiListGroups } from '../api/client'
import { useAuthStore } from '../stores/authStore'
import { GroupList } from '../components/Group/GroupList'
import { GroupForm } from '../components/Group/GroupForm'
import type { Group } from '../types/mail'

const { Title } = Typography

export default function GroupPage() {
  const [groups, setGroups] = useState<Group[]>([])
  const [loading, setLoading] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const userId = useAuthStore((s) => s.userId)

  const fetchGroups = async () => {
    setLoading(true)
    try {
      const data = await apiListGroups()
      setGroups(data)
    } catch {
      // 忽略
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchGroups()
  }, [])

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>群组管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setShowForm(true)}>
          创建群组
        </Button>
      </div>
      <GroupList groups={groups} loading={loading} currentUserId={userId ?? undefined} />
      <GroupForm
        open={showForm}
        onClose={() => setShowForm(false)}
        onCreated={fetchGroups}
      />
    </div>
  )
}
