const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

// ========== Auth helper ==========
// Headlines/Categories API は master 化されているため、すべてのリクエストに
// Bearer トークンを付与する必要がある。AuthContext と同じ localStorage キーを参照。
const TOKEN_KEY = 'auth.token'

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...(extra || {}) }
  try {
    const token = localStorage.getItem(TOKEN_KEY)
    if (token) headers['Authorization'] = `Bearer ${token}`
  } catch {
    /* ignore */
  }
  return headers
}

// ========== Types ==========

export interface Headline {
  id: number
  source_type: string
  headline_raw: string
  headline_ja: string | null
  normalized_text: string | null
  rough_category: string | null
  speaker_name: string | null
  organization: string | null
  translation_status: string
  external_link: string | null
  embed_title: string | null
  embed_description: string | null
  embed_title_ja: string | null
  embed_description_ja: string | null
  published_at: string | null
  created_at: string
  expires_at: string | null
  saved_categories?: SavedCategory[]
}

export interface SavedCategory {
  saved_id: number
  category_id: number
  category_name: string
  category_color: string
  category_parent_id: number | null
  note: string | null
  saved_at: string
}

export interface HeadlinesResponse {
  items: Headline[]
  total: number
  limit: number
  offset: number
}

export interface Category {
  id: number
  name: string
  color: string
  sort_order: number
  parent_id: number | null
  headline_count: number
  created_at: string
}

export interface AdminStatus {
  discord: {
    is_running: boolean
    is_connected: boolean
    guild_count?: number
    last_message_at?: string
  }
  rss: {
    is_running: boolean
    last_fetch_at: string | null
    last_items_seen: number
    last_items_inserted: number
  }
  translation: {
    is_running: boolean
    pending_count: number
    failed_count: number
  }
}

export interface RSSLog {
  id: number
  http_status: number
  etag: string | null
  last_modified: string | null
  items_seen: number
  items_inserted: number
  items_deduped: number
  fetched_at: string
}

// ========== Headlines API ==========

export interface HeadlinesParams {
  limit?: number
  offset?: number
  source?: string
  roughCategory?: string
  speaker?: string
  savedOnly?: boolean
  savedCategoryName?: string
  savedCategoryId?: number
  savedCategoryPrefix?: string
  from?: string
  to?: string
  q?: string
}

export async function fetchHeadlines(params: HeadlinesParams = {}): Promise<HeadlinesResponse> {
  const searchParams = new URLSearchParams()
  if (params.limit) searchParams.set('limit', String(params.limit))
  if (params.offset) searchParams.set('offset', String(params.offset))
  if (params.source) searchParams.set('source', params.source)
  if (params.roughCategory) searchParams.set('roughCategory', params.roughCategory)
  if (params.speaker) searchParams.set('speaker', params.speaker)
  if (params.savedOnly) searchParams.set('savedOnly', 'true')
  if (params.savedCategoryName) searchParams.set('savedCategoryName', params.savedCategoryName)
  if (params.savedCategoryId) searchParams.set('savedCategoryId', String(params.savedCategoryId))
  if (params.savedCategoryPrefix) searchParams.set('savedCategoryPrefix', params.savedCategoryPrefix)
  if (params.from) searchParams.set('from', params.from)
  if (params.to) searchParams.set('to', params.to)
  if (params.q) searchParams.set('q', params.q)

  const resp = await fetch(`${API_BASE_URL}/api/headlines?${searchParams}`, {
    headers: authHeaders(),
  })
  if (!resp.ok) throw new Error(`Failed to fetch headlines: ${resp.status}`)
  return resp.json()
}

export async function fetchHeadlineById(id: number): Promise<Headline> {
  const resp = await fetch(`${API_BASE_URL}/api/headlines/${id}`, {
    headers: authHeaders(),
  })
  if (!resp.ok) throw new Error(`Failed to fetch headline: ${resp.status}`)
  return resp.json()
}

// ========== Public headlines (general/special/master) ==========

