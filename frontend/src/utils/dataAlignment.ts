/**
 * データ整列ユーティリティ
 * As-of Join（ポインタ法）による高速なデータ結合
 * 頻度認識マージ対応
 */

import type { IndicatorFrequency } from '../constants/overlayConfig';

export interface DataPoint {
  date: string;
  value: number;
}

export interface DataPointWithFrequency extends DataPoint {
  frequency?: IndicatorFrequency;
}

export interface MergedDataPoint {
  date: string;
  value: number | null;
  [key: string]: string | number | null;
}

/**
 * As-of Join: ポインタ法による高速マージ O(N + M)
 *
 * 基準データの各日付に対して、比較データの「その日以前の直近値」を取得。
 * filter/二分探索より効率的。
 *
 * @param baseDates 基準データの日付配列（ソート済み）
 * @param overlayPoints 比較データ（ソート済み）
 * @returns 基準日付に対応する比較値の配列（発表前はnull）
 */
export function asOfJoin(
  baseDates: string[],
  overlayPoints: DataPoint[]
): (number | null)[] {
  const result: (number | null)[] = [];

  if (overlayPoints.length === 0) {
    return baseDates.map(() => null);
  }

  let overlayIdx = 0;

  for (const baseDate of baseDates) {
    // overlayIdx を baseDate 以下の最大位置まで進める
    while (
      overlayIdx < overlayPoints.length &&
      overlayPoints[overlayIdx].date <= baseDate
    ) {
      overlayIdx++;
    }

    // overlayIdx - 1 が「その日以前の直近値」
    if (overlayIdx > 0) {
      result.push(overlayPoints[overlayIdx - 1].value);
    } else {
      result.push(null); // 発表前はnull
    }
  }

  return result;
}

/**
 * 複数の比較データを基準データにマージ
 *
 * @param baseData 基準データ
 * @param overlays 比較データの配列（キーとデータのペア）
 * @returns マージ済みデータ
 */
export function mergeOverlayData(
  baseData: DataPoint[],
  overlays: { key: string; data: DataPoint[] }[]
): MergedDataPoint[] {
  if (baseData.length === 0) {
    return [];
  }

  // 基準データをソート
  const sortedBase = [...baseData].sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
  );

  const baseDates = sortedBase.map(d => d.date);

  // 各比較データをマージ
  const overlayValues: Record<string, (number | null)[]> = {};

  for (const overlay of overlays) {
    // 比較データをソート
    const sortedOverlay = [...overlay.data].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    );

    overlayValues[overlay.key] = asOfJoin(baseDates, sortedOverlay);
  }

  // 結果を構築
  return sortedBase.map((basePoint, idx) => {
    const merged: MergedDataPoint = {
      date: basePoint.date,
      value: basePoint.value,
    };

    for (const [key, values] of Object.entries(overlayValues)) {
      merged[key] = values[idx];
    }

    return merged;
  });
}

/**
 * P5-P95レンジを計算（外れ値耐性）
 *
 * @param values 値の配列
 * @returns [P5, P95] のタプル
 */
export function getP5P95Range(values: number[]): [number, number] {
  if (values.length === 0) {
    return [0, 0];
  }

  const validValues = values.filter(v => v !== null && !isNaN(v));
  if (validValues.length === 0) {
    return [0, 0];
  }

  const sorted = [...validValues].sort((a, b) => a - b);
  const p5Idx = Math.floor(sorted.length * 0.05);
  const p95Idx = Math.min(Math.floor(sorted.length * 0.95), sorted.length - 1);

  return [sorted[p5Idx], sorted[p95Idx]];
}

/**
 * 右Y軸が必要かどうかを判定
 *
 * P5-P95レンジで比較し、3倍以上の差があれば右軸を推奨
 *
 * @param mainValues メイン指標の値
 * @param overlayValues 比較指標の値
 * @returns 右軸が必要ならtrue
 */
export function shouldUseRightAxis(
  mainValues: number[],
  overlayValues: (number | null)[]
): boolean {
  const validMainValues = mainValues.filter(v => v !== null && !isNaN(v));
  const validOverlayValues = overlayValues.filter(
    (v): v is number => v !== null && !isNaN(v)
  );

  if (validMainValues.length === 0 || validOverlayValues.length === 0) {
    return false;
  }

  const [mainP5, mainP95] = getP5P95Range(validMainValues);
  const [overlayP5, overlayP95] = getP5P95Range(validOverlayValues);

  const mainRange = mainP95 - mainP5;
  const overlayRange = overlayP95 - overlayP5;

  if (mainRange === 0 || overlayRange === 0) {
    // レンジが0の場合は中央値で比較
    const mainMedian = validMainValues[Math.floor(validMainValues.length / 2)];
    const overlayMedian = validOverlayValues[Math.floor(validOverlayValues.length / 2)];

    if (mainMedian === 0 || overlayMedian === 0) {
      return true;
    }

    const ratio = Math.max(mainMedian, overlayMedian) / Math.min(mainMedian, overlayMedian);
    return ratio > 3;
  }

  const ratio = Math.max(mainRange, overlayRange) / Math.min(mainRange, overlayRange);
  return ratio > 3;
}

