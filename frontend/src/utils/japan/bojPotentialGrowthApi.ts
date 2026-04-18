/**
 * 日銀潜在成長率 API ユーティリティ
 * 日本銀行から潜在成長率データを取得
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export interface BOJPotentialGrowthDataPoint {
  date: string;
  value: number;
}

export interface BOJPotentialGrowthData {
  data: BOJPotentialGrowthDataPoint[];
  latest: BOJPotentialGrowthDataPoint | null;
  cached: boolean;
  source: string;
  last_updated: string | null;
}

/**
 * 日銀潜在成長率データを取得
 */
export const fetchBOJPotentialGrowthData = async (
  forceRefresh: boolean = false
): Promise<BOJPotentialGrowthData> => {
  const params = new URLSearchParams();
  if (forceRefresh) {
    params.append('force_refresh', 'true');
  }
  const qs = params.toString() ? `?${params.toString()}` : '';

  const response = await fetch(`${API_BASE_URL}/api/japan/boj-potential-growth${qs}`);

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return await response.json();
};
