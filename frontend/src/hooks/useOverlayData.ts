/**
 * オーバーレイデータ取得フック
 * 指標IDに基づいて適切なAPIからデータを取得
 */

import { useQuery } from '@tanstack/react-query';
import { OVERLAY_INDICATORS, type OverlayIndicator, type DerivedValueConfig } from '../constants/overlayConfig';
import type { DataPoint } from '../utils/dataAlignment';

// APIベースURL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

// OVERLAY_INDICATORSからマッピングを動的に生成
function getIndicatorMapping(indicatorId: string): {
  endpoint: string;
  dataKey: string;
  valueField?: string;
  derived?: DerivedValueConfig;
  isMarketData?: boolean;
} | null {
  const indicator = OVERLAY_INDICATORS.find(i => i.id === indicatorId);
  if (!indicator) return null;

  // 市場データ（/api/market）の場合は個別銘柄エンドポイントを使用
  if (indicator.apiEndpoint === '/api/market') {
    return {
      endpoint: `/api/market/${indicator.dataKey}/daily`,
      dataKey: indicator.dataKey,
      valueField: indicator.valueField,
      derived: indicator.derived,
      isMarketData: true,
    };
  }

  // apiEndpointを/dashboard形式に変換
  const endpoint = indicator.apiEndpoint + '/dashboard';
  return {
    endpoint,
    dataKey: indicator.dataKey,
    valueField: indicator.valueField,
    derived: indicator.derived,
    isMarketData: false,
  };
}

// APIレスポンスからデータを抽出
interface APIDataItem {
  date: string;
  value?: number;
  [key: string]: unknown;
}

interface APIResponse {
  data: Record<string, unknown>;
  cached: boolean;
  last_updated: string | null;
}

// 優先するフィールド名（順番に試す）
const PREFERRED_VALUE_FIELDS = ['value', 'current', 'mom', 'yoy'];

/**
 * データ項目から数値フィールドを自動検出
 */
function detectValueField(sampleItem: APIDataItem): string | null {
  for (const field of PREFERRED_VALUE_FIELDS) {
    const val = sampleItem[field];
    if (val !== undefined && val !== null && typeof val === 'number') {
      return field;
    }
  }

  for (const [key, val] of Object.entries(sampleItem)) {
    if (key !== 'date' && typeof val === 'number') {
      return key;
    }
  }

  return null;
}

/**
 * ネストしたパスから値を取得（例: "nominal.mom"）
 */
function getNestedValue(obj: unknown, path: string): unknown {
  const parts = path.split('.');
  let current: unknown = obj;

  for (const part of parts) {
    if (current === null || current === undefined) return undefined;
    if (typeof current !== 'object') return undefined;
    current = (current as Record<string, unknown>)[part];
  }

  return current;
}

/**
 * 市場データAPIのレスポンス型
 */
interface MarketAPIResponse {
  data: Array<{
    date: string;
    open: number | null;
    high: number | null;
    low: number | null;
    close: number | null;
    volume?: number;
  }>;
  latest: {
    date: string;
    close: number;
  } | null;
  symbol: Record<string, unknown> | null;
  cached: boolean;
  source: string;
  last_updated: string | null;
}

/**
 * 市場データを抽出
 */
function extractMarketData(
  response: MarketAPIResponse,
  valueField?: string
): DataPoint[] {
  if (!response.data || !Array.isArray(response.data)) {
    console.log('[useOverlayData] No market data in response');
    return [];
  }

  const field = valueField || 'close';

  return response.data
    .filter(item => {
      const val = item[field as keyof typeof item];
      return val !== undefined && val !== null && typeof val === 'number';
    })
    .map(item => ({
      date: item.date,
      value: item[field as keyof typeof item] as number,
    }));
}

/**
 * 指標データを抽出
 */
