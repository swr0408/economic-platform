/**
 * ダッシュボードコンテナ共通コンポーネント
 *
 * ローディング状態、エラー状態、スケルトンローダーを共通化
 */
import React from 'react'
import { Spin, Alert, Button } from 'antd'
import { UseQueryResult } from '@tanstack/react-query'
import type { DashboardResponse } from '../../../../hooks/useDashboardData'
import { DARK_THEME, TEXT_COLORS } from './chartConstants'

// =============================================================================
// 型定義
// =============================================================================

interface DashboardContainerProps<T> {
  /** React QueryのuseQueryの結果 */
  queryResult: UseQueryResult<DashboardResponse<T>, Error>
  /** カテゴリ名（ローディング表示用） */
  categoryName: string
  /** 子コンポーネント（レンダープロップ） */
  children: (data: T) => React.ReactNode
}

// =============================================================================
// スケルトンローダー
// =============================================================================

interface DashboardSkeletonProps {
  message: string
}

export function DashboardSkeleton({ message }: DashboardSkeletonProps) {
  return (
    <div className="country-chart-stack">
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: 400,
          background: DARK_THEME.bgSecondary,
          borderRadius: 12,
        }}
      >
        <Spin size="large" />
        <div style={{ marginTop: 16, color: TEXT_COLORS.secondary }}>{message}</div>
      </div>
    </div>
  )
}

// =============================================================================
// エラー表示
// =============================================================================

interface DashboardErrorProps {
  error: Error
  onRetry: () => void
}

export function DashboardError({ error, onRetry }: DashboardErrorProps) {
  return (
    <Alert
      type="error"
      message="データの取得に失敗しました"
      description={error.message}
      action={
        <Button size="small" onClick={onRetry}>
          再試行
        </Button>
      }
      style={{ marginBottom: 24 }}
    />
  )
}

// =============================================================================
// DashboardContainer
// =============================================================================

export function DashboardContainer<T>({
  queryResult,
  categoryName,
  children,
}: DashboardContainerProps<T>) {
  const { data, isLoading, error, refetch } = queryResult

  // ローディング状態
  if (isLoading) {
    return <DashboardSkeleton message={`${categoryName}データを読み込み中...`} />
  }

  // エラー状態
  if (error) {
    return <DashboardError error={error} onRetry={() => refetch()} />
  }

  // データがない場合
  if (!data?.data) {
    return <DashboardSkeleton message={`${categoryName}データがありません`} />
  }

  // 正常時は子コンポーネントをレンダリング
  return <div className="country-chart-stack">{children(data.data)}</div>
}

// =============================================================================
// ChartWrapper - チャートをラップするコンポーネント
// =============================================================================

interface ChartWrapperProps {
  id: string
  children: React.ReactNode
}

export function ChartWrapper({ id, children }: ChartWrapperProps) {
  return <div id={id}>{children}</div>
}

export default DashboardContainer
