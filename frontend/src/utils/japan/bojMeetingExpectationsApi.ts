/**
 * API utility for fetching BOJ Meeting Expectations from Tokyo Tanshi
 */

export interface BOJMeetingExpectation {
  meeting_date: string;  // "2024-01-23"
  ois_rate: number | null;  // OIS rate in %
  difference: number | null;  // Difference from previous meeting in %
  probability: number | null;  // Probability of rate hike in %
  frequency?: number | null;  // Cumulative rate hike frequency (利上げ織込み回数)
}

export interface BOJMeetingExpectationsData {
  meetings: BOJMeetingExpectation[];
  last_updated: string;
  source: string;
  cached?: boolean;
  error?: string;
}

/**
 * Fetch BOJ Meeting Expectations data from backend
 */
export async function fetchBOJMeetingExpectations(): Promise<BOJMeetingExpectationsData> {
  try {
    const response = await fetch('/api/japan/boj-meeting-expectations');

    if (!response.ok) {
      throw new Error(`Failed to fetch BOJ meeting expectations: ${response.statusText}`);
    }

    const data: BOJMeetingExpectationsData = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching BOJ meeting expectations:', error);
    throw error;
  }
}

/**
 * Format meeting date for display (yyyy/mm format)
 */
export function formatMeetingDate(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    return `${year}/${month}`;
  } catch {
    return dateStr;
  }
}

/**
 * Format OIS rate with 4 decimal places
 */
export function formatOISRate(value: number | null): string {
  if (value === null || value === undefined) {
    return '-';
  }
  return `${value.toFixed(4)}%`;
}

/**
 * Format difference with sign and 4 decimal places
 */
export function formatDifference(value: number | null): string {
  if (value === null || value === undefined) {
    return '-';
  }
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(4)}%`;
}

/**
 * Format probability as integer percentage
 */
export function formatProbability(value: number | null): string {
  if (value === null || value === undefined) {
    return '-';
  }
  return `${Math.round(value)}%`;
}
