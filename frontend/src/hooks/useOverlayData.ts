/**
 * オーバーレイデータ取得フック
 * 指標IDに基づいて適切なAPIからデータを取得
 */

import { useQuery, useQueries } from '@tanstack/react-query';
import { OVERLAY_INDICATORS, type OverlayIndicator, type DerivedValueConfig } from '../constants/overlayConfig';
import { type DataPoint, getDateTimestamp } from '../utils/dataAlignment';

// APIベースURL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

/**
 * 月次データを四半期平均に変換し、前期比（QoQ%）または前年比（YoY%）を計算する共通ヘルパー
 *
 * qoq_pct: 月次指数 → 四半期平均 → (Q_t / Q_{t-1} - 1) × 100
 * yoy_pct: 月次指数 → 四半期平均 → (Q_t / Q_{t-4} - 1) × 100
 */
function computeQuarterlyPctChange(
  data: DataPoint[],
  mode: 'qoq' | 'yoy',
): DataPoint[] {
  // 四半期キー (YYYY-Q1..Q4) でグルーピング
  const qMap = new Map<string, { sum: number; count: number; lastDate: string }>();

  for (const pt of data) {
    if (pt.value === null || pt.value === undefined) continue;
    const d = new Date(pt.date);
    const y = d.getUTCFullYear();
    const m = d.getUTCMonth(); // 0-11
    const q = Math.floor(m / 3) + 1; // 1-4
    const key = `${y}-Q${q}`;

    const entry = qMap.get(key);
    if (entry) {
      entry.sum += pt.value;
      entry.count += 1;
      if (pt.date > entry.lastDate) entry.lastDate = pt.date;
    } else {
      qMap.set(key, { sum: pt.value, count: 1, lastDate: pt.date });
    }
  }

  // 3ヵ月揃った四半期のみ採用し、平均を計算
  const quarters: { key: string; avg: number; date: string }[] = [];
  for (const [key, v] of qMap) {
    if (v.count === 3) {
      quarters.push({ key, avg: v.sum / v.count, date: v.lastDate });
    }
  }
  quarters.sort((a, b) => a.key.localeCompare(b.key));

  const lag = mode === 'qoq' ? 1 : 4;
  const points: DataPoint[] = [];
  for (let i = lag; i < quarters.length; i++) {
    const cur = quarters[i].avg;
    const prev = quarters[i - lag].avg;
    if (prev !== 0) {
      points.push({
        date: quarters[i].date,
        value: Math.round(((cur / prev) - 1) * 10000) / 100,
      });
    }
  }
  return points;
}

/**
 * 月次データを四半期平均に変換し、前期差（first difference）を計算する共通ヘルパー
 *
 * qoq_diff: 月次指数 → 四半期平均 → ΔĪ_Q = Ī_Q − Ī_{Q-1}
 *
 * Ifo景況感指数のように、四半期GDPと整合的に比較したい指数で利用する。
 * 単純平均で四半期平均を算出し、前期差を絶対値（pt差分）で返す。
 */
