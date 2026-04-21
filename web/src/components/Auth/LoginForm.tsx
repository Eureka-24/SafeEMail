/** 登录表单组件 */
import { useState } from 'react'
import { Form, Input, Button, message } from 'antd'
import { UserOutlined, LockOutlined } from '@ant-design/icons'
import { useAuthStore } from '../../stores/authStore'
import { useNavigate } from 'react-router-dom'
import { CaptchaModal } from './CaptchaModal'
import type { LoginPayload } from '../../types/auth'

export function LoginForm() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [captchaVisible, setCaptchaVisible] = useState(false)
  const [captchaQuestion, setCaptchaQuestion] = useState('')
  const [rateLimitSeconds, setRateLimitSeconds] = useState(0)
  const login = useAuthStore((s) => s.login)
  const navigate = useNavigate()

  // 限流倒计时
  useState(() => {
    if (rateLimitSeconds > 0) {
      const timer = setInterval(() => {
        setRateLimitSeconds((prev) => {
          if (prev <= 1) {
            clearInterval(timer)
            return 0
          }
          return prev - 1
        })
      }, 1000)
      return () => clearInterval(timer)
    }
  })

  const handleLogin = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      const payload: LoginPayload = {
        username: values.username,
        password: values.password,
      }
      await login(payload)
      message.success('登录成功')
      navigate('/inbox', { replace: true })
    } catch (err: unknown) {
      const error = err as { status?: number; payload?: Record<string, unknown>; message?: string }
      if (error.status === 429) {
        setRateLimitSeconds(60)
        message.error('操作过于频繁，请稍后再试')
      } else if (error.payload?.captcha_required) {
        setCaptchaQuestion((error.payload.captcha_question as string) || '请计算: 3 + 5 = ?')
        setCaptchaVisible(true)
      } else {
        message.error(error.message || '登录失败')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleCaptchaSubmit = async (answer: string) => {
    setCaptchaVisible(false)
    setLoading(true)
    try {
      const values = form.getFieldsValue()
      const payload: LoginPayload = {
        username: values.username,
        password: values.password,
        captcha_answer: answer,
      }
      await login(payload)
      message.success('登录成功')
      navigate('/inbox', { replace: true })
    } catch (err: unknown) {
      const error = err as { message?: string }
      message.error(error.message || '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Form form={form} onFinish={handleLogin} size="large" autoComplete="off">
        <Form.Item
          name="username"
          rules={[
            { required: true, message: '请输入用户名' },
            { min: 3, message: '用户名至少 3 个字符' },
          ]}
        >
          <Input prefix={<UserOutlined />} placeholder="用户名" />
        </Form.Item>

        <Form.Item
          name="password"
          rules={[
            { required: true, message: '请输入密码' },
            { min: 8, message: '密码至少 8 位' },
            {
              pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/,
              message: '密码需包含大写、小写字母和数字',
            },
          ]}
        >
          <Input.Password prefix={<LockOutlined />} placeholder="密码" />
        </Form.Item>

        <Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            loading={loading}
            disabled={rateLimitSeconds > 0}
            block
          >
            {rateLimitSeconds > 0 ? `请等待 ${rateLimitSeconds}s` : '登录'}
          </Button>
        </Form.Item>
      </Form>

      <CaptchaModal
        open={captchaVisible}
        question={captchaQuestion}
        onSubmit={handleCaptchaSubmit}
        onCancel={() => setCaptchaVisible(false)}
      />
    </>
  )
}