/**
 * 値の配列からnullを除いた有効な値を抽出
 */
export function extractValidValues(values: (number | null)[]): number[] {
  return values.filter((v): v is number => v !== null && !isNaN(v));
}

/**
 * 頻度認識マージ: 最も細かい頻度のデータを基準にマージ
 *
 * @param mainData メイン指標データ
 * @param mainFrequency メイン指標の頻度
 * @param overlays 比較データの配列（キー、データ、頻度のペア）
 * @returns マージ済みデータと使用された基準頻度
 */
export function mergeWithFrequencyAwareness(
  mainData: DataPoint[],
  mainFrequency: IndicatorFrequency,
  overlays: { key: string; data: DataPoint[]; frequency: IndicatorFrequency }[]
): { mergedData: MergedDataPoint[]; baseFrequency: IndicatorFrequency } {
  // 頻度の優先順位
  const FREQ_PRIORITY: Record<IndicatorFrequency, number> = {
    daily: 1,
    weekly: 2,
    monthly: 3,
    quarterly: 4,
    irregular: 3,
  };

  // 最も細かい頻度を特定
  const allFrequencies = [mainFrequency, ...overlays.map(o => o.frequency)];
  let finestFreq = mainFrequency;
  let finestPriority = FREQ_PRIORITY[mainFrequency];

  for (const freq of allFrequencies) {
    if (FREQ_PRIORITY[freq] < finestPriority) {
      finestFreq = freq;
      finestPriority = FREQ_PRIORITY[freq];
    }
  }

  // 最も細かい頻度のデータを基準として使用
  let baseDates: string[];
  let baseDataMap: Map<string, number>;

  if (finestFreq === mainFrequency) {
    // メイン指標が最も細かい場合は従来通り
    const sortedMain = [...mainData].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    );
    baseDates = sortedMain.map(d => d.date);
    baseDataMap = new Map(sortedMain.map(d => [d.date, d.value]));
  } else {
    // オーバーレイの中で最も細かいデータを基準にする
    const finestOverlay = overlays.find(o => o.frequency === finestFreq);
    if (!finestOverlay || finestOverlay.data.length === 0) {
      // フォールバック: メインデータを使用
      const sortedMain = [...mainData].sort(
        (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
      );
      baseDates = sortedMain.map(d => d.date);
      baseDataMap = new Map(sortedMain.map(d => [d.date, d.value]));
    } else {
      // 最も細かいオーバーレイを基準にする
      const sortedFinest = [...finestOverlay.data].sort(
        (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
      );

      // メインデータの期間に絞る
      const mainSorted = [...mainData].sort(
        (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
      );
      const mainStartDate = mainSorted.length > 0 ? mainSorted[0].date : '';
      const mainEndDate = mainSorted.length > 0 ? mainSorted[mainSorted.length - 1].date : '';

      // 期間フィルタリング
      const filteredFinest = sortedFinest.filter(d => d.date >= mainStartDate && d.date <= mainEndDate);

      baseDates = filteredFinest.map(d => d.date);
      baseDataMap = new Map(filteredFinest.map(d => [d.date, d.value]));
    }
  }

  if (baseDates.length === 0) {
    return { mergedData: [], baseFrequency: finestFreq };
  }

  // メインデータをAs-of Joinでマップ
  const sortedMain = [...mainData].sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
  );
  const mainValues = finestFreq === mainFrequency
    ? baseDates.map(d => baseDataMap.get(d) ?? null)
    : asOfJoin(baseDates, sortedMain);

  // 各オーバーレイをマージ
  const overlayValues: Record<string, (number | null)[]> = {};

  for (const overlay of overlays) {
    if (overlay.frequency === finestFreq && overlays.find(o => o.frequency === finestFreq)?.key === overlay.key) {
      // このオーバーレイが基準の場合、そのまま使用
      overlayValues[overlay.key] = baseDates.map(d => baseDataMap.get(d) ?? null);
    } else {
      // As-of Joinでマップ
      const sortedOverlay = [...overlay.data].sort(
        (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
      );
      overlayValues[overlay.key] = asOfJoin(baseDates, sortedOverlay);
    }
  }

  // 結果を構築
  const mergedData = baseDates.map((date, idx) => {
    const merged: MergedDataPoint = {
      date,
      value: mainValues[idx],
    };

    for (const [key, values] of Object.entries(overlayValues)) {
      merged[key] = values[idx];
    }

    return merged;
  });

  return { mergedData, baseFrequency: finestFreq };
}
