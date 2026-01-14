/**
 * Japan Industrial Production Index (IIP) API
 *
 * Endpoints:
 * - GET /api/japan/iip - IIPデータ取得（前月比含む）
 * - GET /api/japan/iip-yoy - IIP YoYデータ取得
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface NextRelease {
  date: string;
  datetime_utc?: string;
  datetime_jst?: string;
  time_jst?: string;
  label?: string;
}

export interface JapanIIPDataPoint {
  date: string;           // YYYY-MM-01 format
  item_code: string;      // 品目番号 (1000000000)
  item_name: string;      // 品目名称 (鉱工業)
  category: string;       // カテゴリ
  value: number | null;   // 生産指数
  mom_change: number | null; // 前月比 (%)
}

export interface JapanIIPResponse {
  data: JapanIIPDataPoint[];
  latest: JapanIIPDataPoint | null;
  next_release?: NextRelease | null;
  cached: boolean;
  source: string;
  last_updated: string | null;
  error?: string;
}

export interface JapanIIPYoYDataPoint {
  date: string;
  item_code: string;
  item_name: string;
  category: string;
  index_value: number | null;
  yoy_change: number | null;  // 前年比 (%)
}

export interface JapanIIPYoYResponse {
  data: JapanIIPYoYDataPoint[];
  latest: JapanIIPYoYDataPoint | null;
  next_release?: NextRelease | null;
  cached: boolean;
  source: string;
  last_updated: string | null;
  error?: string;
}

/**
 * IIPデータ取得（前月比含む）
 */
export async function fetchJapanIIPData(
  forceRefresh: boolean = false
): Promise<JapanIIPResponse> {
  const params = new URLSearchParams();
  if (forceRefresh) {
    params.append('force_refresh', 'true');
  }

  const url = `${API_BASE_URL}/api/japan/iip${params.toString() ? '?' + params.toString() : ''}`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch Japan IIP data: ${response.status}`);
  }

  return response.json();
}

/**
 * IIP YoYデータ取得（前年比）
 */
export async function fetchJapanIIPYoYData(
  forceRefresh: boolean = false
): Promise<JapanIIPYoYResponse> {
  const params = new URLSearchParams();
  if (forceRefresh) {
    params.append('force_refresh', 'true');
  }

  const url = `${API_BASE_URL}/api/japan/iip-yoy${params.toString() ? '?' + params.toString() : ''}`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch Japan IIP YoY data: ${response.status}`);
  }

  return response.json();
}

/**
 * 日付フォーマット (YYYY-MM-01 -> YYYY/MM)
 */
export function formatIIPDate(dateStr: string): string {
  try {
    const [year, month] = dateStr.split('-');
    return `${year}/${month}`;
  } catch {
    return dateStr;
  }
}
