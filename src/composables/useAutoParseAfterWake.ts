/**
 * 解析页与唤醒页共用的开关：唤醒成功后是否自动执行 *_resume.py
 * 使用 localStorage 持久化，避免仅写在某一页导致另一页读不到。
 */
const STORAGE_KEY = 'resume_auto_parse_after_wake'

export function loadAutoParseAfterWake(): boolean {
  const v = localStorage.getItem(STORAGE_KEY)
  if (v === null) return true
  return v === 'true'
}

export function saveAutoParseAfterWake(value: boolean): void {
  localStorage.setItem(STORAGE_KEY, String(value))
}