function extractIndicatorData(
  response: APIResponse,
  dataKey: string,
  valueField?: string,
  derived?: DerivedValueConfig
): DataPoint[] {
  // dataKeyでデータを取得
  let indicatorData = response.data[dataKey] as {
    data?: APIDataItem[];
    [key: string]: unknown;
  } | null;

  if (!indicatorData) {
    console.log('[useOverlayData] No indicator data for:', dataKey);
    return [];
  }

  if (derived) {
    const data = indicatorData.data;
    if (!data || !Array.isArray(data) || data.length === 0) {
      return [];
    }

    const sorted = [...data].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
    const points: DataPoint[] = [];
    let prevValue: number | null = null;

    for (const item of sorted) {
      const rawValue = getNestedValue(item, derived.sourceField);
      const currentValue = typeof rawValue === 'number' && !isNaN(rawValue) ? rawValue : null;
      if (currentValue === null) {
        continue;
      }
      if (prevValue !== null) {
        points.push({ date: item.date, value: currentValue - prevValue });
      }
      prevValue = currentValue;
    }

    return points;
  }

  // valueFieldにドットが含まれる場合（ネストパス）
  if (valueField && valueField.includes('.')) {
    const parts = valueField.split('.');
    const nestedKey = parts[0];  // 例: "nominal"
    const fieldName = parts.slice(1).join('.');  // 例: "mom"

    const nestedData = indicatorData[nestedKey] as { data?: APIDataItem[] } | null;
    if (nestedData?.data && Array.isArray(nestedData.data)) {
      return nestedData.data
        .filter(item => {
          const val = getNestedValue(item, fieldName);
          return val !== undefined && val !== null && typeof val === 'number';
        })
        .map(item => ({
          date: item.date,
          value: getNestedValue(item, fieldName) as number,
        }));
    }
    return [];
  }

  // dataフィールドがある場合
  if (indicatorData.data && Array.isArray(indicatorData.data) && indicatorData.data.length > 0) {
    // 指定されたvalueFieldを使用、なければ自動検出
    const field = valueField || detectValueField(indicatorData.data[0]);
    if (!field) {
      console.log('[useOverlayData] No numeric field found for:', dataKey);
      return [];
    }
    console.log('[useOverlayData] Using value field:', field, 'for dataKey:', dataKey);

    return indicatorData.data
      .filter((item): item is APIDataItem => {
        const val = item[field];
        return val !== undefined && val !== null && typeof val === 'number';
      })
      .map(item => ({
        date: item.date,
        value: item[field] as number,
      }));
  }

  return [];
}

/**
 * 単一指標のデータを取得
 */
export function useOverlayIndicatorData(indicator: OverlayIndicator | null) {
  const mapping = indicator ? getIndicatorMapping(indicator.id) : null;

  const query = useQuery<DataPoint[], Error>({
    queryKey: ['overlay', indicator?.id, mapping?.endpoint, mapping?.valueField],
    queryFn: async () => {
      if (!indicator || !mapping) {
        return [];
      }

      const url = `${API_BASE_URL}${mapping.endpoint}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      // 市場データの場合は専用の抽出ロジックを使用
      if (mapping.isMarketData) {
        const data = await response.json() as MarketAPIResponse;
        const result = extractMarketData(data, mapping.valueField);
        console.log('[useOverlayData] Extracted', result.length, 'market data points for', indicator.id);
        return result;
      }

      // 通常の指標データ
      const data = await response.json() as APIResponse;
      const result = extractIndicatorData(data, mapping.dataKey, mapping.valueField, mapping.derived);
      console.log('[useOverlayData] Extracted', result.length, 'points for', indicator.id);
      return result;
    },
    enabled: !!indicator && !!mapping,
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });

  return {
    ...query,
    indicatorId: indicator?.id || null,
  };
}

/**
 * 複数指標のデータを並列取得
 */
export function useMultipleOverlayData(indicators: OverlayIndicator[]) {
  const queries = indicators.map(indicator => {
    const mapping = getIndicatorMapping(indicator.id);
    return { indicator, mapping };
  });

  return useQuery<Record<string, DataPoint[]>, Error>({
    queryKey: ['overlays', indicators.map(i => i.id).join(',')],
    queryFn: async () => {
      const results: Record<string, DataPoint[]> = {};

      // エンドポイントでグループ化
      const endpointGroups = new Map<string, { indicator: OverlayIndicator; mapping: NonNullable<ReturnType<typeof getIndicatorMapping>> }[]>();

      for (const { indicator, mapping } of queries) {
        if (!mapping) continue;

        if (!endpointGroups.has(mapping.endpoint)) {
          endpointGroups.set(mapping.endpoint, []);
        }
        endpointGroups.get(mapping.endpoint)!.push({ indicator, mapping });
      }

      // 各エンドポイントを並列フェッチ
      const fetchPromises = Array.from(endpointGroups.entries()).map(
        async ([endpoint, items]) => {
          try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`);
            if (!response.ok) {
              console.error(`API error for ${endpoint}: ${response.status}`);
              return;
            }

            const data = await response.json() as APIResponse;

            for (const { indicator, mapping } of items) {
              results[indicator.id] = extractIndicatorData(
                data,
                mapping.dataKey,
                mapping.valueField,
                mapping.derived
              );
            }
          } catch (error) {
            console.error(`Failed to fetch ${endpoint}:`, error);
          }
        }
      );

      await Promise.all(fetchPromises);
      return results;
    },
    enabled: indicators.length > 0,
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });
}
