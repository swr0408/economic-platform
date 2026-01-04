/**
 * 比較ページ用の状態管理フック
 * URLパラメータと同期して状態を管理
 */

import { useState, useCallback, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  type OverlayIndicator,
  getIndicatorById,
  OVERLAY_INDICATORS,
} from '../constants/overlayConfig';

// =============================================================================
// 型定義
// =============================================================================

export type RangeType = '1Y' | '3Y' | '5Y' | '10Y' | 'Max';

export interface CompareOptions {
  index100: boolean;
}

export interface UseCompareStateResult {
  // 選択中の指標ID配列
  selectedIndicatorIds: string[];
  // 選択中の指標オブジェクト配列
  selectedIndicators: OverlayIndicator[];
  // 期間設定
  range: RangeType;
  // オプション
  options: CompareOptions;
  // アクション
  addIndicator: (indicatorId: string) => void;
  removeIndicator: (indicatorId: string) => void;
  setRange: (range: RangeType) => void;
  setOptions: (options: CompareOptions) => void;
  clearAll: () => void;
  // 最大選択数
  maxSelections: number;
  // 追加可能かどうか
  canAddMore: boolean;
}

// =============================================================================
// 定数
// =============================================================================

const MAX_SELECTIONS = 6;
const DEFAULT_RANGE: RangeType = '5Y';

// =============================================================================
// メインフック
// =============================================================================

export function useCompareState(): UseCompareStateResult {
  const [searchParams, setSearchParams] = useSearchParams();

  // URLからstate復元
  const initialIndicatorIds = useMemo(() => {
    return searchParams.getAll('s').filter(id => {
      // 指標が存在するか確認
      return OVERLAY_INDICATORS.some(i => i.id === id);
    });
  }, []);

  const initialRange = useMemo(() => {
    const rangeParam = searchParams.get('range');
    if (rangeParam && ['1Y', '3Y', '5Y', '10Y', 'Max'].includes(rangeParam)) {
      return rangeParam as RangeType;
    }
    return DEFAULT_RANGE;
  }, []);

  const initialIndex100 = useMemo(() => {
    return searchParams.get('index100') === 'true';
  }, []);

  // State
  const [selectedIndicatorIds, setSelectedIndicatorIds] = useState<string[]>(initialIndicatorIds);
  const [range, setRangeState] = useState<RangeType>(initialRange);
  const [options, setOptionsState] = useState<CompareOptions>({
    index100: initialIndex100,
  });

  // URL同期
  useEffect(() => {
    const params = new URLSearchParams();

    // 指標ID（複数）
    selectedIndicatorIds.forEach(id => params.append('s', id));

    // 期間（デフォルト以外のみ）
    if (range !== DEFAULT_RANGE) {
      params.set('range', range);
    }

    // オプション（trueのみ）
    if (options.index100) {
      params.set('index100', 'true');
    }

    setSearchParams(params, { replace: true });
  }, [selectedIndicatorIds, range, options, setSearchParams]);

  // 指標追加
  const addIndicator = useCallback((indicatorId: string) => {
    setSelectedIndicatorIds(prev => {
      // 既に追加済み
      if (prev.includes(indicatorId)) {
        return prev;
      }
      // 最大数に達している
      if (prev.length >= MAX_SELECTIONS) {
        return prev;
      }
      // 指標が存在しない
      if (!OVERLAY_INDICATORS.some(i => i.id === indicatorId)) {
        console.warn('[useCompareState] Unknown indicator:', indicatorId);
        return prev;
      }
      return [...prev, indicatorId];
    });
  }, []);

  // 指標削除
  const removeIndicator = useCallback((indicatorId: string) => {
    setSelectedIndicatorIds(prev => prev.filter(id => id !== indicatorId));
  }, []);

  // 期間設定
  const setRange = useCallback((newRange: RangeType) => {
    setRangeState(newRange);
  }, []);

  // オプション設定
  const setOptions = useCallback((newOptions: CompareOptions) => {
    setOptionsState(newOptions);
  }, []);

  // 全解除
  const clearAll = useCallback(() => {
    setSelectedIndicatorIds([]);
  }, []);

  // 選択中の指標オブジェクト
  const selectedIndicators = useMemo(() => {
    return selectedIndicatorIds
      .map(id => getIndicatorById(id))
      .filter((indicator): indicator is OverlayIndicator => indicator !== undefined);
  }, [selectedIndicatorIds]);

  // 追加可能かどうか
  const canAddMore = selectedIndicatorIds.length < MAX_SELECTIONS;

  return {
    selectedIndicatorIds,
    selectedIndicators,
    range,
    options,
    addIndicator,
    removeIndicator,
    setRange,
    setOptions,
    clearAll,
    maxSelections: MAX_SELECTIONS,
    canAddMore,
  };
}

// =============================================================================
// ヘルパー: 期間からフィルタリング用の開始日を計算
// =============================================================================

export function getStartDateFromRange(range: RangeType): Date | null {
  const now = new Date();

  switch (range) {
    case '1Y':
      return new Date(now.getFullYear() - 1, now.getMonth(), now.getDate());
    case '3Y':
      return new Date(now.getFullYear() - 3, now.getMonth(), now.getDate());
    case '5Y':
      return new Date(now.getFullYear() - 5, now.getMonth(), now.getDate());
    case '10Y':
      return new Date(now.getFullYear() - 10, now.getMonth(), now.getDate());
    case 'Max':
      return null; // 全期間
    default:
      return null;
  }
}

// =============================================================================
// ヘルパー: データを期間でフィルタリング
// =============================================================================

export function filterDataByRange<T extends { date: string }>(
  data: T[],
  range: RangeType
): T[] {
  const startDate = getStartDateFromRange(range);

  if (!startDate) {
    return data;
  }

  return data.filter(item => {
    const itemDate = new Date(item.date);
    return itemDate >= startDate;
  });
}
