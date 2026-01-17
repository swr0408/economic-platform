/**
 * BOE OIS Forward Curve API Client
 * Bank of England OIS forward curve data (Month1-12)
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface OISCurvePoint {
  date: string;
  data: {
    [key: string]: number | null; // Month1-12
  };
}

export interface OISCurveData {
  current: OISCurvePoint | null;
  previous: OISCurvePoint | null;
  metadata?: {
    source?: string;
    indicator?: string;
    total_dates?: number;
    date_range?: {
      start: string;
      end: string;
    };
  };
}

export interface OISCurveResponse {
  data: OISCurveData;
  cached: boolean;
  source: string;
  last_updated: string;
  error?: string;
}

export interface OISCurveChartData {
  current: OISCurvePoint | null;
  previous: OISCurvePoint | null;
  metadata?: {
    source?: string;
    indicator?: string;
  };
}

/**
 * Fetch BOE OIS forward curve data
 */
export async function fetchBOEOISCurve(forceRefresh = false): Promise<OISCurveResponse> {
  const url = new URL(`${API_BASE_URL}/api/uk/boe-ois-curve`);
  if (forceRefresh) {
    url.searchParams.append('force_refresh', 'true');
  }

  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error(`Failed to fetch BOE OIS data: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch BOE OIS curve data formatted for charting
 */
export async function fetchBOEOISChartData(): Promise<OISCurveChartData> {
  const url = `${API_BASE_URL}/api/uk/boe-ois-curve/chart`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch BOE OIS chart data: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Format OIS curve data for Recharts
 * Converts current and previous data into chart-ready format
 */
export interface ChartDataPoint {
  date: string; // Using 'date' for ZoomableChart compatibility (actually tenor)
  value: number; // Primary value (same as currentRate)
  tenor?: string;
  tenorNum?: number;
  currentRate?: number | null;
  previousRate?: number | null;
  [key: string]: unknown; // Index signature for compatibility with ZoomableChart DataPoint
}

export function formatBOEOISForChart(data: OISCurveChartData): ChartDataPoint[] {
  const chartData: ChartDataPoint[] = [];

  // Extract months 1-12
  for (let month = 1; month <= 12; month++) {
    const monthKey = `Month${month}`;

    const currentRate = data.current?.data?.[monthKey] ?? null;
    const previousRate = data.previous?.data?.[monthKey] ?? null;

    chartData.push({
      date: `${month}M`, // ZoomableChart uses 'date' as x-axis key
      tenor: `${month}M`,
      tenorNum: month,
      value: currentRate ?? 0, // Primary value for ZoomableChart
      currentRate,
      previousRate,
    });
  }

  return chartData;
}

/**
 * Sort chart data by tenor order
 */
export function sortByTenor(data: ChartDataPoint[]): ChartDataPoint[] {
  return [...data].sort((a, b) => (a.tenorNum ?? 0) - (b.tenorNum ?? 0));
}
