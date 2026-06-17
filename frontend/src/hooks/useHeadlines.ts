import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchHeadlines, fetchHeadlineById, saveHeadline, unsaveHeadline,
  createManualHeadline,
  retranslateHeadline, fetchCategories, createCategory, updateCategory,
  deleteCategory, fetchAdminStatus, runRSSBackfill, fetchRSSLogs,
  seedCategories,
  fetchReadMarker, setReadMarker, clearReadMarker,
  reorderSavedHeadlines, reorderSidebarEntries,
  type HeadlinesParams, type SaveHeadlineParams, type ManualHeadlineParams,
  type HeadlinesResponse, type SidebarOrderEntry, type Category,
} from '../api/headlinesApi'

// ========== Headlines ==========

export function useHeadlines(params: HeadlinesParams = {}) {
  return useQuery({
    queryKey: ['headlines', params],
    queryFn: () => fetchHeadlines(params),
    refetchInterval: 30_000,
  })
}

export function useHeadlineDetail(id: number | null) {
  return useQuery({
    queryKey: ['headline', id],
    queryFn: () => fetchHeadlineById(id!),
    enabled: id !== null,
  })
}

// ========== Save / Unsave ==========

export function useSaveHeadline() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ headlineId, params }: { headlineId: number; params: SaveHeadlineParams }) =>
      saveHeadline(headlineId, params),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['headlines'] })
      qc.invalidateQueries({ queryKey: ['headline'] })
      qc.invalidateQueries({ queryKey: ['categories'] })
    },
  })
}

export function useCreateManualHeadline() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: ManualHeadlineParams) => createManualHeadline(params),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['headlines'] })
      qc.invalidateQueries({ queryKey: ['headline'] })
      qc.invalidateQueries({ queryKey: ['categories'] })
    },
  })
}

export function useUnsaveHeadline() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ headlineId, savedId }: { headlineId: number; savedId: number }) =>
      unsaveHeadline(headlineId, savedId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['headlines'] })
      qc.invalidateQueries({ queryKey: ['headline'] })
      qc.invalidateQueries({ queryKey: ['categories'] })
    },
  })
}

export function useRetranslate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (headlineId: number) => retranslateHeadline(headlineId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['headlines'] })
      qc.invalidateQueries({ queryKey: ['headline'] })
    },
  })
}

// ========== Saved headline reorder (master only) ==========

export function useReorderSavedHeadlines() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ categoryId, savedIds }: { categoryId: number; savedIds: number[] }) =>
      reorderSavedHeadlines(categoryId, savedIds),
    // 楽観的更新: キャッシュ上の sort_order を即時書き換えてドロップ直後に並びを反映
    onMutate: async ({ categoryId, savedIds }) => {
      await qc.cancelQueries({ queryKey: ['headlines'] })
      const orderMap = new Map(savedIds.map((id, idx) => [id, idx]))
      qc.setQueriesData<HeadlinesResponse>({ queryKey: ['headlines'] }, old => {
        if (!old?.items) return old
        return {
          ...old,
          items: old.items.map(item => ({
            ...item,
            saved_categories: item.saved_categories?.map(sc =>
              sc.category_id === categoryId && orderMap.has(sc.saved_id)
                ? { ...sc, sort_order: orderMap.get(sc.saved_id)! }
                : sc
            ),
          })),
        }
      })
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['headlines'] })
    },
  })
}

export function useReorderSidebarEntries() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ entries }: { entries: SidebarOrderEntry[] }) => reorderSidebarEntries(entries),
    // 楽観的更新: saved_headlines.sort_order と categories.sort_order の両キャッシュを即時反映
    onMutate: async ({ entries }) => {
      await qc.cancelQueries({ queryKey: ['headlines'] })
      await qc.cancelQueries({ queryKey: ['categories'] })
      const savedOrder = new Map(entries.filter(e => e.type === 'saved').map(e => [e.id, e.sortOrder]))
      const catOrder = new Map(entries.filter(e => e.type === 'category').map(e => [e.id, e.sortOrder]))
      qc.setQueriesData<HeadlinesResponse>({ queryKey: ['headlines'] }, old => {
        if (!old?.items) return old
        return {
          ...old,
          items: old.items.map(item => ({
            ...item,
            saved_categories: item.saved_categories?.map(sc =>
              savedOrder.has(sc.saved_id)
                ? { ...sc, sort_order: savedOrder.get(sc.saved_id)! }
                : sc
            ),
          })),
        }
      })
      qc.setQueryData<Category[]>(['categories'], old =>
        old?.map(c => (catOrder.has(c.id) ? { ...c, sort_order: catOrder.get(c.id)! } : c))
      )
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['headlines'] })
      qc.invalidateQueries({ queryKey: ['categories'] })
    },
  })
}

// ========== Read marker 「ここまで見た」 (master only) ==========

export function useReadMarker(enabled: boolean = true) {
  return useQuery({
    queryKey: ['read-marker'],
    queryFn: fetchReadMarker,
    enabled,
  })
}

export function useSetReadMarker() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (headlineId: number) => setReadMarker(headlineId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['read-marker'] })
    },
  })
}

export function useClearReadMarker() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: clearReadMarker,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['read-marker'] })
    },
  })
}

// ========== Categories ==========

export function useCategories() {
  return useQuery({
    queryKey: ['categories'],
    queryFn: fetchCategories,
  })
}

export function useCreateCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, color, parent_id }: { name: string; color?: string; parent_id?: number }) =>
      createCategory(name, color, parent_id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['categories'] })
    },
  })
}

export function useUpdateCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, params }: { id: number; params: { name?: string; color?: string; sort_order?: number } }) =>
      updateCategory(id, params),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['categories'] })
    },
  })
}

export function useDeleteCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteCategory(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['categories'] })
      qc.invalidateQueries({ queryKey: ['headlines'] })
    },
  })
}

// ========== Admin ==========

export function useAdminStatus() {
  return useQuery({
    queryKey: ['admin-status'],
    queryFn: fetchAdminStatus,
    refetchInterval: 10_000,
  })
}

export function useRunRSSBackfill() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: runRSSBackfill,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-status'] })
      qc.invalidateQueries({ queryKey: ['rss-logs'] })
    },
  })
}

export function useRSSLogs(limit: number = 20) {
  return useQuery({
    queryKey: ['rss-logs', limit],
    queryFn: () => fetchRSSLogs(limit),
  })
}

export function useSeedCategories() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: seedCategories,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['categories'] })
    },
  })
}
