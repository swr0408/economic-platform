/**
 * グローバル fetch ラッパ
 *
 * 目的:
 * - 既存の各チャートコンポーネントは `await fetch('/api/...')` を直接呼んでいるが、
 *   それらに Authorization ヘッダや credentials が付いていないため、
 *   visibility 制御 (special/master) が掛かった endpoint で 401 になる。
 * - すべてのコンポーネントを書き直す代わりに、グローバル window.fetch を上書きして
 *   `/api/` 宛のリクエストには自動で
 *     - credentials: 'include'  (httpOnly Cookie 送信)
 *     - Authorization: Bearer <token> (localStorage から自動付与)
 *   を設定する。
 *
 * 安全性:
 * - 既に Authorization ヘッダが付いている場合は上書きしない
 * - 既に credentials が指定されている場合は上書きしない
 * - /api/ 以外 (外部 CDN 等) は素通し
 */

const AUTH_TOKEN_STORAGE_KEY = 'auth.token'

function readAuthToken(): string | null {
  try {
    return localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
  } catch {
    return null
  }
}

function isApiUrl(url: string): boolean {
  // 絶対 URL の場合は origin を見る
  if (url.startsWith('http://') || url.startsWith('https://')) {
    try {
      const u = new URL(url)
      // 同一 origin の /api/ 宛
      if (u.origin === window.location.origin && u.pathname.startsWith('/api/')) {
        return true
      }
      // localhost/127.0.0.1 の /api/ も対象 (dev での fallback)
      if (
        (u.hostname === 'localhost' || u.hostname === '127.0.0.1') &&
        u.pathname.startsWith('/api/')
      ) {
        return true
      }
      return false
    } catch {
      return false
    }
  }
  // 相対 URL の場合
  return url.startsWith('/api/')
}

function extractUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.toString()
  // Request オブジェクト
  return input.url
}

function hasAuthHeader(headers: HeadersInit | undefined): boolean {
  if (!headers) return false
  if (headers instanceof Headers) {
    return headers.has('Authorization') || headers.has('authorization')
  }
  if (Array.isArray(headers)) {
    return headers.some(([k]) => k.toLowerCase() === 'authorization')
  }
  return Object.keys(headers).some((k) => k.toLowerCase() === 'authorization')
}

function mergeHeaders(
  headers: HeadersInit | undefined,
  authHeader: string,
): HeadersInit {
  if (!headers) {
    return { Authorization: authHeader }
  }
  if (headers instanceof Headers) {
    const cloned = new Headers(headers)
    cloned.set('Authorization', authHeader)
    return cloned
  }
  if (Array.isArray(headers)) {
    return [...headers, ['Authorization', authHeader]]
  }
  return { ...headers, Authorization: authHeader }
}

/** /api/ リクエストのデフォルトタイムアウト (ms) */
const DEFAULT_API_TIMEOUT_MS = 30_000

let installed = false

export function installAuthFetch(): void {
  if (installed) return
  if (typeof window === 'undefined' || typeof window.fetch !== 'function') return

  const originalFetch = window.fetch.bind(window)

  window.fetch = (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = extractUrl(input)
    if (!isApiUrl(url)) {
      return originalFetch(input, init)
    }

    const merged: RequestInit = { ...(init ?? {}) }

    // Cookie を必ず送る (オリジン同一でも明示しておく)
    if (merged.credentials === undefined) {
      merged.credentials = 'include'
    }

    // Bearer token 自動付与 (既存ヘッダがあれば優先)
    if (!hasAuthHeader(merged.headers)) {
      const token = readAuthToken()
      if (token) {
        merged.headers = mergeHeaders(merged.headers, `Bearer ${token}`)
      }
    }

    // タイムアウト自動付与 (signal が未設定の場合のみ)
    // fetchWithTimeout 等で既に signal を設定済みなら介入しない
    if (!merged.signal) {
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), DEFAULT_API_TIMEOUT_MS)
      merged.signal = controller.signal

      return originalFetch(input, merged)
        .then((response) => {
          clearTimeout(timer)
          return response
        })
        .catch((err) => {
          clearTimeout(timer)
          if (err instanceof DOMException && err.name === 'AbortError') {
            throw new Error(`Request timed out after ${DEFAULT_API_TIMEOUT_MS}ms: ${url}`)
          }
          throw err
        })
    }

    return originalFetch(input, merged)
  }

  installed = true
}
