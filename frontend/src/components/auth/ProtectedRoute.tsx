/**
 * ProtectedRoute
 *
 * 認証・認可ガード用のラッパーコンポーネント。
 *
 * - 未ログイン時は /login にリダイレクト (from state を保持)
 * - allowedRoles を指定するとそのロールのみ通す。不一致なら / にリダイレクト
 * - 認証状態の初期ロード中 (loading=true) は null を返す (画面の瞬間フラッシュを回避)
 *
 * 設計方針:
 * - バックエンド側で role を強制しているので、フロントのガードは UX 向上のみ
 * - 既存のルートを壊さないため、このコンポーネントは「明示的に使う」方式
 *   (App.tsx で必要な Route だけ <ProtectedRoute> でラップする)
 */
import { type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth, type UserRole } from '../../contexts/AuthContext'

interface ProtectedRouteProps {
  children: ReactNode
  /** 指定した場合、このロールを持つユーザーのみアクセス可 (複数OR) */
  allowedRoles?: UserRole[]
  /** ロール不一致時のリダイレクト先 (デフォルト '/') */
  fallback?: string
}

export default function ProtectedRoute({
  children,
  allowedRoles,
  fallback = '/',
}: ProtectedRouteProps) {
  const { user, loading } = useAuth()
  const location = useLocation()

  // 初期ロード中は何も描画しない (未認証と誤判定するのを避ける)
  if (loading) {
    return null
  }

  // 未ログイン → ログイン画面へ (復帰用に from を渡す)
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  // ロール指定ありかつ不一致 → fallback へ
  if (allowedRoles && allowedRoles.length > 0 && !allowedRoles.includes(user.role)) {
    return <Navigate to={fallback} replace />
  }

  return <>{children}</>
}
