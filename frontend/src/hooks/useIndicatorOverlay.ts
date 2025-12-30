/**
 * 指標オーバーレイフック
 * データ結合・変換・軸判定を一括管理
 */

import { useMemo, useState, useCallback, useEffect } from 'react';
import {
  mergeWithFrequencyAwareness,
  type DataPoint,
  type MergedDataPoint,
} from '../utils/dataAlignment';
import { transformToIndex100 } from '../utils/transforms';
import {
  type OverlayIndicator,
  type OverlaySettings,
  type OverlayConfig,
  type IndicatorFrequency,
  DEFAULT_OVERLAY_SETTINGS,
  getOverlayColor,
  getFrequencyLabel,
  getOverlayStorageKey,
} from '../constants/overlayConfig';

// =============================================================================
// 型定義
// =============================================================================

export interface OverlayData {
  indicator: OverlayIndicator;
  data: DataPoint[];
}

export interface OverlayChipInfo {
  id: string;
  label: string;
  color: string;
  frequency: string;
  axis: string;
  onRemove: () => void;
}

export interface AdditionalLineConfig {
  dataKey: string;
  color: string;
  name: string;
  strokeWidth: number;
  yAxisId: string;
  strokeDasharray?: string;
  seriesType?: 'line' | 'bar';
}

export interface RightYAxisConfig {
  id: string;
  domain: [number, number];
  ticks?: number[];
  color?: string;
}

export interface UseIndicatorOverlayResult {
  // 状態
  selectedOverlays: OverlayConfig[];

  // マージ済みデータ（ZoomableChartのdata用）
  mergedData: MergedDataPoint[];

  // additionalLines設定
  additionalLines: AdditionalLineConfig[];

  // 右Y軸設定（必要な場合のみ）
  rightYAxes: RightYAxisConfig[] | undefined;

  // チップ情報
  overlayChips: OverlayChipInfo[];

  // X軸の基準となる頻度（最も細かい頻度）
  baseFrequency: IndicatorFrequency;

  // アクション
  addOverlay: (indicator: OverlayIndicator, data: DataPoint[]) => void;
  removeOverlay: (indicatorId: string) => void;
  updateOverlaySettings: (indicatorId: string, settings: Partial<OverlaySettings>) => void;
  clearAllOverlays: () => void;

  // 比較中かどうか
  hasOverlays: boolean;
}

// =============================================================================
// メインフック
// =============================================================================

