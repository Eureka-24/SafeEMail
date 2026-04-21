/** 快捷操作按钮组 — 从邮件 actions 字段动态渲染 */
import { Button, Space, Modal, message } from 'antd'
import {
  CalendarOutlined, CheckOutlined, CloseOutlined,
  LinkOutlined, CopyOutlined,
} from '@ant-design/icons'
import { useMailStore } from '../../stores/mailStore'
import type { MailAction } from '../../types/mail'

interface ActionButtonsProps {
  emailId: string
  actions: MailAction[]
}

const iconMap: Record<string, React.ReactNode> = {
  schedule: <CalendarOutlined />,
  confirm: <CheckOutlined />,
  reject: <CloseOutlined />,
  safe_link: <LinkOutlined />,
  summary: <CopyOutlined />,
}

export function ActionButtons({ emailId, actions }: ActionButtonsProps) {
  const execAction = useMailStore((s) => s.execAction)

  if (!actions?.length) return null

  const handleAction = (action: MailAction, index: number) => {
    switch (action.type) {
      case 'schedule':
        execAction(emailId, index)
          .then(() => message.success('已添加日程'))
          .catch(() => message.error('操作失败'))
        break

      case 'confirm':
      case 'reject':
        Modal.confirm({
          title: `确认${action.type === 'confirm' ? '接受' : '拒绝'}`,
          content: `确定要${action.label}吗？`,
          okText: '确定',
          cancelText: '取消',
          onOk: () =>
            execAction(emailId, index, true)
              .then(() => message.success('操作成功'))
              .catch(() => message.error('操作失败')),
        })
        break

      case 'safe_link': {
        const url = action.data?.url as string | undefined
        if (!url) {
          message.error('链接无效')
          return
        }
        // 简单安全检查
        if (url.startsWith('https://') || url.startsWith('http://')) {
          window.open(url, '_blank', 'noopener,noreferrer')
        } else {
          Modal.warning({
            title: '不安全链接',
            content: `此链接看起来不安全：${url}`,
          })
        }
        break
      }

      case 'summary': {
        const summary = action.data?.text as string | undefined
        if (summary) {
          navigator.clipboard.writeText(summary)
            .then(() => message.success('摘要已复制到剪贴板'))
            .catch(() => message.error('复制失败'))
        }
        break
      }

      default:
        execAction(emailId, index)
          .then(() => message.success('操作成功'))
          .catch(() => message.error('操作失败'))
    }
  }

  return (
    <div style={{ marginTop: 16 }}>
      <Space wrap>
        {actions.map((action, i) => (
          <Button
            key={i}
            icon={iconMap[action.type]}
            onClick={() => handleAction(action, i)}
          >
            {action.label}
          </Button>
        ))}
      </Space>
    </div>
  )
}
