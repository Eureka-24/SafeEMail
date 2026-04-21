/** 密码 / 用户名前端预校验规则 */

/** 用户名校验：≥ 3 字符 */
export function validateUsername(username: string): string | null {
  if (!username || username.length < 3) {
    return '用户名至少需要 3 个字符'
  }
  return null
}

/** 密码校验：≥ 8 位，包含大写 + 小写 + 数字 */
export function validatePassword(password: string): string | null {
  if (!password || password.length < 8) {
    return '密码至少需要 8 位'
  }
  if (!/[A-Z]/.test(password)) {
    return '密码需要包含大写字母'
  }
  if (!/[a-z]/.test(password)) {
    return '密码需要包含小写字母'
  }
  if (!/[0-9]/.test(password)) {
    return '密码需要包含数字'
  }
  return null
}

/** 确认密码一致性校验 */
export function validateConfirmPassword(password: string, confirm: string): string | null {
  if (password !== confirm) {
    return '两次输入的密码不一致'
  }
  return null
}
