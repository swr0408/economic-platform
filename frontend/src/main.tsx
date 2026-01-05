import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider, theme } from 'antd'
import jaJP from 'antd/locale/ja_JP'
import { queryClient } from './lib/queryClient'
import App from './App'
import 'flag-icons/css/flag-icons.min.css'
import './styles/index.css'

// Axios グローバル設定をインポート（タイムアウト、インターセプター）
import './utils/axiosConfig'

// EconAlpha ダークテーマ設定
const econAlphaTheme = {
  algorithm: theme.darkAlgorithm,
  token: {
    // プライマリカラー（ティール系）
    colorPrimary: '#10b981',
    colorLink: '#10b981',
    colorLinkHover: '#34d399',
    // 背景色（Slate系ダーク）
    colorBgContainer: '#1e293b',
    colorBgElevated: '#334155',
    colorBgLayout: '#0f172a',
    colorBgSpotlight: '#1e293b',
    // ボーダー
    colorBorder: '#334155',
    colorBorderSecondary: '#475569',
    // テキスト
    colorText: '#f1f5f9',
    colorTextSecondary: '#94a3b8',
    colorTextTertiary: '#64748b',
    colorTextQuaternary: '#475569',
    // サクセス/エラー/警告
    colorSuccess: '#10b981',
    colorError: '#ef4444',
    colorWarning: '#f59e0b',
    colorInfo: '#3b82f6',
    // ボーダー半径
    borderRadius: 8,
    // フォント
    fontFamily: "'Inter', 'Noto Sans JP', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
  },
  components: {
    Layout: {
      headerBg: '#0f172a',
      siderBg: '#1e293b',
      bodyBg: '#0f172a',
    },
    Menu: {
      darkItemBg: '#1e293b',
      darkSubMenuItemBg: '#0f172a',
      darkItemSelectedBg: '#10b981',
      darkItemHoverBg: '#334155',
    },
    Card: {
      colorBgContainer: '#1e293b',
      colorBorderSecondary: '#334155',
    },
    Table: {
      colorBgContainer: '#1e293b',
      headerBg: '#334155',
    },
    Button: {
      primaryColor: '#0f172a',
    },
  },
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ConfigProvider locale={jaJP} theme={econAlphaTheme}>
        <App />
      </ConfigProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
