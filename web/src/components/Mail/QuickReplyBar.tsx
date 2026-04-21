/** 快速回复建议条 */
import { useEffect, useState } from 'react'
import { Button, Space, Spin, Typography } from 'antd'
import { ThunderboltOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useMailStore } from '../../stores/mailStore'

const { Text } = Typography

interface QuickReplyBarProps {
  emailId: string
}

export function QuickReplyBar({ emailId }: QuickReplyBarProps) {
  const navigate = useNavigate()
  const getQuickReplies = useMailStore((s) => s.getQuickReplies)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    getQuickReplies(emailId)
      .then(setSuggestions)
      .catch(() => setSuggestions([]))
      .finally(() => setLoading(false))
  }, [emailId, getQuickReplies])

  if (loading) {
    return <Spin size="small" style={{ margin: '8px 0' }} />
  }

  if (!suggestions.length) return null

  return (
    <div style={{ marginTop: 16, padding: '12px 16px', background: '#f6f8fa', borderRadius: 8 }}>
      <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
        <ThunderboltOutlined /> 快速回复建议
      </Text>
      <Space wrap>
        {suggestions.map((text, i) => (
          <Button
            key={i}
            size="small"
            onClick={() =>
              navigate(`/compose?reply=${emailId}&quickReply=${encodeURIComponent(text)}`)
            }
          >
            {text}
          </Button>
        ))}
      </Space>
    </div>
  )
}
