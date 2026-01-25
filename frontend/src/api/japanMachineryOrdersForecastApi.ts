/**
 * Japan Machinery Orders Forecast API Client
 * 機械受注見通し調査データ（四半期）
 *
 * Endpoints:
 * - GET /api/japan/machinery-orders-forecast - 機械受注見通しデータ取得
 * - POST /api/japan/machinery-orders-forecast/refresh - データ強制更新
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface MachineryOrdersForecastDataPoint {
  date: string;                    // YYYY-MM-01 format (quarter end month)
  achievement_rate: number | null; // 達成率 (%)
  actual_amount: number | null;    // 実績額 (百万円)
  forecast_amount: number | null;  // 見通し額 (百万円)
  qoq_change: number | null;       // 前期比 (%)
  unit: string;                    // 単位
}

export interface MachineryOrdersForecastResponse {
  table_data: MachineryOrdersForecastDataPoint[];
  last_updated: string;
  data_source: string;
}

/**
 * 機械受注見通しデータ取得
 */
export async function fetchMachineryOrdersForecastData(): Promise<MachineryOrdersForecastResponse> {
  const response = await fetch(`${API_BASE_URL}/api/japan/machinery-orders-forecast`);

  if (!response.ok) {
    throw new Error(`Failed to fetch Japan Machinery Orders Forecast data: ${response.status}`);
  }

  return response.json();
}

/**
 * データ強制更新
 */
export async function refreshMachineryOrdersForecastData(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/japan/machinery-orders-forecast/refresh`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error(`Failed to refresh Japan Machinery Orders Forecast data: ${response.status}`);
  }
}
