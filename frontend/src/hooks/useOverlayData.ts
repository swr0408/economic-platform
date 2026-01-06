/**
 * オーバーレイデータ取得フック
 * 指標IDに基づいて適切なAPIからデータを取得
 */

import { useQuery, useQueries } from '@tanstack/react-query';
import { OVERLAY_INDICATORS, type OverlayIndicator, type DerivedValueConfig } from '../constants/overlayConfig';
import type { DataPoint } from '../utils/dataAlignment';

// APIベースURL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

// OVERLAY_INDICATORSからマッピングを動的に生成
function getIndicatorMapping(indicatorId: string): {
  endpoint: string;
  dataKey: string;
  valueField?: string;
  nestedKey?: string;  // ppi_categoriesのようにカテゴリ配列からの抽出用
  derived?: DerivedValueConfig;
  isMarketData?: boolean;
  isDirectApi?: boolean;  // /dashboardを追加しない個別APIの場合
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
      isDirectApi: false,
    };
  }

  // 個別API（/dashboardを追加しない）の判定
  // - /api/nyfed/term-premium
  // - /api/fed-h15/policy-rate
  // など、特定のエンドポイントは直接使用
  const directApiPatterns = [
    '/api/nyfed/',
    '/api/fed-h15/',
    '/api/cme/',
  ];
  const isDirectApi = directApiPatterns.some(pattern => indicator.apiEndpoint.startsWith(pattern));

  if (isDirectApi) {
    return {
      endpoint: indicator.apiEndpoint,
      dataKey: indicator.dataKey,
      valueField: indicator.valueField,
      derived: indicator.derived,
      isMarketData: false,
      isDirectApi: true,
    };
  }

  // apiEndpointを/dashboard形式に変換
  const endpoint = indicator.apiEndpoint + '/dashboard';
  return {
    endpoint,
    dataKey: indicator.dataKey,
    valueField: indicator.valueField,
    nestedKey: indicator.nestedKey,
    derived: indicator.derived,
    isMarketData: false,
    isDirectApi: false,
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
  derived?: DerivedValueConfig,
  nestedKey?: string
): DataPoint[] {
  // dataKeyでデータを取得
  const indicatorData = response.data[dataKey] as unknown;

  if (!indicatorData) {
    console.log('[useOverlayData] No indicator data for:', dataKey);
    return [];
  }

  // パターン: ppi_categories のような categories 配列構造
  // { categories: [{ key: 'airline_passenger', data: [{date, yoy, mom}] }, ...] }
  if (nestedKey && dataKey === 'ppi_categories') {
    const dataObj = indicatorData as { categories?: Array<{ key: string; data: Array<{ date: string; yoy: number | null; mom: number | null }> }> };
    if (dataObj.categories && Array.isArray(dataObj.categories)) {
      const category = dataObj.categories.find(cat => cat.key === nestedKey);
      if (category && category.data) {
        const field = valueField || 'yoy';
        console.log('[useOverlayData] PPI categories pattern for:', nestedKey, 'field:', field, 'length:', category.data.length);
        return category.data
          .filter(item => {
            const val = item[field as keyof typeof item];
            return val !== undefined && val !== null && typeof val === 'number';
          })
          .map(item => ({
            date: item.date,
            value: item[field as keyof typeof item] as number,
          }));
      }
      console.log('[useOverlayData] Category not found:', nestedKey);
    }
    return [];
  }

  // パターン0: housing_indicators のような特殊構造
  // { data: { zillow: [{date, yoy}], case_shiller: [{date, yoy}], rent_cpi: [{date, yoy}] } }
  if (dataKey === 'housing_indicators' && valueField) {
    const dataObj = indicatorData as { data?: Record<string, Array<{ date: string; yoy: number }>> };
    if (dataObj.data && typeof dataObj.data === 'object') {
      const seriesData = dataObj.data[valueField];
      if (Array.isArray(seriesData)) {
        console.log('[useOverlayData] Housing indicators pattern for:', dataKey, '.', valueField, 'length:', seriesData.length);
        return seriesData
          .filter(item => item.yoy !== undefined && item.yoy !== null && typeof item.yoy === 'number')
          .map(item => ({
            date: item.date,
            value: item.yoy,
          }));
      }
    }
    console.log('[useOverlayData] No housing indicators data for:', valueField);
    return [];
  }

  // パターン0.5: zillow_rent_index / rent_cpi のような構造
  // { data: [{date, yoy}], latest: {...} }
  if ((dataKey === 'zillow_rent_index' || dataKey === 'rent_cpi') && valueField === 'yoy') {
    const dataObj = indicatorData as { data?: Array<{ date: string; yoy: number }> };
    if (dataObj.data && Array.isArray(dataObj.data)) {
      console.log('[useOverlayData] Zillow/RentCPI pattern for:', dataKey, 'length:', dataObj.data.length);
      return dataObj.data
        .filter(item => item.yoy !== undefined && item.yoy !== null && typeof item.yoy === 'number')
        .map(item => ({
          date: item.date,
          value: item.yoy,
        }));
    }
    console.log('[useOverlayData] No data for:', dataKey);
    return [];
  }

  // パターン1: 直接配列の場合 (例: gdp_growth_rate: [{date, value}])
  if (Array.isArray(indicatorData)) {
    console.log('[useOverlayData] Direct array pattern for:', dataKey, 'length:', indicatorData.length);
    return (indicatorData as APIDataItem[])
      .filter(item => {
        const val = item.value;
        return val !== undefined && val !== null && typeof val === 'number';
      })
      .map(item => ({
        date: item.date,
        value: item.value as number,
      }));
  }

  const dataObj = indicatorData as {
    data?: APIDataItem[];
    [key: string]: unknown;
  };

  if (derived) {
    const data = dataObj.data;
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
    const nestedKey = parts[0];  // 例: "baseline" or "nominal"
    const remainingPath = parts.slice(1).join('.');  // 例: "data" or "mom"

    const nestedData = dataObj[nestedKey] as Record<string, unknown> | null;
    if (!nestedData) {
      console.log('[useOverlayData] No nested data for:', nestedKey);
      return [];
    }

    // パターン3: baseline.data のようなパス (fci.baseline.data)
    if (remainingPath === 'data') {
      const dataArray = nestedData.data as APIDataItem[] | undefined;
      if (dataArray && Array.isArray(dataArray)) {
        console.log('[useOverlayData] Nested data array pattern for:', dataKey, '.', valueField, 'length:', dataArray.length);
        return dataArray
          .filter(item => {
            const val = item.value;
            return val !== undefined && val !== null && typeof val === 'number';
          })
          .map(item => ({
            date: item.date,
            value: item.value as number,
          }));
      }
    }

    // パターン: weekly.nominal のような場合（nested object内のdata配列から特定フィールドを取得）
    const nestedDataWithData = nestedData as { data?: APIDataItem[] };
    if (nestedDataWithData?.data && Array.isArray(nestedDataWithData.data)) {
      console.log('[useOverlayData] Nested data with field pattern for:', dataKey, '.', valueField, 'remainingPath:', remainingPath, 'dataLength:', nestedDataWithData.data.length);
      const result = nestedDataWithData.data
        .filter(item => {
          const val = getNestedValue(item, remainingPath);
          return val !== undefined && val !== null && typeof val === 'number';
        })
        .map(item => ({
          date: item.date,
          value: getNestedValue(item, remainingPath) as number,
        }));
      console.log('[useOverlayData] Extracted', result.length, 'points from nested data field pattern');
      return result;
    }
    console.log('[useOverlayData] No matching nested pattern for:', dataKey, 'nestedKey:', nestedKey, 'nestedData:', nestedData);
    return [];
  }

  // パターン2: valueFieldがサブオブジェクトを指す場合 (例: potential_gdp.real: [{date, value}])
  if (valueField && !valueField.includes('.')) {
    const subData = dataObj[valueField];
    if (Array.isArray(subData)) {
      console.log('[useOverlayData] Sub-object array pattern for:', dataKey, '.', valueField, 'length:', subData.length);
      return (subData as APIDataItem[])
        .filter(item => {
          const val = item.value;
          return val !== undefined && val !== null && typeof val === 'number';
        })
        .map(item => ({
          date: item.date,
          value: item.value as number,
        }));
    }
  }

  // dataフィールドがある場合
  if (dataObj.data && Array.isArray(dataObj.data) && dataObj.data.length > 0) {
    // 指定されたvalueFieldを使用、なければ自動検出
    const field = valueField || detectValueField(dataObj.data[0]);
    if (!field) {
      console.log('[useOverlayData] No numeric field found for:', dataKey);
      return [];
    }
    console.log('[useOverlayData] Using value field:', field, 'for dataKey:', dataKey);

    return dataObj.data
      .filter((item): item is APIDataItem => {
        const val = item[field];
        return val !== undefined && val !== null && typeof val === 'number';
      })
      .map(item => ({
        date: item.date,
        value: item[field] as number,
      }));
  }

  console.log('[useOverlayData] No matching pattern for:', dataKey, 'valueField:', valueField);
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
      const result = extractIndicatorData(data, mapping.dataKey, mapping.valueField, mapping.derived, mapping.nestedKey);
      console.log('[useOverlayData] Extracted', result.length, 'points for', indicator.id);
      return result;
    },
    enabled: !!indicator && !!mapping,
    staleTime: 24 * 60 * 60 * 1000, // 1日
    gcTime: 24 * 60 * 60 * 1000, // 1日
  });

  return {
    ...query,
    indicatorId: indicator?.id || null,
  };
}

