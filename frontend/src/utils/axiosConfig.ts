/**
 * Axios グローバル設定
 *
 * - デフォルトタイムアウト設定
 * - リクエストキャンセル機能
 */
import axios from 'axios'

// デフォルトタイムアウト（60秒）
axios.defaults.timeout = 60000

// リクエストインターセプター
axios.interceptors.request.use(
  (config) => {
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
