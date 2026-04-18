/**
 * 潜在成長率 API ユーティリティ
 * 内閣府から潜在成長率データを取得
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

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
  const params = new URLSearchParams();
  if (forceRefresh) {
    params.append('force_refresh', 'true');
  }
  const qs = params.toString() ? `?${params.toString()}` : '';

  const response = await fetch(`${API_BASE_URL}/api/japan/potential-growth${qs}`);

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return await response.json();
};