/**
 * 個別API（nyfed, fed-h15等）のレスポンスからデータを抽出
 */
interface DirectApiDataItem {
  date: string;
  [key: string]: unknown;
}

function extractDirectApiData(
  response: unknown,
  dataKey: string,
  valueField?: string
): DataPoint[] {
  const data = response as { data?: DirectApiDataItem[]; meta?: unknown };

  if (!data.data || !Array.isArray(data.data)) {
    console.log('[useOverlayData] No data array in direct API response for:', dataKey);
    return [];
  }

  const field = valueField || dataKey;

  return data.data
    .filter((item) => {
      const val = item[field];
      return val !== undefined && val !== null && typeof val === 'number';
    })
    .map((item) => ({
      date: item.date,
      value: item[field] as number,
    }));
}

/**
 * 単一指標データをフェッチする関数
 */
async function fetchSingleIndicatorData(
  _indicator: OverlayIndicator,
  mapping: NonNullable<ReturnType<typeof getIndicatorMapping>>
): Promise<DataPoint[]> {
  const response = await fetch(`${API_BASE_URL}${mapping.endpoint}`);
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  const data = await response.json();

  // 市場データの場合
  if (mapping.isMarketData) {
    return extractMarketData(data as MarketAPIResponse, mapping.valueField);
  }
  // 個別API（nyfed, fed-h15等）の場合
  else if (mapping.isDirectApi) {
    return extractDirectApiData(data, mapping.dataKey, mapping.valueField);
  }
  // 通常の指標データ（/dashboard形式）
  else {
    return extractIndicatorData(
      data as APIResponse,
      mapping.dataKey,
      mapping.valueField,
      mapping.derived,
      mapping.nestedKey
    );
  }
}

