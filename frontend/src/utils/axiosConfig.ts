/**
 * Axios グローバル設定
 *
 * - デフォルトタイムアウト設定
 * - リクエストキャンセル機能
 * - httpOnly Cookie 併用 (withCredentials)
 * - localStorage の Bearer token を全リクエストに自動付与
 */
import axios from 'axios'

// デフォルトタイムアウト（60秒）
axios.defaults.timeout = 60000

// すべての axios リクエストに Cookie を載せる
// (httpOnly access_token Cookie を併用するため)
axios.defaults.withCredentials = true

// localStorage から Bearer token を読むキー (AuthContext と一致させる)
const AUTH_TOKEN_STORAGE_KEY = 'auth.token'

function readAuthToken(): string | null {
  try {
    return localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
  } catch {
    return null
  }
}

// リクエストインターセプター
axios.interceptors.request.use(
  (config) => {
    // Bearer token を Authorization ヘッダに自動付与
    // (既に設定済みの場合は上書きしない)
    const headers = config.headers ?? {}
    const hasAuth =
      typeof (headers as Record<string, unknown>).Authorization !== 'undefined' ||
      typeof (headers as Record<string, unknown>).authorization !== 'undefined'
    if (!hasAuth) {
      const token = readAuthToken()
      if (token) {
        ;(headers as Record<string, string>).Authorization = `Bearer ${token}`
        config.headers = headers
      }
    }

    // DEV環境でリクエストをログ
    if (import.meta.env.DEV) {
      console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`)
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// レスポンスインターセプター
axios.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    // キャンセルされたリクエストはエラーとして扱わない
    if (axios.isCancel(error)) {
      console.log('[API] Request cancelled:', error.message)
      return Promise.reject(error)
    }

    // タイムアウトエラー
    if (error.code === 'ECONNABORTED') {
      console.warn('[API] Request timeout:', error.config?.url)
    }

    return Promise.reject(error)
  }
)

export default axios
