/**
 * useCanView - 指標 visibility に応じて現在のユーザーが閲覧可能か返すフック
 *
 * 重要: EconAlpha は会員制サイトで、未ログインユーザーは一切閲覧できない。
 * したがって 'public' は「未認証公開」ではなく「ログイン済み一般ユーザー向け公開」を指す。
 *
 * visibility の意味:
 *   - undefined / 'public': ログイン済みなら誰でも閲覧可 (general / special / master)
 *   - 'special': special / master のみ閲覧可
 *   - 'master':  master のみ閲覧可
 *
 * 未ログイン (role が undefined) の場合は visibility に関わらず常に false。
 *
 * 用途:
 * - サイドバーのメニュー項目を visibility に応じてフィルタする
 * - スクリーンショット系チャートを未認可ユーザに対して非表示にする
 *
 * 注意:
 * - これはあくまで UI 表示制御。実際の権限強制は backend
 *   (ReadVisibilityGuardMiddleware / WriteOperationGuardMiddleware) が担当する
 * - role と visibility の対応は backend の services/visibility/visibility_service.py
 *   の階層と完全に揃えること
 */
import { useCallback } from 'react'
import { useAuth, type UserRole } from '../contexts/AuthContext'
import type { IndicatorVisibility } from '../constants/countryData'

/**
 * visibility と user role を受け取り、閲覧可能か判定 (純関数)。
 * テストや非フックコンテキストから直接呼べる。
 */
export function canViewVisibility(
  visibility: IndicatorVisibility | undefined,
  role: UserRole | undefined,
): boolean {
  // 未ログインは visibility に関わらず一切閲覧不可 (会員制サイト)
  if (!role) return false

  // public (= visibility 未指定) はログイン済みなら誰でも見られる
  if (!visibility) return true

  if (visibility === 'master') {
    return role === 'master'
  }
  if (visibility === 'special') {
    return role === 'master' || role === 'special'
  }
  return false
}

/**
 * 単一の visibility に対する閲覧可否を返すフック。
 *
 * @example
 *   const canView = useCanView('special')
 *   if (!canView) return null
 */
export function useCanView(visibility: IndicatorVisibility | undefined): boolean {
  const { user } = useAuth()
  return canViewVisibility(visibility, user?.role)
}

/**
 * 任意の visibility に対する判定関数を返すフック。
 * 複数の指標をループで判定したい時 (サイドバー等) はこちらが便利。
 *
 * @example
 *   const canView = useCanViewFn()
 *   indicators.filter(i => canView(i.visibility))
 */
export function useCanViewFn(): (visibility: IndicatorVisibility | undefined) => boolean {
  const { user } = useAuth()
  return useCallback(
    (visibility: IndicatorVisibility | undefined) =>
      canViewVisibility(visibility, user?.role),
    [user?.role],
  )
}
