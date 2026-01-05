/**
 * React Query クライアント設定
 * ページ読み込み最適化のためのキャッシュ戦略
 */
import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // 1日間は再取得しない（stale状態にならない）
      staleTime: 24 * 60 * 60 * 1000,
      // 1日間キャッシュを保持
      gcTime: 24 * 60 * 60 * 1000,
      // エラー時は2回リトライ
      retry: 2,
      // ウィンドウフォーカス時の自動再取得を無効化
      refetchOnWindowFocus: false,
      // マウント時の再取得を無効化（キャッシュがあれば使う）
      refetchOnMount: false,
      // 再接続時の再取得を無効化
      refetchOnReconnect: false,
    },
  },
})
