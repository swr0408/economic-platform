import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchHeadlines, fetchHeadlineById, saveHeadline, unsaveHeadline,
  retranslateHeadline, fetchCategories, createCategory, updateCategory,
  deleteCategory, fetchAdminStatus, runRSSBackfill, fetchRSSLogs,
  type HeadlinesParams, type SaveHeadlineParams,
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
    mutationFn: ({ name, color }: { name: string; color?: string }) =>
      createCategory(name, color),
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
