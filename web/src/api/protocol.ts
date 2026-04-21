/** 协议消息构造 — 与 shared/protocol.py 对齐 */
import { v4 as uuidv4 } from 'uuid'
import type { ProtocolRequest, Action } from '../types/protocol'

/** 构造标准协议请求 */
export function buildRequest(
  action: Action,
  payload: Record<string, unknown> = {},
  token?: string | null,
): ProtocolRequest {
  return {
    version: '1.0',
    type: 'REQUEST',
    action,
    request_id: uuidv4(),
    token: token ?? null,
    payload,
  }
}
