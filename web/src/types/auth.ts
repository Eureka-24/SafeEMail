/** 认证相关类型 */

export interface LoginPayload {
  username: string
  password: string
  captcha_answer?: string
}

export interface RegisterPayload {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  user_id: string
  username: string
  domain: string
}

export interface RefreshResponse {
  access_token: string
}

export interface RegisterResponse {
  user_id: string
  username: string
}

/** JWT payload 中解析出的用户信息 */
export interface TokenPayload {
  sub: string        // user_id
  username: string
  domain: string
  jti: string
  iat: number
  exp: number
  type: 'access' | 'refresh'
}
