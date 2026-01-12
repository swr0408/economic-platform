/**
 * 潜在成長率 API ユーティリティ
 * 内閣府から潜在成長率データを取得
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface PotentialGrowthDataPoint {
  date: string;
  value: number;
}

export interface PotentialGrowthData {
  data: PotentialGrowthDataPoint[];
  latest: PotentialGrowthDataPoint | null;
  cached: boolean;
  source: string;
  last_updated: string | null;
}

/**
 * 潜在成長率データを取得
 */
export const fetchPotentialGrowthData = async (
  forceRefresh: boolean = false
): Promise<PotentialGrowthData> => {
  const url = new URL(`${API_BASE_URL}/api/japan/potential-growth`);
  if (forceRefresh) {
    url.searchParams.append('force_refresh', 'true');
  }

  const response = await fetch(url.toString());

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return await response.json();
};
