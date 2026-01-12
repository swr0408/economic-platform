/**
 * 日銀貸出動向 API クライアント
 *
 * エンドポイント:
 * - GET /api/japan/boj-lending - 貸出動向データ取得
 * - GET /api/japan/boj-lending/cache-status - キャッシュステータス取得
 * - POST /api/japan/boj-lending/refresh - データ強制更新
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface BOJLendingDataPoint {
  date: string; // YYYY-MM format
  value: number; // 億円
}

export interface BOJLendingResponse {
  data: BOJLendingDataPoint[];
  latest: BOJLendingDataPoint | null;
  cached: boolean;
  source: string;
  last_updated: string | null;
  error?: string;
}

export interface BOJLendingCacheStatus {
  indicator: string;
  source: string;
  data_code: string;
  cache_key: string;
  exists: boolean;
  last_updated: string | null;
  data_count: number;
  file_cache_exists: boolean;
  last_update_month: string | null;
}

/**
 * 日銀貸出動向データを取得（生データ、億円単位）
 *
 * @param forceRefresh キャッシュを無視して強制更新
 * @returns 貸出動向データ
 */
export async function fetchBOJLendingData(
  forceRefresh: boolean = false
): Promise<BOJLendingResponse> {
  const params = new URLSearchParams();
  if (forceRefresh) {
    params.append('force_refresh', 'true');
  }

  const url = `${API_BASE_URL}/api/japan/boj-lending${params.toString() ? '?' + params.toString() : ''}`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch BOJ Lending data: ${response.status}`);
  }

  return response.json();
}

/**
 * 日銀貸出動向データを取得（前年比、%単位）
 *
 * @param forceRefresh キャッシュを無視して強制更新
 * @returns 貸出動向データ（前年比）
 */
export async function fetchBOJLendingYoYData(
  forceRefresh: boolean = false
): Promise<BOJLendingResponse> {
  const params = new URLSearchParams();
  if (forceRefresh) {
    params.append('force_refresh', 'true');
  }

  const url = `${API_BASE_URL}/api/japan/boj-lending/yoy${params.toString() ? '?' + params.toString() : ''}`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch BOJ Lending YoY data: ${response.status}`);
  }

  return response.json();
}

/**
 * キャッシュステータスを取得
 *
 * @returns キャッシュの状態情報
 */
export async function fetchBOJLendingCacheStatus(): Promise<BOJLendingCacheStatus> {
  const url = `${API_BASE_URL}/api/japan/boj-lending/cache-status`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch cache status: ${response.status}`);
  }

  return response.json();
}

/**
 * データを強制更新
 *
 * @returns 更新結果
 */
export async function refreshBOJLendingData(): Promise<{
  status: string;
  data_count: number;
  latest: BOJLendingDataPoint | null;
  last_updated: string | null;
}> {
  const url = `${API_BASE_URL}/api/japan/boj-lending/refresh`;

  const response = await fetch(url, { method: 'POST' });
  if (!response.ok) {
    throw new Error(`Failed to refresh data: ${response.status}`);
  }

  return response.json();
}
