/** 垃圾邮件标记 */
import { Tag } from 'antd'
import { WarningOutlined } from '@ant-design/icons'

export function SpamBadge() {
  return (
    <Tag icon={<WarningOutlined />} color="warning">
      垃圾邮件
    </Tag>
  )
}
