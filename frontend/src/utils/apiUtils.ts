/**
 * API呼び出し共通ユーティリティ
 *
 * 各APIモジュールで重複している処理を共通化:
 * - fetch処理
 * - エラーハンドリング
 * - 開発環境でのログ出力
 * - メタ情報の処理
 *
 * 使用例:
 *   import { fetchJson, fetchBlob, logApiMeta } from '@/utils/apiUtils'
 *
 *   // JSONデータ取得
 *   const data = await fetchJson<ResponseType>('/api/example')
 *
 *   // Blob取得（画像など）
 *   const url = await fetchBlob('/api/image')
 */

/**
 * 共通のAPIメタ情報型
 */
export interface ApiMeta {
  cached: boolean
  source?: string
  stale?: boolean
  last_updated: string | null
  response_time_ms: number
  count?: number
  [key: string]: unknown  // 追加のメタ情報用
}

/**
 * 共通のAPIレスポンス型
 */
export interface ApiResponse<T> {
  data: T
  meta: ApiMeta
}

/**
 * APIエラー
 */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public endpoint: string
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/**
 * JSONデータを取得する汎用関数
 *
 * @param endpoint - APIエンドポイント
 * @param options - fetch オプション
 * @returns JSONレスポンス
 * @throws ApiError
 */
export async function fetchJson<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  try {
    const response = await fetch(endpoint, options)

    if (!response.ok) {
      throw new ApiError(
        `HTTP error! status: ${response.status}`,
        response.status,
        endpoint
      )
    }

    return await response.json() as T
  } catch (error) {
    if (error instanceof ApiError) {
      throw error
    }
    console.error(`Error fetching ${endpoint}:`, error)
    throw error
  }
}

/**
 * Blobデータを取得してObject URLを返す汎用関数
 *
 * @param endpoint - APIエンドポイント
 * @param options - fetch オプション
 * @returns Object URL（使用後はURL.revokeObjectURLで解放すること）
 * @throws ApiError
 */
export async function fetchBlob(
  endpoint: string,
  options?: RequestInit
): Promise<string> {
  try {
    const response = await fetch(endpoint, options)

    if (!response.ok) {
      throw new ApiError(
        `HTTP error! status: ${response.status}`,
        response.status,
        endpoint
      )
    }

    const blob = await response.blob()
    return URL.createObjectURL(blob)
  } catch (error) {
    if (error instanceof ApiError) {
      throw error
    }
    console.error(`Error fetching ${endpoint}:`, error)
    throw error
  }
}

/**
 * APIメタ情報をログ出力（開発環境のみ）
 *
 * @param label - ログのラベル
 * @param meta - メタ情報オブジェクト
 */
export function logApiMeta(label: string, meta: ApiMeta | Record<string, unknown>): void {
  if (import.meta.env.DEV) {
    console.log(`${label}:`, meta)
  }
}

/**
 * データとメタ情報を分離して取得
 *
 * @param endpoint - APIエンドポイント
 * @param logLabel - ログ用ラベル（省略時はログなし）
 * @returns [データ配列, メタ情報]
 */
export async function fetchWithMeta<T>(
  endpoint: string,
  logLabel?: string
): Promise<ApiResponse<T>> {
  const response = await fetchJson<ApiResponse<T>>(endpoint)

  if (logLabel) {
    logApiMeta(logLabel, response.meta)
  }

  return response
}

/**
 * データのみを取得（メタ情報はログ出力のみ）
 *
 * @param endpoint - APIエンドポイント
 * @param logLabel - ログ用ラベル
 * @returns データ
 */
export async function fetchData<T>(
  endpoint: string,
  logLabel?: string
): Promise<T> {
  const response = await fetchWithMeta<T>(endpoint, logLabel)
  return response.data
}

/**
 * 名目・実質データ用のレスポンス型
 */
export interface NominalRealData<T> {
  date: string
  mom: number | null
  yoy: number | null
  value?: T
}

export interface NominalRealResponse<T = NominalRealData<number>> {
  nominal: {
    data: T[]
    latest: T | null
  } | null
  real: {
    data: T[]
    latest: T | null
  } | null
  next_release: {
    date: string
    label?: string
  } | null
  cached: boolean
  source: string
  last_updated: string | null
}

/**
 * 名目・実質データを取得
 *
 * @param endpoint - APIエンドポイント
 * @param logLabel - ログ用ラベル
 * @returns NominalRealResponse
 */
export async function fetchNominalRealData<T = NominalRealData<number>>(
  endpoint: string,
  logLabel?: string
): Promise<NominalRealResponse<T>> {
  const response = await fetchJson<NominalRealResponse<T>>(endpoint)

  if (logLabel && import.meta.env.DEV) {
    console.log(`${logLabel}:`, {
      cached: response.cached,
      source: response.source,
      last_updated: response.last_updated,
      nominal_count: response.nominal?.data?.length ?? 0,
      real_count: response.real?.data?.length ?? 0,
    })
  }

  return response
}

/**
 * 単一シリーズデータ用のレスポンス型
 */
export interface SingleSeriesResponse<T> {
  data: T[]
  latest: T | null
  next_release: {
    date: string
    label?: string
  } | null
  cached: boolean
  source: string
  last_updated: string | null
}

/**
 * 単一シリーズデータを取得
 *
 * @param endpoint - APIエンドポイント
 * @param logLabel - ログ用ラベル
 * @returns SingleSeriesResponse
 */
export async function fetchSingleSeriesData<T>(
  endpoint: string,
  logLabel?: string
): Promise<SingleSeriesResponse<T>> {
  const response = await fetchJson<SingleSeriesResponse<T>>(endpoint)

  if (logLabel && import.meta.env.DEV) {
    console.log(`${logLabel}:`, {
      cached: response.cached,
      source: response.source,
      last_updated: response.last_updated,
      count: response.data?.length ?? 0,
    })
  }

  return response
}
