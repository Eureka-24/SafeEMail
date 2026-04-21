/** 验证码弹窗组件 */
import { useState } from 'react'
import { Modal, Input, Typography } from 'antd'

const { Text } = Typography

interface CaptchaModalProps {
  open: boolean
  question: string
  onSubmit: (answer: string) => void
  onCancel: () => void
}

export function CaptchaModal({ open, question, onSubmit, onCancel }: CaptchaModalProps) {
  const [answer, setAnswer] = useState('')

  const handleOk = () => {
    if (answer.trim()) {
      onSubmit(answer.trim())
      setAnswer('')
    }
  }

  return (
    <Modal
      title="安全验证"
      open={open}
      onOk={handleOk}
      onCancel={() => {
        setAnswer('')
        onCancel()
      }}
      okText="提交"
      cancelText="取消"
    >
      <div style={{ marginBottom: 16 }}>
        <Text>请回答以下问题以验证身份：</Text>
      </div>
      <div style={{ marginBottom: 16, fontSize: 18, fontWeight: 'bold' }}>
        {question}
      </div>
      <Input
        placeholder="请输入答案"
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        onPressEnter={handleOk}
        autoFocus
      />
    </Modal>
  )
}
