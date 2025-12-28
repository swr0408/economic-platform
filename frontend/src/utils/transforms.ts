/**
 * データ変換ユーティリティ
 * Index=100変換、Z-score変換（Phase2）
 */

/**
 * Index=100 変換
 *
 * 基準値を100として、各値を基準値に対する比率で変換。
 * 基準日は配列の最初の有効な値。
 *
 * @param values 元の値の配列
 * @param baseIndex 基準とするインデックス（デフォルト: 最初の有効な値）
 * @returns Index=100に変換された値の配列
 */
export function toIndex100(
  values: (number | null)[],
  baseIndex?: number
): (number | null)[] {
  // 最初の有効な値を見つける
  let baseValue: number | null = null;
  let foundIndex = baseIndex;

  if (foundIndex === undefined) {
    for (let i = 0; i < values.length; i++) {
      if (values[i] !== null && !isNaN(values[i] as number)) {
        baseValue = values[i];
        foundIndex = i;
        break;
      }
    }
  } else {
    baseValue = values[foundIndex] ?? null;
  }

  if (baseValue === null || baseValue === 0) {
    // 基準値が見つからない or 0 の場合はそのまま返す
    return values;
  }

  return values.map(v => {
    if (v === null || isNaN(v)) {
      return null;
    }
    return (v / baseValue!) * 100;
  });
}

/**
 * 複数系列をIndex=100に変換
 *
 * @param data マージ済みデータ
 * @param keys 変換するキーの配列
 * @returns 変換済みデータ
 */
export function transformToIndex100<T extends Record<string, unknown>>(
  data: T[],
  keys: string[]
): T[] {
  if (data.length === 0) {
    return [];
  }

  // 各キーの基準値を取得
  const baseValues: Record<string, number | null> = {};

  for (const key of keys) {
    for (const item of data) {
      const value = item[key];
      if (typeof value === 'number' && !isNaN(value)) {
        baseValues[key] = value;
        break;
      }
    }
  }

  // 変換を適用
  return data.map(item => {
    const transformed = { ...item };

    for (const key of keys) {
      const value = item[key];
      const baseValue = baseValues[key];

      if (
        typeof value === 'number' &&
        !isNaN(value) &&
        baseValue !== null &&
        baseValue !== undefined &&
        baseValue !== 0
      ) {
        (transformed as Record<string, unknown>)[key] = (value / baseValue) * 100;
      }
    }

    return transformed;
  });
}

/**
 * Z-score変換（Phase 2用）
 *
 * (値 - 平均) / 標準偏差
 *
 * @param values 元の値の配列
 * @returns Z-scoreに変換された値の配列
 */
export function toZScore(values: (number | null)[]): (number | null)[] {
  const validValues = values.filter((v): v is number => v !== null && !isNaN(v));

  if (validValues.length === 0) {
    return values;
  }

  // 平均を計算
  const mean = validValues.reduce((sum, v) => sum + v, 0) / validValues.length;

  // 標準偏差を計算
  const squaredDiffs = validValues.map(v => Math.pow(v - mean, 2));
  const variance = squaredDiffs.reduce((sum, v) => sum + v, 0) / validValues.length;
  const stdDev = Math.sqrt(variance);

  if (stdDev === 0) {
    // 全て同じ値の場合は0を返す
    return values.map(v => (v === null ? null : 0));
  }

  return values.map(v => {
    if (v === null || isNaN(v)) {
      return null;
    }
    return (v - mean) / stdDev;
  });
}

/**
 * 複数系列をZ-scoreに変換（Phase 2用）
 */
export function transformToZScore<T extends Record<string, unknown>>(
  data: T[],
  keys: string[]
): T[] {
  if (data.length === 0) {
    return [];
  }

  // 各キーの統計を計算
  const stats: Record<string, { mean: number; stdDev: number }> = {};

  for (const key of keys) {
    const values: number[] = [];

    for (const item of data) {
      const value = item[key];
      if (typeof value === 'number' && !isNaN(value)) {
        values.push(value);
      }
    }

    if (values.length > 0) {
      const mean = values.reduce((sum, v) => sum + v, 0) / values.length;
      const squaredDiffs = values.map(v => Math.pow(v - mean, 2));
      const variance = squaredDiffs.reduce((sum, v) => sum + v, 0) / values.length;
      const stdDev = Math.sqrt(variance);

      stats[key] = { mean, stdDev };
    }
  }

  // 変換を適用
  return data.map(item => {
    const transformed = { ...item };

    for (const key of keys) {
      const value = item[key];
      const stat = stats[key];

      if (
        typeof value === 'number' &&
        !isNaN(value) &&
        stat &&
        stat.stdDev !== 0
      ) {
        (transformed as Record<string, unknown>)[key] = (value - stat.mean) / stat.stdDev;
      }
    }

    return transformed;
  });
}

/**
 * 変化率を計算（前期比）
 *
 * @param values 元の値の配列
 * @returns 変化率の配列（%）
 */
export function toChangeRate(values: (number | null)[]): (number | null)[] {
  return values.map((v, i) => {
    if (i === 0 || v === null || values[i - 1] === null) {
      return null;
    }

    const prevValue = values[i - 1] as number;
    if (prevValue === 0) {
      return null;
    }

    return ((v - prevValue) / prevValue) * 100;
  });
}