function computeQuarterlyDiff(data: DataPoint[]): DataPoint[] {
  // 四半期キー (YYYY-Q1..Q4) でグルーピング
  const qMap = new Map<string, { sum: number; count: number; lastDate: string }>();

  for (const pt of data) {
    if (pt.value === null || pt.value === undefined) continue;
    const d = new Date(pt.date);
    const y = d.getUTCFullYear();
    const m = d.getUTCMonth(); // 0-11
    const q = Math.floor(m / 3) + 1; // 1-4
    const key = `${y}-Q${q}`;

    const entry = qMap.get(key);
    if (entry) {
      entry.sum += pt.value;
      entry.count += 1;
      if (pt.date > entry.lastDate) entry.lastDate = pt.date;
    } else {
      qMap.set(key, { sum: pt.value, count: 1, lastDate: pt.date });
    }
  }

  // 3ヵ月揃った四半期のみ採用し、単純平均を計算
  const quarters: { key: string; avg: number; date: string }[] = [];
  for (const [key, v] of qMap) {
    if (v.count === 3) {
      quarters.push({ key, avg: v.sum / v.count, date: v.lastDate });
    }
  }
  quarters.sort((a, b) => a.key.localeCompare(b.key));

  // 1期ラグ差分: ΔĪ_Q = Ī_Q − Ī_{Q-1}
  const points: DataPoint[] = [];
  for (let i = 1; i < quarters.length; i++) {
    const cur = quarters[i].avg;
    const prev = quarters[i - 1].avg;
    points.push({
      date: quarters[i].date,
      value: Math.round((cur - prev) * 100) / 100,
    });
  }
  return points;
}

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
  // - /api/japan/quarterly-gdp など
  // 特定のエンドポイントは直接使用
  const directApiPatterns = [
    '/api/nyfed/',
    '/api/fed-h15/',
    '/api/cme/',
    '/api/japan/quarterly-gdp',
    '/api/japan/gdp-components',
    '/api/japan/gdp-deflator',
    '/api/japan/potential-growth',
    '/api/japan/gdp-gap',
    '/api/japan/boj-',
    '/api/japan/ois-',
    '/api/japan/capital-investment',
    '/api/japan/iip',
    '/api/japan/capacity-utilization',
    '/api/japan/national-cpi',
    '/api/japan/tokyo-cpi',
    '/api/japan/cgpi',
    '/api/japan/cgpi-food-agriculture',
    '/api/japan/import-export-price',
    '/api/japan/sppi',
    '/api/japan/pos-uvpi',
    '/api/japan/machinery-orders',
    '/api/japan/machine-tool-orders',
    '/api/japan/tertiary-industry-index',
    '/api/japan/current-account',
    '/api/japan/balance-of-trade',
    '/api/japan/terms-of-trade',
    '/api/japan/price-di-spread',
    '/api/japan/price-pass-through-rate',
    '/api/japan/economy-watcher/',
    // UK個別API（BOE Bank Rate、ONS GDP/GVA/Production、UK QT等）
    '/api/uk/boe-',
    '/api/uk/ons-',
    '/api/uk/uk-qt',
    '/api/uk/uk-trade-balance',
    '/api/uk/uk-current-account',
    '/api/uk/uk-government-debt-to-gdp-ratio',
    // Eurozone個別API（PMI、ECB CES等）
    '/api/eurozone/pmi',
    '/api/eurozone/germany-pmi',
    '/api/eurozone/france-pmi',
    '/api/eurozone/ecb-ces-wage-expectations',
    '/api/eurozone/ecb-balance-sheet',
    '/api/eurozone/eu-government-debt-to-gdp-ratio',
    // Switzerland個別API（SNB、BFS/FSO等）
    '/api/switzerland/',
    // Canada個別API（BOC、Statistics Canada等）
    '/api/canada/boc/',
    '/api/canada/statcan/',
    // Australia個別API（RBA、ABS、APRA、Melbourne Institute等）
    '/api/australia/rba/',
    '/api/australia/abs/',
    '/api/australia/apra/',
    '/api/australia/melbourne-institute/',
    '/api/australia/housing/',
    // New Zealand個別API（RBNZ・Stats NZ・ANZ等）
    '/api/newzealand/rbnz/',
    '/api/newzealand/stats-nz/',
    '/api/newzealand/anz/',
    '/api/newzealand/nzier/',
    '/api/newzealand/businessnz/',
    // China個別API（PBOC・NBS・SAFE等）
    '/api/china/pboc/',
    '/api/china/nbs/',
    '/api/china/safe/',
    '/api/china/mof/',
    '/api/china/bond-connect/',
    // Global個別API
    '/api/global/',
    // Market個別API（TSMC売上高、Fear & Greed等）
    '/api/market/tsmc/',
    '/api/market/fear-greed',
    '/api/market/advance-decline-ratio',
    '/api/market/nikkei-yoy',
    '/api/market/crude-oil-yoy',
    '/api/market/natural-gas-yoy',
    '/api/market/nikkei-double-inverse',
    '/api/market/jpx-investor-trading',
    '/api/market/gold-etf-holdings',
    '/api/market/gold-premium',
    '/api/market/wgc-gold-etf',
    '/api/market/sge-gold',
    '/api/market/china-gold-etf-balance',
    '/api/market/lbma-stock',
    '/api/market/silver-etf-holdings',
    '/api/market/weekly-crude-oil-inventories',
    '/api/market/cushing-inventory',
    '/api/market/distillate-fuel-inventories',
    '/api/market/gasoline-refinery',
    '/api/market/natural-gas-trade',
    '/api/market/natural-gas-storage',
    '/api/market/eu-natural-gas-storage',
    '/api/market/eu-natural-gas-production',
    '/api/market/noaa-hdd-cdd',
    '/api/market/roni',
    '/api/market/lng-exports-by-region',
    '/api/market/short-term-energy-outlook',
    '/api/market/steo-natural-gas',
    '/api/market/sp500-valuation',
    '/api/market/nasdaq100-valuation',
    '/api/market/nikkei225-valuation',
    '/api/market/topix-valuation',
    '/api/market/nikkei-regression',
    '/api/market/electronic-components-balance',
    '/api/market/jpx-pcr',
    '/api/market/cftc-positioning',
    '/api/market/crack-spread',
    '/api/market/vix-term-structure',
    '/api/market/historical-volatility',
    '/api/market/vix-cross-ratio',
    '/api/market/sector-ratio',
    '/api/market/copper-to-gold-ratio',
    '/api/market/russell2000-russell1000',
    '/api/market/financial-stress-index',
    '/api/market/nt-magnification',
    '/api/market/us-interest-rate-spread',
    '/api/market/corporate-bond-market-distress-index',
  ];
  const isDirectApi = directApiPatterns.some(pattern => indicator.apiEndpoint.startsWith(pattern));

  if (isDirectApi) {
    return {
      endpoint: indicator.apiEndpoint,
      dataKey: indicator.dataKey,
      valueField: indicator.valueField,
      nestedKey: indicator.nestedKey,
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
  valueField?: string,
  derived?: DerivedValueConfig
): DataPoint[] {
  if (!response.data || !Array.isArray(response.data)) {
    console.log('[useOverlayData] No market data in response');
    return [];
  }

  const field = valueField || 'close';

  // derived指定がある場合はextractIndicatorDataと同じ変換ロジックを使う
  if (derived) {
    const sorted = [...response.data].sort(
      (a, b) => getDateTimestamp(a.date) - getDateTimestamp(b.date)
    );
    const points: DataPoint[] = [];

    if (derived.type === 'yoy') {
      const period = derived.period ?? 365;
      if (period >= 100) {
        // 日数ベース（日次データ向け）
        const msWindow = period * 86400000;
        const tolerance = 7 * 86400000;
        const dateMap = new Map<number, number>();
        for (const item of sorted) {
          const val = item[derived.sourceField as keyof typeof item];
          if (typeof val === 'number' && !isNaN(val)) {
            dateMap.set(getDateTimestamp(item.date), val);
          }
        }
        for (const item of sorted) {
          const currentValue = item[derived.sourceField as keyof typeof item];
          if (typeof currentValue !== 'number' || isNaN(currentValue)) continue;
          const currentTs = getDateTimestamp(item.date);
          const targetTs = currentTs - msWindow;
          let bestPrev: number | null = null;
          let bestDist = Infinity;
          for (const [ts, val] of dateMap) {
            const dist = Math.abs(ts - targetTs);
            if (dist <= tolerance && dist < bestDist) {
              bestDist = dist;
              bestPrev = val;
            }
          }
          if (bestPrev !== null && bestPrev !== 0) {
            points.push({
              date: item.date,
              value: Math.round(((currentValue - bestPrev) / bestPrev) * 10000) / 100,
            });
          }
        }
      } else {
        for (let i = period; i < sorted.length; i++) {
          const cur = sorted[i][derived.sourceField as keyof typeof sorted[0]];
          const prev = sorted[i - period][derived.sourceField as keyof typeof sorted[0]];
          if (typeof cur === 'number' && typeof prev === 'number' && prev !== 0) {
            points.push({
              date: sorted[i].date,
              value: Math.round(((cur - prev) / prev) * 10000) / 100,
            });
          }
        }
      }
    } else if (derived.type === 'diff') {
      const period = derived.period ?? 1;
      for (let i = period; i < sorted.length; i++) {
        const cur = sorted[i][derived.sourceField as keyof typeof sorted[0]];
        const prev = sorted[i - period][derived.sourceField as keyof typeof sorted[0]];
        if (typeof cur === 'number' && typeof prev === 'number') {
          points.push({ date: sorted[i].date, value: cur - prev });
        }
      }
    }

    return points;
  }

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
  // dataKeyでデータを取得（ドット記法をサポート）
  let indicatorData: unknown;
  if (dataKey.includes('.')) {
    // ドット記法の場合、ネストされたパスを解決
    indicatorData = getNestedValue(response.data, dataKey);
  } else {
    indicatorData = response.data[dataKey] as unknown;
  }

  if (!indicatorData) {
    console.log('[useOverlayData] No indicator data for:', dataKey);
    return [];
  }

  // パターン: nestedKeyがドット記法で指定されている場合（例: annual_rates.total_hicp）
  // ECB HICPなど: { annual_rates: { total_hicp: [{date, value}], core_hicp: [{date, value}] } }
  if (nestedKey && nestedKey.includes('.')) {
    const nestedData = getNestedValue(indicatorData, nestedKey);
    if (Array.isArray(nestedData)) {
      console.log('[useOverlayData] Nested key dot notation pattern for:', dataKey, '.', nestedKey, 'length:', nestedData.length);
      return (nestedData as APIDataItem[])
        .filter(item => {
          const val = item.value;
          return val !== undefined && val !== null && typeof val === 'number';
        })
        .map(item => ({
          date: item.date,
          value: item.value as number,
        }));
    }
    console.log('[useOverlayData] Nested key dot notation data not found:', dataKey, '.', nestedKey);
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

  // パターン: housing_starts_permits のようなネスト構造
  // { housing_starts: { data: [{date, value, mom, yoy, qoq}], latest: {...} }, building_permits: { data: [...], latest: {...} } }
  if (nestedKey && dataKey === 'housing_starts_permits') {
    const dataObj = indicatorData as Record<string, { data?: Array<{ date: string; value: number | null; mom: number | null; yoy: number | null; qoq: number | null }> }>;
    const nestedData = dataObj[nestedKey];
    if (nestedData && nestedData.data && Array.isArray(nestedData.data)) {
      const field = valueField || 'value';
      console.log('[useOverlayData] Housing starts/permits pattern for:', nestedKey, 'field:', field, 'length:', nestedData.data.length);
      return nestedData.data
        .filter(item => {
          const val = item[field as keyof typeof item];
          return val !== undefined && val !== null && typeof val === 'number';
        })
        .map(item => ({
          date: item.date,
          value: item[field as keyof typeof item] as number,
        }));
    }
    console.log('[useOverlayData] Nested data not found:', nestedKey);
    return [];
  }

  // パターン: sp_pmi のようなネスト構造（S&P Global PMI）
  // { manufacturing: { data: [{date, value, forecast, previous}], latest: {...} }, services: {...}, composite: {...} }
  if (nestedKey && dataKey === 'sp_pmi') {
    const dataObj = indicatorData as Record<string, { data?: Array<{ date: string; value: number | null; forecast: number | null; previous: number | null }> }>;
    const nestedData = dataObj[nestedKey];
    if (nestedData && nestedData.data && Array.isArray(nestedData.data)) {
      const field = valueField || 'value';
      console.log('[useOverlayData] S&P PMI pattern for:', nestedKey, 'field:', field, 'length:', nestedData.data.length);
      return nestedData.data
        .filter(item => {
          const val = item[field as keyof typeof item];
          return val !== undefined && val !== null && typeof val === 'number';
        })
        .map(item => ({
          date: item.date,
          value: item[field as keyof typeof item] as number,
        }));
    }
    console.log('[useOverlayData] S&P PMI nested data not found:', nestedKey);
    return [];
  }

  // パターン: 汎用的なnestedKeyパターン（ドット記法でない場合）
  // ecb_inflation_expectations: { inflation_12m: [{date, value}], inflation_3y: [...] }
  // germany_cpi: { cpi_yoy: [{date, value}], cpi_mom: [...] }
  // germany_ppi: { ppi_yoy: [{date, value}], ppi_mom: [...] }
  if (nestedKey && !nestedKey.includes('.')) {
    const dataObj = indicatorData as Record<string, unknown>;
    const nestedData = dataObj[nestedKey];
    if (Array.isArray(nestedData)) {
      console.log('[useOverlayData] Generic nested key pattern for:', dataKey, '.', nestedKey, 'length:', nestedData.length);
      return (nestedData as APIDataItem[])
        .filter(item => {
          const val = item.value;
          return val !== undefined && val !== null && typeof val === 'number';
        })
        .map(item => ({
          date: item.date,
          value: item.value as number,
        }));
    }
    console.log('[useOverlayData] Generic nested key data not found:', dataKey, '.', nestedKey);
    // フォールスルー: 他のパターンも試す
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

  // パターン0.6: ny_inflation_expectations / michigan_inflation_expectations のような構造
  // { data: { one_year: [{date, value}], three_year: [{date, value}], five_year: [{date, value}] }, latest: {...} }
  if ((dataKey === 'ny_inflation_expectations' || dataKey === 'michigan_inflation_expectations') && valueField) {
    const dataObj = indicatorData as { data?: Record<string, Array<{ date: string; value: number }>> };
    if (dataObj.data && typeof dataObj.data === 'object') {
      const seriesData = dataObj.data[valueField];
      if (Array.isArray(seriesData)) {
        console.log('[useOverlayData] Inflation Expectations pattern for:', dataKey, '.', valueField, 'length:', seriesData.length);
        return seriesData
          .filter(item => item.value !== undefined && item.value !== null && typeof item.value === 'number')
          .map(item => ({
            date: item.date,
            value: item.value,
          }));
      }
    }
    console.log('[useOverlayData] No Inflation Expectations data for:', dataKey, '.', valueField);
    return [];
  }

  // パターン1: 直接配列の場合 (例: gdp_growth_rate: [{date, value}])
  if (Array.isArray(indicatorData)) {
    // valueFieldが指定されている場合はそのフィールドを使用、なければ'value'
    const field = valueField || 'value';
    console.log('[useOverlayData] Direct array pattern for:', dataKey, 'valueField:', field, 'length:', indicatorData.length);
    const rawPoints = (indicatorData as APIDataItem[])
      .filter(item => {
        const val = item[field];
        return val !== undefined && val !== null && typeof val === 'number';
      })
      .map(item => ({
        date: item.date,
        value: item[field] as number,
      }));

    // derived変換を適用（qoq_pct / yoy_pct / qoq_diff など）
    if (derived && rawPoints.length > 0) {
      if (derived.type === 'qoq_pct') {
        return computeQuarterlyPctChange(rawPoints, 'qoq');
      }
      if (derived.type === 'yoy_pct') {
        return computeQuarterlyPctChange(rawPoints, 'yoy');
      }
      if (derived.type === 'qoq_diff') {
        return computeQuarterlyDiff(rawPoints);
      }
      if (derived.type === 'diff') {
        const period = derived.period ?? 1;
        const sorted = [...rawPoints].sort((a, b) => getDateTimestamp(a.date) - getDateTimestamp(b.date));
        const result: DataPoint[] = [];
        for (let i = period; i < sorted.length; i++) {
          result.push({ date: sorted[i].date, value: sorted[i].value - sorted[i - period].value });
        }
        return result;
      }
      if (derived.type === 'yoy') {
        const period = derived.period ?? 12;
        const sorted = [...rawPoints].sort((a, b) => getDateTimestamp(a.date) - getDateTimestamp(b.date));
        const result: DataPoint[] = [];
        for (let i = period; i < sorted.length; i++) {
          const cur = sorted[i].value;
          const prev = sorted[i - period].value;
          if (prev !== 0) {
            result.push({
              date: sorted[i].date,
              value: Math.round(((cur - prev) / prev) * 10000) / 100,
            });
          }
        }
        return result;
      }
    }

    return rawPoints;
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

    const sorted = [...data].sort((a, b) => getDateTimestamp(a.date) - getDateTimestamp(b.date));
    const points: DataPoint[] = [];

    if (derived.type === 'ratio' && derived.denominatorFields) {
      // ratio: sourceField / sum(denominatorFields) * 100
      for (const item of sorted) {
        const rawNumerator = getNestedValue(item, derived.sourceField);
        const numerator = typeof rawNumerator === 'number' && !isNaN(rawNumerator) ? rawNumerator : null;
        if (numerator === null) continue;

        let denominator = 0;
        let valid = true;
        for (const field of derived.denominatorFields) {
          const rawVal = getNestedValue(item, field);
          if (typeof rawVal !== 'number' || isNaN(rawVal)) { valid = false; break; }
          denominator += rawVal;
        }
        if (!valid || denominator === 0) continue;

        points.push({ date: item.date, value: Math.round((numerator / denominator) * 10000) / 100 });
      }
    } else if (derived.type === 'yoy') {
      // yoy: (current - yearAgo) / yearAgo * 100
      // 日次データの場合は日付ベースで約365日前を探す、月次データの場合はperiod(デフォルト12)で探す
      const dateMap = new Map<number, { value: number; date: string }>();
      for (const item of sorted) {
        const rawVal = getNestedValue(item, derived.sourceField);
        const val = typeof rawVal === 'number' && !isNaN(rawVal) ? rawVal : null;
        if (val !== null) {
          dateMap.set(getDateTimestamp(item.date), { value: val, date: item.date });
        }
      }
      const period = derived.period ?? 12;
      if (period >= 100) {
        // 日数ベース（日次データ向け: period=365）
        const msWindow = period * 86400000;
        const tolerance = 7 * 86400000; // ±7日の許容範囲
        for (const item of sorted) {
          const rawCurrent = getNestedValue(item, derived.sourceField);
          const currentValue = typeof rawCurrent === 'number' && !isNaN(rawCurrent) ? rawCurrent : null;
          if (currentValue === null) continue;
          const currentTs = getDateTimestamp(item.date);
          const targetTs = currentTs - msWindow;
          // targetTs ± tolerance 内で最も近いデータポイントを探す
          let bestPrev: number | null = null;
          let bestDist = Infinity;
          for (const [ts, entry] of dateMap) {
            const dist = Math.abs(ts - targetTs);
            if (dist <= tolerance && dist < bestDist) {
              bestDist = dist;
              bestPrev = entry.value;
            }
          }
          if (bestPrev !== null && bestPrev !== 0) {
            points.push({
              date: item.date,
              value: Math.round(((currentValue - bestPrev) / bestPrev) * 10000) / 100,
            });
          }
        }
      } else {
        // インデックスベース（月次データ向け: period=12）
        for (let i = period; i < sorted.length; i++) {
          const rawCurrent = getNestedValue(sorted[i], derived.sourceField);
          const rawPrev = getNestedValue(sorted[i - period], derived.sourceField);
          const currentValue = typeof rawCurrent === 'number' && !isNaN(rawCurrent) ? rawCurrent : null;
          const prevValue = typeof rawPrev === 'number' && !isNaN(rawPrev) ? rawPrev : null;
          if (currentValue !== null && prevValue !== null && prevValue !== 0) {
            points.push({
              date: sorted[i].date,
              value: Math.round(((currentValue - prevValue) / prevValue) * 10000) / 100,
            });
          }
        }
      }
    } else {
      // diff: current - prev
      const period = derived.period ?? 1;
      for (let i = period; i < sorted.length; i++) {
        const rawCurrent = getNestedValue(sorted[i], derived.sourceField);
        const rawPrev = getNestedValue(sorted[i - period], derived.sourceField);
        const currentValue = typeof rawCurrent === 'number' && !isNaN(rawCurrent) ? rawCurrent : null;
        const prevValue = typeof rawPrev === 'number' && !isNaN(rawPrev) ? rawPrev : null;
        if (currentValue !== null && prevValue !== null) {
          points.push({ date: sorted[i].date, value: currentValue - prevValue });
        }
      }
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
        const result = extractMarketData(data, mapping.valueField, mapping.derived);
        console.log('[useOverlayData] Extracted', result.length, 'market data points for', indicator.id);
        return result;
      }

      // 個別API（nyfed, fed-h15, uk等）の場合は専用の抽出ロジックを使用
      if (mapping.isDirectApi) {
        const data = await response.json();
        const result = extractDirectApiData(data, mapping.dataKey, mapping.valueField, mapping.nestedKey);
        console.log('[useOverlayData] Extracted', result.length, 'direct API points for', indicator.id);
        return result;
      }

      // 通常の指標データ（/dashboard形式）
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
  valueField?: string,
  nestedKey?: string
): DataPoint[] {
  const data = response as Record<string, unknown>;

  // パターン: ドット記法のdataKey（例: manufacturing.data）
  // { manufacturing: { data: [{date, value}], latest: {...} }, services: {...} }
  if (dataKey.includes('.')) {
    const indicatorData = getNestedValue(data, dataKey);
    if (Array.isArray(indicatorData)) {
      const field = valueField || 'value';
      console.log('[useOverlayData] Direct API dot notation pattern for:', dataKey, 'field:', field, 'length:', indicatorData.length);
      return (indicatorData as DirectApiDataItem[])
        .filter((item) => {
          const val = item[field];
          return val !== undefined && val !== null && typeof val === 'number';
        })
        .map((item) => ({
          date: item.date,
          value: item[field] as number,
        }));
    }
    // パターン: 並列配列構造（DMP等）
    // { date: ["2022-05", ...], expected_3mo_avg: [0.057, ...] }
    const parallelData = indicatorData as Record<string, unknown> | undefined;
    if (parallelData && Array.isArray(parallelData.date)) {
      const field = valueField || 'value';
      const dates = parallelData.date as string[];
      const values = parallelData[field] as number[] | undefined;
      if (values && Array.isArray(values)) {
        console.log('[useOverlayData] Direct API parallel arrays pattern for:', dataKey, 'field:', field, 'length:', dates.length);
        const result: DataPoint[] = [];
        for (let i = 0; i < dates.length; i++) {
          if (values[i] !== undefined && values[i] !== null && typeof values[i] === 'number') {
            result.push({ date: dates[i], value: values[i] });
          }
        }
        return result;
      }
    }
    console.log('[useOverlayData] No data found for dot notation dataKey:', dataKey);
    return [];
  }

  // パターン: series 配列構造 (GDP構成要素)
  // { series: [{ name: '民間最終消費支出', data: [{date, value}] }, ...] }
  if (dataKey === 'series' && nestedKey) {
    const seriesArray = data.series as Array<{ name: string; data: Array<{ date: string; value: number }> }> | undefined;
    if (seriesArray && Array.isArray(seriesArray)) {
      const series = seriesArray.find(s => s.name === nestedKey);
      if (series && series.data) {
        const field = valueField || 'value';
        console.log('[useOverlayData] Series pattern for:', nestedKey, 'field:', field, 'length:', series.data.length);
        return series.data
          .filter(item => {
            const val = item[field as keyof typeof item];
            return val !== undefined && val !== null && typeof val === 'number';
          })
          .map(item => ({
            date: item.date,
            value: item[field as keyof typeof item] as number,
          }));
      }
      console.log('[useOverlayData] Series not found:', nestedKey);
    }
    return [];
  }

  // パターン: トップレベルにdataKeyがある場合（UK GDP等）
  // { qoq: [{date, qoq_change, ...}], yoy: [{date, yoy_change, ...}] }
  const topLevelData = data[dataKey] as DirectApiDataItem[] | undefined;
  if (topLevelData && Array.isArray(topLevelData)) {
    const field = valueField || 'value';
    console.log('[useOverlayData] Top-level dataKey pattern for:', dataKey, 'field:', field, 'length:', topLevelData.length);
    return topLevelData
      .filter((item) => {
        const val = item[field];
        return val !== undefined && val !== null && typeof val === 'number';
      })
      .map((item) => ({
        date: item.date,
        value: item[field] as number,
      }));
  }

  // 通常のdata配列形式
  const dataArray = data.data as DirectApiDataItem[] | undefined;
  if (!dataArray || !Array.isArray(dataArray)) {
    console.log('[useOverlayData] No data array in direct API response for:', dataKey);
    return [];
  }

  const field = valueField || dataKey;

  return dataArray
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
    return extractMarketData(data as MarketAPIResponse, mapping.valueField, mapping.derived);
  }
  // 個別API（nyfed, fed-h15等）の場合
  else if (mapping.isDirectApi) {
    const points = extractDirectApiData(data, mapping.dataKey, mapping.valueField, mapping.nestedKey);
    // derived変換を適用
    if (mapping.derived && points.length > 0) {
      if (mapping.derived.type === 'qoq_pct') {
        return computeQuarterlyPctChange(points, 'qoq');
      }
      if (mapping.derived.type === 'yoy_pct') {
        return computeQuarterlyPctChange(points, 'yoy');
      }
      if (mapping.derived.type === 'qoq_diff') {
        return computeQuarterlyDiff(points);
      }
      if (mapping.derived.type === 'yoy') {
        // (current - prev) / prev * 100 : period個前との前年比
        const period = mapping.derived.period ?? 12;
        const sorted = [...points].sort((a, b) => getDateTimestamp(a.date) - getDateTimestamp(b.date));
        const result: DataPoint[] = [];
        for (let i = period; i < sorted.length; i++) {
          const cur = sorted[i].value;
          const prev = sorted[i - period].value;
          if (cur !== null && prev !== null && prev !== 0) {
            result.push({
              date: sorted[i].date,
              value: Math.round(((cur - prev) / prev) * 10000) / 100,
            });
          }
        }
        return result;
      }
      if (mapping.derived.type === 'diff') {
        const period = mapping.derived.period ?? 1;
        const sorted = [...points].sort((a, b) => getDateTimestamp(a.date) - getDateTimestamp(b.date));
        const result: DataPoint[] = [];
        for (let i = period; i < sorted.length; i++) {
          const cur = sorted[i].value;
          const prev = sorted[i - period].value;
          if (cur !== null && prev !== null) {
            result.push({ date: sorted[i].date, value: cur - prev });
          }
        }
        return result;
      }
    }
    return points;
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