/**
 * 複数指標のデータを並列取得（各指標を個別にキャッシュ）
 *
 * useQueriesを使用して各指標を個別にキャッシュすることで：
 * - 新しい指標追加時に既存データは再フェッチしない
 * - 各指標のローディング状態を個別に管理
 * - キャッシュ効率が向上
 */
export function useMultipleOverlayData(indicators: OverlayIndicator[]) {
  const queryResults = useQueries({
    queries: indicators.map(indicator => {
      const mapping = getIndicatorMapping(indicator.id);
      return {
        queryKey: ['overlay-single', indicator.id, mapping?.endpoint],
        queryFn: async () => {
          if (!mapping) return [];
          return fetchSingleIndicatorData(indicator, mapping);
        },
        enabled: !!mapping,
        staleTime: 24 * 60 * 60 * 1000, // 1日
        gcTime: 24 * 60 * 60 * 1000, // 1日
      };
    }),
  });

  // 結果をRecord形式にまとめる
  const data: Record<string, DataPoint[]> = {};
  let isLoading = false;
  let isError = false;

  queryResults.forEach((result, index) => {
    const indicator = indicators[index];
    if (result.data) {
      data[indicator.id] = result.data;
    }
    if (result.isLoading) {
      isLoading = true;
    }
    if (result.isError) {
      isError = true;
    }
  });

  return {
    data: Object.keys(data).length > 0 ? data : undefined,
    isLoading,
    isError,
  };
}
