/**
 * GDPデフレーター API ユーティリティ
 * e-Stat（内閣府）からGDPデフレーターデータを取得
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export interface GDPDeflatorDataPoint {
  date: string;
  value: number;
}

export interface GDPDeflatorData {
  data: GDPDeflatorDataPoint[];
  latest: GDPDeflatorDataPoint | null;
  cached: boolean;
  source: string;
  last_updated: string | null;
}

/**
 * GDPデフレーターデータを取得
 */
export const fetchGDPDeflatorData = async (
  forceRefresh: boolean = false
): Promise<GDPDeflatorData> => {
  const url = new URL(`${API_BASE_URL}/api/japan/gdp-deflator`);
  if (forceRefresh) {
    url.searchParams.append('force_refresh', 'true');
  }

  const response = await fetch(url.toString());

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return await response.json();
};
