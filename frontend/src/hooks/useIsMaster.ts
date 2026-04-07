/**
 * useIsMaster - 現在のユーザーが master ロールかどうかを返す薄いフック
 *
 * 用途:
 * - 更新ボタン等の master 限定 UI を条件レンダリングするためのヘルパー
 * - `useAuth().hasRole('master')` の薄いラッパー
 *
 * 注意:
 * - これはあくまで UI 表示制御のためのヒューリスティック
 * - 実際の権限強制は backend (WriteOperationGuardMiddleware + 個別 require_role) が担当する
 */
import { useAuth } from '../contexts/AuthContext'

export function useIsMaster(): boolean {
  const { hasRole } = useAuth()
  return hasRole('master')
}
