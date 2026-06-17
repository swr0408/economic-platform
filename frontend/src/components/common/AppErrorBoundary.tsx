import { Component, type ReactNode, type ErrorInfo } from 'react'

/**
 * アプリ全体を保護するトップレベル ErrorBoundary。
 *
 * 目的:
 * - これが無いと、どこか1コンポーネントの描画エラーでツリー全体が unmount され
 *   「画面が真っ暗 (ブランク)」になる。本コンポーネントでエラーを捕捉し、
 *   ブランク化を防いで原因を画面に表示する。
 * - 表示されたエラーメッセージ / スタックがそのまま原因調査の手がかりになる。
 *
 * 配置: providers より外側 (App の最上位) に置き、provider を含む全描画エラーを捕捉する。
 * router 外なので遷移は window.location を使う。
 */
interface State {
  hasError: boolean
  error: Error | null
  info: ErrorInfo | null
}

const colors = {
  bgPrimary: '#0f172a',
  bgSecondary: '#1e293b',
  border: '#334155',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  accent: '#10b981',
  danger: '#ef4444',
}

export default class AppErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { hasError: false, error: null, info: null }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // コンソールにも残す (本番でも開発でも調査できるように)
    console.error('[AppErrorBoundary] Uncaught render error:', error, info)
    this.setState({ info })
  }

  private handleReload = () => {
    window.location.reload()
  }

  private handleHome = () => {
    window.location.href = '/'
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <div
        style={{
          minHeight: '100vh',
          background: colors.bgPrimary,
          color: colors.textPrimary,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 24,
          boxSizing: 'border-box',
        }}
      >
        <div
          style={{
            maxWidth: 720,
            width: '100%',
            background: colors.bgSecondary,
            border: `1px solid ${colors.border}`,
            borderRadius: 12,
            padding: 24,
          }}
        >
          <h2 style={{ marginTop: 0, color: colors.danger }}>画面の描画でエラーが発生しました</h2>
          <p style={{ color: colors.textSecondary }}>
            一時的な問題の可能性があります。まず「再読み込み」をお試しください。
            繰り返す場合は、下記のエラー内容を開発者に共有してください。
          </p>

          <div style={{ display: 'flex', gap: 12, margin: '16px 0' }}>
            <button
              onClick={this.handleReload}
              style={{
                background: colors.accent,
                color: '#0b1220',
                border: 'none',
                borderRadius: 8,
                padding: '8px 16px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              再読み込み
            </button>
            <button
              onClick={this.handleHome}
              style={{
                background: 'transparent',
                color: colors.textPrimary,
                border: `1px solid ${colors.border}`,
                borderRadius: 8,
                padding: '8px 16px',
                cursor: 'pointer',
              }}
            >
              ホームへ
            </button>
          </div>

          <pre
            style={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              background: colors.bgPrimary,
              border: `1px solid ${colors.border}`,
              borderRadius: 8,
              padding: 12,
              fontSize: 12,
              color: colors.textSecondary,
              maxHeight: 320,
              overflow: 'auto',
              margin: 0,
            }}
          >
            {this.state.error?.message || 'Unknown error'}
            {this.state.error?.stack ? `\n\n${this.state.error.stack}` : ''}
            {this.state.info?.componentStack
              ? `\n\n--- component stack ---${this.state.info.componentStack}`
              : ''}
          </pre>
        </div>
      </div>
    )
  }
}
