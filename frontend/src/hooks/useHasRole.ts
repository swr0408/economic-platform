/**
 * useHasRole - 任意のロールチェック (汎用)
 *
 * 用途:
 *   const isPrivileged = useHasRole('special', 'master')
 *   const isMaster = useHasRole('master')
 *
 * UX 用 (実権限は backend で強制)。
 */
import { useAuth, type UserRole } from '../contexts/AuthContext'

export function useHasRole(...roles: UserRole[]): boolean {
  const { hasRole } = useAuth()
  return hasRole(...roles)
}
