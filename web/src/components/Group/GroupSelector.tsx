/** 群组选择器弹窗 — 选择群组后展开成员地址 */
import { useEffect, useState } from 'react'
import { Modal, List, Checkbox, Spin, message } from 'antd'
import { TeamOutlined } from '@ant-design/icons'
import { apiListGroups } from '../../api/client'
import type { Group } from '../../types/mail'

interface GroupSelectorProps {
  open: boolean
  onClose: () => void
  onSelect: (members: string[]) => void
}

export function GroupSelector({ open, onClose, onSelect }: GroupSelectorProps) {
  const [groups, setGroups] = useState<Group[]>([])
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setSelected(new Set())
    apiListGroups()
      .then(setGroups)
      .catch(() => message.error('获取群组失败'))
      .finally(() => setLoading(false))
  }, [open])

  const toggleGroup = (groupId: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(groupId)) next.delete(groupId)
      else next.add(groupId)
      return next
    })
  }

  const handleOk = () => {
    const members = new Set<string>()
    groups.forEach((g) => {
      if (selected.has(g.group_id)) {
        g.members.forEach((m) => members.add(m))
      }
    })
    onSelect(Array.from(members))
    onClose()
  }

  return (
    <Modal
      title="选择群组"
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      okText="添加成员"
      cancelText="取消"
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: 24 }}><Spin /></div>
      ) : (
        <List
          dataSource={groups}
          renderItem={(group) => (
            <List.Item key={group.group_id}>
              <Checkbox
                checked={selected.has(group.group_id)}
                onChange={() => toggleGroup(group.group_id)}
              >
                <TeamOutlined style={{ marginRight: 4 }} />
                {group.group_name}（{group.members.length} 人）
              </Checkbox>
            </List.Item>
          )}
        />
      )}
    </Modal>
  )
}
