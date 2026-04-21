/** 撤回按钮 — 5 分钟窗口倒计时 + 二次确认 */
import { useState, useEffect, useRef } from 'react'
import { Button, Modal, message, Typography } from 'antd'
import { UndoOutlined } from '@ant-design/icons'
import { useMailStore } from '../../stores/mailStore'

const { Text } = Typography

interface RecallButtonProps {
  emailId: string
  sentAt: string  // ISO 时间
  recallSignature?: string
  status: string
  onRecalled?: () => void
}

const RECALL_WINDOW_MS = 5 * 60 * 1000 // 5 分钟

export function RecallButton({ emailId, sentAt, recallSignature, status, onRecalled }: RecallButtonProps) {
  const recallMail = useMailStore((s) => s.recallMail)
  const [remaining, setRemaining] = useState(0)
  const [loading, setLoading] = useState(false)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    const calc = () => {
      const sent = new Date(sentAt).getTime()
      const left = sent + RECALL_WINDOW_MS - Date.now()
      return Math.max(0, left)
    }

    setRemaining(calc())
    timerRef.current = setInterval(() => {
      const left = calc()
      setRemaining(left)
      if (left <= 0 && timerRef.current) {
        clearInterval(timerRef.current)
      }
    }, 1000)

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [sentAt])

  // 已撤回或超时或非 SENT 状态不显示
  if (status !== 'SENT' || remaining <= 0) return null

  const formatRemaining = () => {
    const totalSec = Math.ceil(remaining / 1000)
    const min = Math.floor(totalSec / 60)
    const sec = totalSec % 60
    return `${min}:${sec.toString().padStart(2, '0')}`
  }

  const handleRecall = () => {
    if (!recallSignature) {
      message.error('缺少撤回签名，无法撤回')
      return
    }
    Modal.confirm({
      title: '确认撤回',
      content: '撤回后，如果收件人已阅读，邮件仍会标记为已撤回。确认撤回？',
      okText: '撤回',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        setLoading(true)
        try {
          const resp = await recallMail(emailId, recallSignature)
          const payload = resp.payload as Record<string, unknown>
          if (payload?.already_read) {
            message.warning('撤回成功，但收件人已阅读')
          } else {
            message.success('邮件已撤回')
          }
          onRecalled?.()
        } catch {
          message.error('撤回失败')
        } finally {
          setLoading(false)
        }
      },
    })
  }

  return (
    <Button
      icon={<UndoOutlined />}
      onClick={handleRecall}
      loading={loading}
      danger
    >
      撤回 <Text type="secondary" style={{ marginLeft: 4, fontSize: 12 }}>({formatRemaining()})</Text>
    </Button>
  )
}
