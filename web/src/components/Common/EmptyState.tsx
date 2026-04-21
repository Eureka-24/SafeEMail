/** 空状态提示组件 */
import { Empty } from 'antd'

interface EmptyStateProps {
  description?: string
}

export function EmptyState({ description = '暂无数据' }: EmptyStateProps) {
  return (
    <div style={{ padding: '60px 0' }}>
      <Empty description={description} />
    </div>
  )
}
