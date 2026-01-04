/**
 * チャートオーバーレイ統合フック
 * オーバーレイ管理ロジックを一元化し、各チャートコンポーネントの重複コードを削減
 */

import { useState, useCallback, useEffect } from 'react';
import { useIndicatorOverlay, type UseIndicatorOverlayResult } from './useIndicatorOverlay';
import { useOverlayIndicatorData } from './useOverlayData';
import type { OverlayIndicator, IndicatorFrequency } from '../constants/overlayConfig';
import type { DataPoint } from '../utils/dataAlignment';

// =============================================================================
// 型定義
// =============================================================================

export interface UseChartWithOverlayResult extends UseIndicatorOverlayResult {
  /** 指標選択ハンドラ（ComparePopoverのonSelectに渡す） */
  handleSelectIndicator: (indicator: OverlayIndicator) => void;
  /** オーバーレイデータ取得中かどうか */
  isLoadingOverlay: boolean;
  /** 破線スタイルを適用したadditionalLines */
  enhancedAdditionalLines: Array<{
    dataKey: string;
    color: string;
    name: string;
    strokeWidth: number;
    yAxisId: string;
    strokeDasharray: string;
    seriesType?: 'line' | 'bar';
  }>;
}

// =============================================================================
// メインフック
// =============================================================================

/**
 * チャートオーバーレイ統合フック
 *
 * @param mainIndicatorId メイン指標のID（overlayConfig.tsに登録されているID）
 * @param chartData チャートデータ（date, valueを含む配列）
 * @param frequency メイン指標の頻度
 * @returns オーバーレイ管理に必要な状態とアクション
 *
 * @example
 * ```tsx
 * const {
 *   selectedOverlays,
 *   mergedData,
 *   enhancedAdditionalLines,
 *   rightYAxes,
 *   overlayChips,
 *   baseFrequency,
 *   handleSelectIndicator,
 *   clearAllOverlays,
 *   hasOverlays,
 *   isLoadingOverlay,
 * } = useChartWithOverlay('ism_manufacturing', chartData, 'monthly');
 * ```
 */
export function useChartWithOverlay<T extends { date: string }>(
  mainIndicatorId: string,
  chartData: T[],
  frequency: IndicatorFrequency = 'monthly'
): UseChartWithOverlayResult {
  // 選択待ちの指標（データ取得中）
  const [pendingIndicator, setPendingIndicator] = useState<OverlayIndicator | null>(null);

  // ベースのオーバーレイ管理フック
  const overlay = useIndicatorOverlay(mainIndicatorId, chartData as unknown as DataPoint[], frequency);

  // 選択中の指標のデータを取得
  const {
    data: overlayData,
    isLoading: isLoadingOverlay,
    indicatorId: fetchedIndicatorId,
    isSuccess,
  } = useOverlayIndicatorData(pendingIndicator);

  // オーバーレイデータが取得できたら追加
  useEffect(() => {
    if (
      pendingIndicator &&
      fetchedIndicatorId === pendingIndicator.id &&
      isSuccess &&
      !isLoadingOverlay &&
      overlayData &&
      overlayData.length > 0
    ) {
      overlay.addOverlay(pendingIndicator, overlayData);
      setPendingIndicator(null);
    }
  }, [pendingIndicator, overlayData, overlay.addOverlay, isLoadingOverlay, fetchedIndicatorId, isSuccess]);

  // 指標選択ハンドラ
  const handleSelectIndicator = useCallback((indicator: OverlayIndicator) => {
    setPendingIndicator(indicator);
  }, []);

  // 破線スタイルを適用したadditionalLines
  const enhancedAdditionalLines = overlay.additionalLines.map(line => ({
    ...line,
    strokeDasharray: line.seriesType === 'bar' ? '' : '5 5',
  }));

  return {
    ...overlay,
    handleSelectIndicator,
    isLoadingOverlay,
    enhancedAdditionalLines,
  };
}

export default useChartWithOverlay;
