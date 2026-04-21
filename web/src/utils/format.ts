/** 日期/文件大小格式化工具 */

/** 格式化日期为可读字符串 */
export function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(date.getFullYear(), date.getMonth(), date.getDate())

  const pad = (n: number) => n.toString().padStart(2, '0')

  if (target.getTime() === today.getTime()) {
    // 今天 — 只显示时间
    return `${pad(date.getHours())}:${pad(date.getMinutes())}`
  }

  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  if (target.getTime() === yesterday.getTime()) {
    return `昨天 ${pad(date.getHours())}:${pad(date.getMinutes())}`
  }

  // 今年
  if (date.getFullYear() === now.getFullYear()) {
    return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
  }

  // 非今年
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** 格式化文件大小 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
