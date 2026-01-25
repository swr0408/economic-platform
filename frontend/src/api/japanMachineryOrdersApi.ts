/**
 * Japan Machinery Orders API Client
 * 機械受注データ（船舶・電力を除く民需）
 *
 * Endpoints:
 * - GET /api/japan/machinery-orders - 機械受注データ取得
 * - GET /api/japan/machinery-orders/chart - チャート用データ（YoY）
 * - GET /api/japan/machinery-orders/table - テーブル用データ（MoM）
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface NextRelease {
  date: string;
  datetime_utc?: string;
  datetime_jst?: string;
  time_jst?: string;
  label?: string;
}

export interface MachineryOrdersDataPoint {
  date: string;           // YYYY-MM-01 format
  value: number;          // 金額（百万円）
  unit: string;           // 単位
  mom_change: number | null;  // 前月比 (%)
  mom_3m_avg: number | null;  // 前月比3か月平均 (%)
  yoy_change: number | null;  // 前年比 (%)
}

export interface MachineryOrdersResponse {
  data: MachineryOrdersDataPoint[];
  last_updated: string;
  source: string;
  description: string;
  next_release?: NextRelease | null;
  cached: boolean;
  error?: string;
}

export interface MachineryOrdersChartResponse {
  chart_data: MachineryOrdersDataPoint[];
  last_updated: string;
  data_source: string;
  next_release?: NextRelease | null;
}

export interface MachineryOrdersTableResponse {
  table_data: MachineryOrdersDataPoint[];
  last_updated: string;
  data_source: string;
  next_release?: NextRelease | null;
}

/**
 * 機械受注データ取得
 */
export async function fetchMachineryOrdersData(
  forceRefresh: boolean = false
): Promise<MachineryOrdersResponse> {
  const params = new URLSearchParams();
  if (forceRefresh) {
    params.append('force_refresh', 'true');
  }

  const url = `${API_BASE_URL}/api/japan/machinery-orders${params.toString() ? '?' + params.toString() : ''}`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch Japan Machinery Orders data: ${response.status}`);
  }

  return response.json();
}

/**
 * チャート用データ取得（YoY）
 */
export async function fetchMachineryOrdersChartData(): Promise<MachineryOrdersChartResponse> {
  const response = await fetch(`${API_BASE_URL}/api/japan/machinery-orders/chart`);

  if (!response.ok) {
    throw new Error(`Failed to fetch Japan Machinery Orders chart data: ${response.status}`);
  }

  return response.json();
}

/**
 * テーブル用データ取得（MoM）
 */
export async function fetchMachineryOrdersTableData(): Promise<MachineryOrdersTableResponse> {
  const response = await fetch(`${API_BASE_URL}/api/japan/machinery-orders/table`);

  if (!response.ok) {
    throw new Error(`Failed to fetch Japan Machinery Orders table data: ${response.status}`);
  }

  return response.json();
}

/**
 * データ強制更新
 */
export async function refreshMachineryOrdersData(): Promise<MachineryOrdersResponse> {
  const response = await fetch(`${API_BASE_URL}/api/japan/machinery-orders/refresh`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error(`Failed to refresh Japan Machinery Orders data: ${response.status}`);
  }

  return response.json();
}

/**
 * 日付フォーマット (YYYY-MM-01 -> YYYY/MM)
 */
export function formatMachineryOrdersDate(dateStr: string): string {
  try {
    const [year, month] = dateStr.split('-');
    return `${year}/${month}`;
  } catch {
    return dateStr;
  }
}
