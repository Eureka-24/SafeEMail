/** 创建群组弹窗 */
import { useState } from 'react'
import { Modal, Form, Input, message } from 'antd'
import { apiCreateGroup } from '../../api/client'

interface GroupFormProps {
  open: boolean
  onClose: () => void
  onCreated: () => void
}

export function GroupForm({ open, onClose, onCreated }: GroupFormProps) {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)

  const handleOk = async () => {
    try {
      const values = await form.validateFields()
      setLoading(true)
      const members = (values.members as string)
        .split('\n')
        .map((s: string) => s.trim())
        .filter(Boolean)
      if (!members.length) {
        message.error('至少需要一个成员')
        return
      }
      await apiCreateGroup(values.group_name, members)
      message.success('群组创建成功')
      form.resetFields()
      onCreated()
      onClose()
    } catch (err) {
      if (err && typeof err === 'object' && 'errorFields' in err) return
      message.error('创建失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      title="创建群组"
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      confirmLoading={loading}
      okText="创建"
      cancelText="取消"
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="group_name"
          label="群组名称"
          rules={[{ required: true, message: '请输入群组名称' }]}
        >
          <Input placeholder="输入群组名称" />
        </Form.Item>
        <Form.Item
          name="members"
          label="成员地址（每行一个）"
          rules={[{ required: true, message: '请输入成员地址' }]}
        >
          <Input.TextArea
            rows={5}
            placeholder={`user1@alpha.local\nuser2@beta.local`}
          />
        </Form.Item>
      </Form>
    </Modal>
  )
}
