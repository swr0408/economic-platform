/**
 * API ベース URL の一元管理。
 *
 * ローカル開発 (Vite proxy): VITE_API_BASE_URL は空 → same-origin で動く。
 * 本番 (Vercel):             VITE_API_BASE_URL=https://api.example.com を設定する。
 *
 * 各ファイルで `import.meta.env.VITE_API_BASE_URL || ''` を繰り返す代わりに、
 * この定数を使うことで一箇所で管理できる。
 */
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL || ''

/**
 * API サーバー相対パスを、本番では絶対 URL に変換するヘルパー。
 *
 * 用途: backend が返す `/static/screenshots/xxx.png` のような相対パスを
 *       Vercel frontend から正しく参照できるようにする。
 *
 * @example
 *   apiUrl('/static/screenshots/chart.png')
 *   // ローカル → '/static/screenshots/chart.png' (same-origin)
 *   // 本番   → 'https://api.example.com/static/screenshots/chart.png'
 */
export function apiUrl(path: string): string {
  if (!path) return ''
  if (path.startsWith('http://') || path.startsWith('https://')) return path
  return `${API_BASE_URL}${path}`
}

/**
 * タイムアウト付き fetch ヘルパー。
 *
 * 指定ミリ秒を超えると AbortController で自動キャンセルし、
 * ユーザーが長時間待たされるのを防ぐ。
 *
 * @param input  fetch の第1引数 (URL / Request)
 * @param init   fetch の第2引数 (RequestInit)
 * @param timeoutMs タイムアウト (ms)。デフォルト 15 秒。
 */
export async function fetchWithTimeout(
  input: RequestInfo | URL,
  init?: RequestInit,
  timeoutMs = 15_000,
): Promise<Response> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(input, {
      ...init,
      signal: controller.signal,
    })
    return response
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error(`Request timed out after ${timeoutMs}ms`)
    }
    throw err
  } finally {
    clearTimeout(timer)
  }
}

