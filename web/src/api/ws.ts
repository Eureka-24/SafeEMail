/** WebSocket 连接管理 — 请求匹配 / 自动重连 / 心跳保活 */
import type { ProtocolResponse, Action } from '../types/protocol'
import { buildRequest } from './protocol'

interface PendingRequest {
  resolve: (resp: ProtocolResponse) => void
  reject: (err: Error) => void
  timer: ReturnType<typeof setTimeout>
}

type ConnectionListener = (connected: boolean, reconnecting: boolean) => void

const REQUEST_TIMEOUT = 15_000       // 15 秒超时
const HEARTBEAT_INTERVAL = 30_000    // 30 秒心跳
const HEARTBEAT_TIMEOUT = 60_000     // 60 秒无响应判定断连
const MAX_RECONNECT_DELAY = 30_000   // 最大重连间隔

export class SafeEmailWS {
  private ws: WebSocket | null = null
  private url = ''
  private pendingRequests = new Map<string, PendingRequest>()
  private reconnectAttempts = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private lastPongTime = Date.now()
  private closed = false
  private connectionListeners = new Set<ConnectionListener>()

  /** 注册连接状态监听 */
  onConnectionChange(listener: ConnectionListener): () => void {
    this.connectionListeners.add(listener)
    return () => this.connectionListeners.delete(listener)
  }

  private notifyConnectionChange(connected: boolean, reconnecting: boolean) {
    this.connectionListeners.forEach((l) => l(connected, reconnecting))
  }

  /** 建立连接 */
  connect(url: string): Promise<void> {
    this.url = url
    this.closed = false
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(url)
      } catch (err) {
        reject(err)
        return
      }

      this.ws.onopen = () => {
        this.reconnectAttempts = 0
        this.lastPongTime = Date.now()
        this.startHeartbeat()
        this.notifyConnectionChange(true, false)
        resolve()
      }

      this.ws.onmessage = (event: MessageEvent) => {
        this.lastPongTime = Date.now()
        try {
          const data = JSON.parse(event.data as string) as ProtocolResponse
          const pending = this.pendingRequests.get(data.request_id)
          if (pending) {
            clearTimeout(pending.timer)
            this.pendingRequests.delete(data.request_id)
            pending.resolve(data)
          }
        } catch {
          // 忽略非 JSON 消息
        }
      }

      this.ws.onclose = () => {
        this.stopHeartbeat()
        this.notifyConnectionChange(false, !this.closed)
        if (!this.closed) {
          this.scheduleReconnect()
        }
      }

      this.ws.onerror = () => {
        // onclose 会紧接着触发，重连逻辑在 onclose 中处理
        if (this.ws?.readyState !== WebSocket.OPEN) {
          reject(new Error('WebSocket 连接失败'))
        }
      }
    })
  }

  /** 发送协议请求并等待响应 */
  send(action: Action, payload: Record<string, unknown> = {}, token?: string | null): Promise<ProtocolResponse> {
    return new Promise((resolve, reject) => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        reject(new Error('WebSocket 未连接'))
        return
      }

      const request = buildRequest(action, payload, token)
      const timer = setTimeout(() => {
        this.pendingRequests.delete(request.request_id)
        reject(new Error(`请求超时: ${action}`))
      }, REQUEST_TIMEOUT)

      this.pendingRequests.set(request.request_id, { resolve, reject, timer })

      try {
        this.ws.send(JSON.stringify(request))
      } catch (err) {
        clearTimeout(timer)
        this.pendingRequests.delete(request.request_id)
        reject(err)
      }
    })
  }

  /** 断开连接 */
  disconnect() {
    this.closed = true
    this.stopHeartbeat()
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    // 清理所有 pending 请求
    this.pendingRequests.forEach((p) => {
      clearTimeout(p.timer)
      p.reject(new Error('连接已关闭'))
    })
    this.pendingRequests.clear()

    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  /** 当前是否已连接 */
  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  // ── 内部方法 ──

  private startHeartbeat() {
    this.stopHeartbeat()
    this.heartbeatTimer = setInterval(() => {
      // 检查是否超时无响应
      if (Date.now() - this.lastPongTime > HEARTBEAT_TIMEOUT) {
        this.ws?.close()
        return
      }
      // 发送心跳
      if (this.ws?.readyState === WebSocket.OPEN) {
        const ping = buildRequest('PING', {})
        this.ws.send(JSON.stringify(ping))
      }
    }, HEARTBEAT_INTERVAL)
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  private scheduleReconnect() {
    if (this.closed) return
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), MAX_RECONNECT_DELAY)
    this.reconnectAttempts++
    this.notifyConnectionChange(false, true)

    this.reconnectTimer = setTimeout(async () => {
      try {
        await this.connect(this.url)
      } catch {
        // connect 失败会触发 onclose → scheduleReconnect
      }
    }, delay)
  }
}

/** 全局单例 */
export const wsClient = new SafeEmailWS()
