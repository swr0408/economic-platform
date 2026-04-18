/**
 * ECB Macroeconomic Projections API utility
 * Fetches comprehensive ECB macroeconomic projections from backend
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export interface ECBProjectionDataPoint {
  date: string;
  value: number | null;
}

export interface ECBIndicatorData {
  annual_latest: ECBProjectionDataPoint[];
  annual_previous: ECBProjectionDataPoint[];
  quarterly_latest: ECBProjectionDataPoint[];
  quarterly_previous: ECBProjectionDataPoint[];
}

export interface ECBMacroProjectionsMetadata {
  last_updated: string;
  source: string;
  latest_vintage: string;
  previous_vintage: string;
  latest_season_name: string;
  previous_season_name: string;
  error?: string;
}

export interface ECBMacroProjectionsResponse {
  indicators: {
    gdp: ECBIndicatorData;
    unemployment: ECBIndicatorData;
    hicp: ECBIndicatorData;
    core_inflation: ECBIndicatorData;
    core_inflation_tax: ECBIndicatorData;
    foreign_demand: ECBIndicatorData;
    interest_rate: ECBIndicatorData;
    private_consumption: ECBIndicatorData;
    wages: ECBIndicatorData;
  };
  metadata: ECBMacroProjectionsMetadata;
}

export interface IndicatorConfig {
  key: keyof ECBMacroProjectionsResponse['indicators'];
  name_jp: string;
  name_en: string;
  unit: string;
  description?: string;
}

export const INDICATOR_CONFIGS: IndicatorConfig[] = [
  {
    key: 'interest_rate',
    name_jp: '短期金利',
    name_en: 'Short-term Interest Rates',
    unit: '%',
    description: '短期金利の予測'
  },
  {
    key: 'gdp',
    name_jp: 'GDP成長率',
    name_en: 'GDP Growth',
    unit: '%',
    description: 'GDP成長率の予測'
  },
  {
    key: 'private_consumption',
    name_jp: '民間消費',
    name_en: 'Private Consumption',
    unit: '%',
    description: '民間消費の成長率'
  },
  {
    key: 'foreign_demand',
    name_jp: '外需',
    name_en: 'Foreign Demand',
    unit: '%',
    description: '外需の成長率'
  },
  {
    key: 'unemployment',
    name_jp: '失業率',
    name_en: 'Unemployment Rate',
    unit: '%',
    description: '失業率の予測'
  },
  {
    key: 'hicp',
    name_jp: 'HICP（総合）',
    name_en: 'HICP Inflation',
    unit: '%',
    description: '消費者物価指数（総合）'
  },
  {
    key: 'core_inflation',
    name_jp: 'コアインフレ（除くエネルギー・食料）',
    name_en: 'Core Inflation (excl. energy & food)',
    unit: '%',
    description: 'エネルギーと食料を除くコアインフレ'
  },
  {
    key: 'core_inflation_tax',
    name_jp: 'コアインフレ（除くエネルギー・食料・間接税）',
    name_en: 'Core Inflation (excl. energy, food & indirect taxes)',
    unit: '%',
    description: 'エネルギー、食料、間接税変化を除くコアインフレ'
  },
  {
    key: 'wages',
    name_jp: '賃金上昇率',
    name_en: 'Compensation per Employee',
    unit: '%',
    description: '従業員1人当たりの報酬の成長率'
  }
];

/**
 * Fetch ECB macroeconomic projections data
 * @param forceRefresh - Force refresh data from ECB
 * @returns ECB macroeconomic projections data
 */
export async function fetchECBMacroProjections(forceRefresh = false): Promise<ECBMacroProjectionsResponse> {
  try {
    const params = new URLSearchParams();
    if (forceRefresh) {
      params.set('force_refresh', 'true');
    }
    const qs = params.toString() ? `?${params.toString()}` : '';

    const response = await fetch(`${API_BASE_URL}/api/eurozone/ecb-macro-projections${qs}`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data: ECBMacroProjectionsResponse = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching ECB macro projections data:', error);
    throw error;
  }
}

/**
 * Refresh ECB macroeconomic projections data from source
 * @returns Updated ECB macroeconomic projections data
 */
export async function refreshECBMacroProjections(): Promise<ECBMacroProjectionsResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/eurozone/ecb-macro-projections/refresh`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error(`Failed to refresh: ${response.statusText}`);
    }

    const data: ECBMacroProjectionsResponse = await response.json();
    return data;
  } catch (error) {
    console.error('Error refreshing ECB macro projections data:', error);
    throw error;
  }
}

/**
 * Format date for display (YYYY/MM/DD or YYYY-QX)
 * @param dateStr - Date string
 * @returns Formatted date string
 */
export function formatProjectionDate(dateStr: string): string {
  // Already in quarter format (e.g., "2024-Q1")
  if (dateStr.includes('Q')) {
    return dateStr;
  }

  // Annual format (e.g., "2024")
  if (dateStr.length === 4) {
    return dateStr;
  }

  // Date format
  try {
    const date = new Date(dateStr);
    const year = date.getFullYear();
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const day = date.getDate().toString().padStart(2, '0');
    return `${year}/${month}/${day}`;
  } catch {
    return dateStr;
  }
}
