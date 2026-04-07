/**
 * 認証コンテキスト
 *
 * - JWT (Bearer) を localStorage に保持
 * - 同時にバックエンドが httpOnly Cookie (access_token) も併用発行している
 * - 起動時に /api/auth/me で現在ユーザーを取得し整合性を確認
 * - login / register / logout を提供
 *
 * Cookie 併用の理由:
 * - <img src> や <video src> など Authorization ヘッダを送れない経路があるため
 * - すべての fetch / axios 呼び出しに credentials: 'include' を付与し、
 *   Cookie が常に backend に届くようにする
 *
 * 備考:
 * - backend 側で role 判定を強制しているため、frontend の role 表示は UX のみ
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export type UserRole = 'master' | 'special' | 'general'

export interface AuthUser {
  id: number
  username: string
  email: string | null
  role: UserRole
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: AuthUser
}

interface AuthContextValue {
  user: AuthUser | null
  token: string | null
  loading: boolean
  login: (username: string, password: string) => Promise<AuthUser>
  register: (username: string, password: string, email?: string) => Promise<AuthUser>
  logout: () => Promise<void>
  refresh: () => Promise<void>
  hasRole: (...roles: UserRole[]) => boolean
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>
  authFetch: (input: string, init?: RequestInit) => Promise<Response>
}

const TOKEN_KEY = 'auth.token'
const USER_KEY = 'auth.user'

const AuthContext = createContext<AuthContextValue | null>(null)

function readStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

function readStoredUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as AuthUser) : null
  } catch {
    return null
  }
}

function writeStored(token: string | null, user: AuthUser | null) {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token)
    } else {
      localStorage.removeItem(TOKEN_KEY)
    }
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user))
    } else {
      localStorage.removeItem(USER_KEY)
    }
  } catch {
    // ignore quota/permission errors
  }
}

async function postJson<T>(url: string, body: unknown, token?: string | null): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    credentials: 'include',
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const data = await res.json()
      if (data?.detail) detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch {
      /* ignore parse error */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

async function getJson<T>(url: string, token?: string | null): Promise<T> {
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(url, { headers, credentials: 'include' })
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => readStoredToken())
  const [user, setUser] = useState<AuthUser | null>(() => readStoredUser())
  const [loading, setLoading] = useState<boolean>(true)

  // 起動時にトークンの有効性を確認
  useEffect(() => {
    let cancelled = false
    const stored = readStoredToken()
    if (!stored) {
      setLoading(false)
      return
    }
    ;(async () => {
      try {
        const me = await getJson<AuthUser>('/api/auth/me', stored)
        if (!cancelled) {
          setUser(me)
          writeStored(stored, me)
        }
      } catch {
        if (!cancelled) {
          setToken(null)
          setUser(null)
          writeStored(null, null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const data = await postJson<TokenResponse>('/api/auth/login', { username, password })
    setToken(data.access_token)
    setUser(data.user)
    writeStored(data.access_token, data.user)
    return data.user
  }, [])

  const register = useCallback(async (username: string, password: string, email?: string) => {
    const payload: Record<string, unknown> = { username, password }
    if (email && email.trim() !== '') payload.email = email.trim()
    const data = await postJson<TokenResponse>('/api/auth/register', payload)
    setToken(data.access_token)
    setUser(data.user)
    writeStored(data.access_token, data.user)
    return data.user
  }, [])

  const logout = useCallback(async () => {
    // サーバー側で jti ブラックリスト登録して即時失効させる
    const currentToken = readStoredToken()
    if (currentToken) {
      try {
        await fetch('/api/auth/logout', {
          method: 'POST',
          headers: { Authorization: `Bearer ${currentToken}` },
          credentials: 'include',
        })
      } catch {
        /* ネットワーク障害時はローカル破棄だけ行う */
      }
    }
    setToken(null)
    setUser(null)
    writeStored(null, null)
  }, [])

  const refresh = useCallback(async () => {
    const stored = readStoredToken()
    if (!stored) return
    try {
      const me = await getJson<AuthUser>('/api/auth/me', stored)
      setUser(me)
      writeStored(stored, me)
    } catch {
      setToken(null)
      setUser(null)
      writeStored(null, null)
    }
  }, [])

  const hasRole = useCallback(
    (...roles: UserRole[]) => {
      if (!user) return false
      return roles.includes(user.role)
    },
    [user]
  )

  const changePassword = useCallback(
    async (currentPassword: string, newPassword: string) => {
      const currentToken = readStoredToken()
      if (!currentToken) throw new Error('Not authenticated')
      const res = await fetch('/api/auth/change-password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${currentToken}`,
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
        credentials: 'include',
      })
      if (!res.ok) {
        let detail = `HTTP ${res.status}`
        try {
          const data = await res.json()
          if (data?.detail) detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
        } catch {
          /* ignore */
        }
        throw new Error(detail)
      }
      // パスワード変更後は全トークン失効するので、クライアント状態もクリア
      setToken(null)
      setUser(null)
      writeStored(null, null)
    },
    []
  )

  const authFetch = useCallback(
    async (input: string, init?: RequestInit) => {
      const currentToken = readStoredToken()
      const headers = new Headers(init?.headers)
      if (currentToken) headers.set('Authorization', `Bearer ${currentToken}`)
      if (init?.body && !headers.has('Content-Type')) {
        headers.set('Content-Type', 'application/json')
      }
      const res = await fetch(input, {
        ...init,
        headers,
        credentials: init?.credentials ?? 'include',
      })
      // 401 が返ったらローカルのトークンも破棄する (サーバー側 revoke 済み等)
      if (res.status === 401) {
        setToken(null)
        setUser(null)
        writeStored(null, null)
      }
      return res
    },
    []
  )

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      loading,
      login,
      register,
      logout,
      refresh,
      hasRole,
      changePassword,
      authFetch,
    }),
    [user, token, loading, login, register, logout, refresh, hasRole, changePassword, authFetch]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return ctx
}
