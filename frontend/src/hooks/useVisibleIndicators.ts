/**
 * useVisibleIndicators / useCanSeeIndicator
 *
 * GET /api/compare/candidates から「このロールでは見られない indicator_code 一覧」を取得し、
 * - 単体判定 (useCanSeeIndicator)
 * - 一覧フィルタ (useVisibleIndicators)
 * を提供する。
 *
 * 制御の本体は backend (ReadVisibilityGuardMiddleware)。これは UI 表示制御 / 候補除外用。
 *
 * 5 分メモリキャッシュ + 失敗時はフェイルオープン (全部見える扱い)。
 */
import { useEffect, useState, useMemo } from 'react'
import { useAuth } from '../contexts/AuthContext'

interface CandidatesResponse {
  role: string
  blocked_codes: string[]
}

let _cache: { at: number; data: CandidatesResponse } | null = null
const CACHE_TTL_MS = 5 * 60 * 1000

async function fetchBlocked(authFetch: (u: string) => Promise<Response>): Promise<CandidatesResponse> {
  const now = Date.now()
  if (_cache && now - _cache.at < CACHE_TTL_MS) {
    return _cache.data
  }
  try {
    const res = await authFetch('/api/compare/candidates')
    if (!res.ok) {
      // フェイルオープン
      return { role: 'general', blocked_codes: [] }
    }
    const data = (await res.json()) as CandidatesResponse
    _cache = { at: now, data }
    return data
  } catch {
    return { role: 'general', blocked_codes: [] }
  }
}

/**
 * blocked_codes の Set を返す薄いフック (ComparePopover などが参照).
 *
 * 5 分メモリキャッシュを共有し、未ログイン時は空集合 (= 全部見える) を返す。
 */
export function useBlockedIndicatorCodes(): Set<string> {
  const { authFetch, user } = useAuth()
  const [blocked, setBlocked] = useState<Set<string>>(() => new Set(_cache?.data.blocked_codes || []))

  useEffect(() => {
    if (!user) {
      setBlocked(new Set())
      return
    }
    let cancelled = false
    fetchBlocked((u) => authFetch(u)).then((d) => {
      if (!cancelled) setBlocked(new Set(d.blocked_codes))
    })
    return () => {
      cancelled = true
    }
  }, [authFetch, user])

  return blocked
}

/** ロールが指定 indicator_code を見られるか */
export function useCanSeeIndicator(indicatorCode: string | null | undefined): boolean {
  const { authFetch, user } = useAuth()
  const [blocked, setBlocked] = useState<Set<string>>(() => new Set(_cache?.data.blocked_codes || []))

  useEffect(() => {
    if (!user) return
    let cancelled = false
    fetchBlocked((u) => authFetch(u)).then((d) => {
      if (!cancelled) setBlocked(new Set(d.blocked_codes))
    })
    return () => {
      cancelled = true
    }
  }, [authFetch, user])

  if (!indicatorCode) return true
  return !blocked.has(indicatorCode)
}

/** 候補リストから「見られない」ものを除外 */
export function useVisibleIndicators<T extends { code?: string; indicator_code?: string }>(
  items: T[]
): T[] {
  const { authFetch, user } = useAuth()
  const [blocked, setBlocked] = useState<Set<string>>(() => new Set(_cache?.data.blocked_codes || []))

  useEffect(() => {
    if (!user) return
    let cancelled = false
    fetchBlocked((u) => authFetch(u)).then((d) => {
      if (!cancelled) setBlocked(new Set(d.blocked_codes))
    })
    return () => {
      cancelled = true
    }
  }, [authFetch, user])

  return useMemo(() => {
    if (blocked.size === 0) return items
    return items.filter((it) => {
      const code = it.code ?? it.indicator_code
      return !code || !blocked.has(code)
    })
  }, [items, blocked])
}

/** 強制再フェッチ用 (admin が visibility を変えた直後など) */
export function invalidateVisibilityCache(): void {
  _cache = null
}

/** 後方互換: useIsPrivileged エイリアス */
export function useIsPrivileged(): boolean {
  const { hasRole } = useAuth()
  return hasRole('special', 'master')
}
