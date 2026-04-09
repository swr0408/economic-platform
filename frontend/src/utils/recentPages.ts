/**
 * 最近見たページ - localStorage 永続化ユーティリティ
 *
 * ページ遷移時に自動的に履歴を保存し、ホーム画面で表示する。
 * サーバー保存は Phase 3 で検討 (クラウド移行後 or 会員要望ベース)。
 */

const STORAGE_KEY = 'econalpha.recentPages'
const MAX_ENTRIES = 10
// ホームや認証ページは記録しない
const EXCLUDED_PATHS = new Set<string>([
  '/',
  '/login',
  '/register',
  '/account/password',
])

export interface RecentPageEntry {
  path: string // 例: "/country/usa/inflation"
  title: string // 例: "米国 - インフレ"
  viewedAt: number // Unix ms
}

function safeParse(raw: string | null): RecentPageEntry[] {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (e): e is RecentPageEntry =>
        e && typeof e.path === 'string' && typeof e.title === 'string' && typeof e.viewedAt === 'number'
    )
  } catch {
    return []
  }
}

export function getRecentPages(): RecentPageEntry[] {
  try {
    return safeParse(localStorage.getItem(STORAGE_KEY))
  } catch {
    return []
  }
}

export function recordPageVisit(path: string, title: string): void {
  // 除外パスは記録しない
  if (EXCLUDED_PATHS.has(path)) return
  // タイトルが空なら記録しない
  if (!title || !title.trim()) return

  try {
    const now = Date.now()
    const current = getRecentPages()
    // 同一パスがあれば削除 (最新位置に移動)
    const filtered = current.filter((e) => e.path !== path)
    const next: RecentPageEntry[] = [
      { path, title: title.trim(), viewedAt: now },
      ...filtered,
    ].slice(0, MAX_ENTRIES)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    // 同じタブ内の他のコンポーネントに通知
    window.dispatchEvent(new CustomEvent('econalpha:recent-pages-changed'))
  } catch {
    /* ignore quota errors */
  }
}

export function clearRecentPages(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
    window.dispatchEvent(new CustomEvent('econalpha:recent-pages-changed'))
  } catch {
    /* ignore */
  }
}