export async function fetchPublicHeadlines(params: {
  limit?: number
  offset?: number
  categoryId?: number
} = {}): Promise<{ items: any[]; total: number; limit: number; offset: number }> {
  const searchParams = new URLSearchParams()
  if (params.limit) searchParams.set('limit', String(params.limit))
  if (params.offset) searchParams.set('offset', String(params.offset))
  if (params.categoryId) searchParams.set('category_id', String(params.categoryId))

  const resp = await fetch(`${API_BASE_URL}/api/headlines/public?${searchParams}`, {
    headers: authHeaders(),
  })
  if (!resp.ok) throw new Error(`Failed to fetch public headlines: ${resp.status}`)
  return resp.json()
}

// ========== Save / Unsave ==========

export interface SaveHeadlineParams {
  categoryIds?: number[]
  newCategoryName?: string
  note?: string
  isPublicVisible?: boolean
}

export async function saveHeadline(headlineId: number, params: SaveHeadlineParams): Promise<any> {
  const resp = await fetch(`${API_BASE_URL}/api/headlines/${headlineId}/save`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(params),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to save headline: ${resp.status}`)
  }
  return resp.json()
}

export async function unsaveHeadline(headlineId: number, savedId: number): Promise<void> {
  const resp = await fetch(`${API_BASE_URL}/api/headlines/${headlineId}/save/${savedId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!resp.ok) throw new Error(`Failed to unsave headline: ${resp.status}`)
}

export async function retranslateHeadline(headlineId: number): Promise<void> {
  const resp = await fetch(`${API_BASE_URL}/api/headlines/${headlineId}/retranslate`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!resp.ok) throw new Error(`Failed to retranslate headline: ${resp.status}`)
}

// ========== Categories ==========

export async function fetchCategories(): Promise<Category[]> {
  const resp = await fetch(`${API_BASE_URL}/api/categories`, {
    headers: authHeaders(),
  })
  if (!resp.ok) throw new Error(`Failed to fetch categories: ${resp.status}`)
  return resp.json()
}

export async function createCategory(name: string, color: string = '#3b82f6', parent_id?: number): Promise<Category> {
  const resp = await fetch(`${API_BASE_URL}/api/categories`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ name, color, parent_id }),
  })
  if (!resp.ok) throw new Error(`Failed to create category: ${resp.status}`)
  return resp.json()
}

export async function updateCategory(
  id: number,
  params: { name?: string; color?: string; sort_order?: number }
): Promise<void> {
  const resp = await fetch(`${API_BASE_URL}/api/categories/${id}`, {
    method: 'PATCH',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(params),
  })
  if (!resp.ok) throw new Error(`Failed to update category: ${resp.status}`)
}

export async function deleteCategory(id: number): Promise<void> {
  const resp = await fetch(`${API_BASE_URL}/api/categories/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!resp.ok) throw new Error(`Failed to delete category: ${resp.status}`)
}

// ========== Admin ==========

export async function fetchAdminStatus(): Promise<AdminStatus> {
  const resp = await fetch(`${API_BASE_URL}/api/admin/status`, {
    headers: authHeaders(),
  })
  if (!resp.ok) throw new Error(`Failed to fetch admin status: ${resp.status}`)
  return resp.json()
}

export async function runRSSBackfill(): Promise<any> {
  const resp = await fetch(`${API_BASE_URL}/api/admin/rss-backfill/run`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!resp.ok) throw new Error(`Failed to run RSS backfill: ${resp.status}`)
  return resp.json()
}

export async function fetchRSSLogs(limit: number = 20): Promise<RSSLog[]> {
  const resp = await fetch(`${API_BASE_URL}/api/admin/rss-backfill/logs?limit=${limit}`, {
    headers: authHeaders(),
  })
  if (!resp.ok) throw new Error(`Failed to fetch RSS logs: ${resp.status}`)
  return resp.json()
}

export async function seedCategories(): Promise<Category[]> {
  const resp = await fetch(`${API_BASE_URL}/api/admin/seed-categories`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!resp.ok) throw new Error(`Failed to seed categories: ${resp.status}`)
  return resp.json()
}
