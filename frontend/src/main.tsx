import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider } from 'antd'
import jaJP from 'antd/locale/ja_JP'
import { queryClient } from './lib/queryClient'
import App from './App'
import 'flag-icons/css/flag-icons.min.css'
import './styles/index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ConfigProvider locale={jaJP}>
        <App />
      </ConfigProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
