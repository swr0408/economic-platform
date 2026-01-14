/**
 * 設備投資 API クライアント
 *
 * エンドポイント:
 * - GET /api/japan/capital-investment - 設備投資データ取得
 * - GET /api/japan/capital-investment/yoy - 前年比データ取得
 * - GET /api/japan/capital-investment/cache-status - キャッシュステータス取得
 * - POST /api/japan/capital-investment/refresh - データ強制更新
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface NextRelease {
  date: string;
  datetime_utc?: string;
  datetime_jst?: string;
  time_jst?: string;
  label?: string;
}

export interface CapitalInvestmentDataPoint {
  date: string; // YYYY-Qn format
  value: number; // 百万円
  unit?: string;
  qoq_growth?: number | null; // 前期比 %
  yoy_growth?: number | null; // 前年比 %
}

export interface CapitalInvestmentResponse {
  data: CapitalInvestmentDataPoint[];
  latest: CapitalInvestmentDataPoint | null;
  next_release?: NextRelease | null;
  cached: boolean;
  source: string;
  last_updated: string | null;
  description?: string;
  error?: string;
}

export interface CapitalInvestmentYoYDataPoint {
  date: string;
  value: number | null;
}

export interface CapitalInvestmentYoYResponse {
  data: CapitalInvestmentYoYDataPoint[];
  latest: CapitalInvestmentYoYDataPoint | null;
  cached: boolean;
  source: string;
  last_updated: string | null;
  error?: string;
}

export interface CapitalInvestmentCacheStatus {
  indicator: string;
  source: string;
  cache_key: string;
  exists: boolean;
  last_updated: string | null;
  data_count: number;
  file_cache_exists: boolean;
}

/**
 * 設備投資データを取得（生データ、百万円単位）
 *
 * @param forceRefresh キャッシュを無視して強制更新
 * @returns 設備投資データ
 */
export async function fetchCapitalInvestmentData(
  forceRefresh: boolean = false
): Promise<CapitalInvestmentResponse> {
  const params = new URLSearchParams();
  if (forceRefresh) {
    params.append('force_refresh', 'true');
  }

  const url = `${API_BASE_URL}/api/japan/capital-investment${params.toString() ? '?' + params.toString() : ''}`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch Capital Investment data: ${response.status}`);
  }

  return response.json();
}

/**
 * 設備投資データを取得（前年比、%単位）
 *
 * @param forceRefresh キャッシュを無視して強制更新
 * @returns 設備投資データ（前年比）
 */
export async function fetchCapitalInvestmentYoYData(
  forceRefresh: boolean = false
): Promise<CapitalInvestmentYoYResponse> {
  const params = new URLSearchParams();
  if (forceRefresh) {
    params.append('force_refresh', 'true');
  }

  const url = `${API_BASE_URL}/api/japan/capital-investment/yoy${params.toString() ? '?' + params.toString() : ''}`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch Capital Investment YoY data: ${response.status}`);
  }

  return response.json();
}

/**
 * キャッシュステータスを取得
 *
 * @returns キャッシュの状態情報
 */
export async function fetchCapitalInvestmentCacheStatus(): Promise<CapitalInvestmentCacheStatus> {
  const url = `${API_BASE_URL}/api/japan/capital-investment/cache-status`;

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
export async function refreshCapitalInvestmentData(): Promise<{
  status: string;
  data_count: number;
  latest: CapitalInvestmentDataPoint | null;
  last_updated: string | null;
}> {
  const url = `${API_BASE_URL}/api/japan/capital-investment/refresh`;

  const response = await fetch(url, { method: 'POST' });
  if (!response.ok) {
    throw new Error(`Failed to refresh data: ${response.status}`);
  }

  return response.json();
}