export function useIndicatorOverlay(
  mainIndicatorId: string,
  mainData: DataPoint[],
  mainFrequency: IndicatorFrequency = 'monthly'
): UseIndicatorOverlayResult {
  // ==========================================================================
  // 状態管理
  // ==========================================================================

  const [overlays, setOverlays] = useState<
    { config: OverlayConfig; data: DataPoint[] }[]
  >([]);

  // ==========================================================================
  // localStorage からの復元
  // ==========================================================================

  useEffect(() => {
    const storageKey = getOverlayStorageKey(mainIndicatorId);
    const saved = localStorage.getItem(storageKey);

    if (saved) {
      try {
        // 保存された設定からデータは復元できないため、設定のみ保持
        // データはaddOverlay時に渡される
        // TODO: 将来的にはここで設定を復元し、データ再取得を行う
        JSON.parse(saved);
      } catch {
        // パースエラーは無視
      }
    }
  }, [mainIndicatorId]);

  // ==========================================================================
  // localStorage への保存
  // ==========================================================================

  useEffect(() => {
    const storageKey = getOverlayStorageKey(mainIndicatorId);
    const configs = overlays.map(o => o.config);

    if (configs.length > 0) {
      localStorage.setItem(storageKey, JSON.stringify(configs));
    } else {
      localStorage.removeItem(storageKey);
    }
  }, [overlays, mainIndicatorId]);

  // ==========================================================================
  // アクション
  // ==========================================================================

  const addOverlay = useCallback(
    (indicator: OverlayIndicator, data: DataPoint[]) => {
      console.log('[useIndicatorOverlay] addOverlay called:', indicator.id, 'data points:', data.length);
      setOverlays(prev => {
        // 既に追加されている場合はスキップ
        if (prev.some(o => o.config.indicator.id === indicator.id)) {
          console.log('[useIndicatorOverlay] Already exists, skipping');
          return prev;
        }

        // 最大3本まで
        if (prev.length >= 3) {
          console.log('[useIndicatorOverlay] Max overlays reached');
          return prev;
        }

        console.log('[useIndicatorOverlay] Adding overlay to state');
        return [
          ...prev,
          {
            config: {
              indicator,
              settings: { ...DEFAULT_OVERLAY_SETTINGS },
            },
            data,
          },
        ];
      });
    },
    []
  );

  const removeOverlay = useCallback((indicatorId: string) => {
    setOverlays(prev => prev.filter(o => o.config.indicator.id !== indicatorId));
  }, []);

  const updateOverlaySettings = useCallback(
    (indicatorId: string, settings: Partial<OverlaySettings>) => {
      setOverlays(prev =>
        prev.map(o => {
          if (o.config.indicator.id === indicatorId) {
            return {
              ...o,
              config: {
                ...o.config,
                settings: { ...o.config.settings, ...settings },
              },
            };
          }
          return o;
        })
      );
    },
    []
  );

  const clearAllOverlays = useCallback(() => {
    setOverlays([]);
  }, []);

  // ==========================================================================
  // データマージ（頻度認識）
  // ==========================================================================

  const { mergedData, axisAssignments, baseFrequency } = useMemo(() => {
    console.log('[useIndicatorOverlay] Computing mergedData, overlays:', overlays.length, 'mainData:', mainData.length);
    if (overlays.length === 0 || mainData.length === 0) {
      return {
        mergedData: mainData.map(d => ({ date: d.date, value: d.value })),
        axisAssignments: {} as Record<string, string>,
        baseFrequency: mainFrequency,
      };
    }

    // 頻度認識マージを使用
    const overlayInputs = overlays.map(o => ({
      key: o.config.indicator.id,
      data: o.data,
      frequency: o.config.indicator.frequency,
    }));
    console.log('[useIndicatorOverlay] overlayInputs:', overlayInputs.map(i => ({ key: i.key, dataLen: i.data.length, freq: i.frequency })));

    const { mergedData: merged, baseFrequency: detectedBaseFreq } = mergeWithFrequencyAwareness(
      mainData,
      mainFrequency,
      overlayInputs
    );
    console.log('[useIndicatorOverlay] merged data length:', merged.length, 'baseFrequency:', detectedBaseFreq);
    if (merged.length > 0) {
      console.log('[useIndicatorOverlay] merged sample:', merged[0]);
    }

    // 常に右軸を使用（左軸は不具合が起きるため）
    const assignments: Record<string, string> = {};
    for (const [index, overlay] of overlays.entries()) {
      assignments[overlay.config.indicator.id] = `right-${index + 1}`;
    }
    console.log('[useIndicatorOverlay] axisAssignments:', assignments);

    return { mergedData: merged, axisAssignments: assignments, baseFrequency: detectedBaseFreq };
  }, [mainData, mainFrequency, overlays]);

  // ==========================================================================
  // Index100変換の適用
  // ==========================================================================

  const transformedData = useMemo(() => {
    // Index100に変換するキーを特定
    const index100Keys = overlays
      .filter(o => o.config.settings.transform === 'index100')
      .map(o => o.config.indicator.id);

    // メインデータもIndex100の場合（将来対応）
    // 現在はオーバーレイのみ対応

    if (index100Keys.length === 0) {
      return mergedData;
    }

    return transformToIndex100(mergedData, index100Keys);
  }, [mergedData, overlays]);

  // ==========================================================================
  // additionalLines設定
  // ==========================================================================

  const additionalLines = useMemo<AdditionalLineConfig[]>(() => {
    const lines = overlays.map((overlay, index) => {
      const { indicator } = overlay.config;
      const axis = axisAssignments[indicator.id] || 'left';
      const seriesType = indicator.chartType === 'bar' ? 'bar' as const : 'line' as const;

      return {
        dataKey: indicator.id,
        color: getOverlayColor(index),
        name: indicator.name,
        strokeWidth: 1.5,
        yAxisId: axis,
        strokeDasharray: seriesType === 'line' ? '5 5' : undefined,
        seriesType,
      };
    });
    console.log('[useIndicatorOverlay] additionalLines:', lines);
    return lines;
  }, [overlays, axisAssignments]);

  // ==========================================================================
  // 右Y軸設定
  // ==========================================================================

  
const rightYAxes = useMemo<RightYAxisConfig[] | undefined>(() => {
  if (overlays.length === 0) {
    return undefined;
  }

  const axes: RightYAxisConfig[] = [];

  for (const [index, overlay] of overlays.entries()) {
    const indicatorId = overlay.config.indicator.id;
    const values = transformedData
      .map(d => (d as Record<string, unknown>)[indicatorId])
      .filter((v): v is number => typeof v === 'number' && !isNaN(v));

    if (values.length === 0) {
      axes.push({
        id: `right-${index + 1}`,
        domain: [0, 1],
        color: getOverlayColor(index),
      });
      continue;
    }

    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = (max - min) * 0.1 || 1;

    axes.push({
      id: `right-${index + 1}`,
      domain: [min - padding, max + padding],
      color: getOverlayColor(index),
    });
  }

  return axes;
}, [overlays, transformedData]);



  // ==========================================================================
  // チップ情報
  // ==========================================================================

  const overlayChips = useMemo<OverlayChipInfo[]>(() => {
    return overlays.map((overlay, index) => {
      const { indicator, settings } = overlay.config;
      const axis = axisAssignments[indicator.id] || 'left';

      // ラベル構築: "NY連銀 月次 右軸"
      const parts = [
        indicator.name,
        getFrequencyLabel(indicator.frequency),
      ];

      if (axis === 'right') {
        parts.push('右軸');
      }

      if (settings.transform === 'index100') {
        parts.push('Index');
      }

      return {
        id: indicator.id,
        label: parts.join(' '),
        color: getOverlayColor(index),
        frequency: getFrequencyLabel(indicator.frequency),
        axis,
        onRemove: () => removeOverlay(indicator.id),
      };
    });
  }, [overlays, axisAssignments, removeOverlay]);

  // ==========================================================================
  // 戻り値
  // ==========================================================================

  return {
    selectedOverlays: overlays.map(o => o.config),
    mergedData: transformedData,
    additionalLines,
    rightYAxes,
    overlayChips,
    baseFrequency,
    addOverlay,
    removeOverlay,
    updateOverlaySettings,
    clearAllOverlays,
    hasOverlays: overlays.length > 0,
  };
}

// =============================================================================
// ヘルパーフック: オーバーレイデータの取得
// =============================================================================

/**
 * 指標IDからデータを取得するためのフック
 * 実際のAPI呼び出しは各チャートコンポーネントの既存フックを使用
 */
export function useOverlayDataFetcher() {
  // このフックは各チャートコンポーネントで
  // useDashboardDataなどの既存フックを使用してデータを取得し、
  // addOverlayに渡す形で使用
  return null;
}
