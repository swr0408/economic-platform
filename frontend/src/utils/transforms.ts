/**
 * データ変換ユーティリティ
 */

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
