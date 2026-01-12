/**
 * GDP構成要素 API ユーティリティ
 * e-Stat（内閣府）からGDP構成要素データを取得
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface GDPComponentDataPoint {
  date: string;
  value: number;
}

export interface GDPComponentSeries {
  name: string;
  code: string;
  data: GDPComponentDataPoint[];
}

export interface GDPComponentsLatest {
  date: string;
  components: {
    [key: string]: {
      date: string;
      value: number;
    };
  };
}

export interface GDPComponentsData {
  series: GDPComponentSeries[];
  latest: GDPComponentsLatest | null;
  next_release: string | null;
  cached: boolean;
  source: string;
  last_updated: string | null;
}

export interface TableColumn {
  key: string;
  label: string;
  type: 'string' | 'number';
}

export interface TableRow {
  date: string;
  [key: string]: string | number | undefined;
}

export interface GDPComponentsTableData {
  columns: TableColumn[];
  rows: TableRow[];
  metadata: {
    source: string;
    indicator: string;
  };
  last_updated: string | null;
}

/**
 * GDP構成要素データを取得
 */
export const fetchGDPComponentsData = async (
  forceRefresh: boolean = false
): Promise<GDPComponentsData> => {
  const url = new URL(`${API_BASE_URL}/api/japan/gdp-components`);
  if (forceRefresh) {
    url.searchParams.append('force_refresh', 'true');
  }

  const response = await fetch(url.toString());

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return await response.json();
};

/**
 * テーブル表示用データを取得
 */
export const fetchGDPComponentsTableData = async (): Promise<GDPComponentsTableData> => {
  const url = `${API_BASE_URL}/api/japan/gdp-components/table`;

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return await response.json();
};
