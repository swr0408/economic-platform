/**
 * 比較ページ専用チャートコンポーネント
 * 複数指標を重ねて表示
 */

import { useMemo } from 'react';
import { Spin, Empty } from 'antd';
import { LineChartOutlined } from '@ant-design/icons';
import ZoomableChart from '../common/ZoomableChart';
import { type OverlayIndicator, getOverlayColor } from '../../constants/overlayConfig';
import { shiftDataByMonths, getDateTimestamp, parseDate, type MergedDataPoint } from '../../utils/dataAlignment';
import type { IndicatorFrequency } from '../../constants/overlayConfig';
import { transformToIndex100 } from '../../utils/transforms';
import { filterDataByRange, type RangeType } from '../../hooks/useCompareState';
import { formatQuarterLabel } from '../../utils/dateFormatters';

// テーマカラー
const DARK_THEME = {
  bgSecondary: '#1e293b',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textTertiary: '#64748b',
  accent: '#10b981',
};

interface CompareChartProps {
  indicators: OverlayIndicator[];
  dataMap: Record<string, { date: string; value: number | null }[]>;
  isLoading: boolean;
  range: RangeType;
  index100: boolean;
  timeShifts: Record<string, number>;
}

export default function CompareChart({
  indicators,
  dataMap,
  isLoading,
  range,
  index100,
  timeShifts,
}: CompareChartProps) {
  // データマージ
  const { mergedData, useQuarterKey, additionalLines, rightYAxes } = useMemo(() => {
    if (indicators.length === 0 || Object.keys(dataMap).length === 0) {
      return {
        mergedData: [] as MergedDataPoint[],
        useQuarterKey: false,
        additionalLines: [],
        rightYAxes: undefined,
      };
    }

    // 頻度の優先順位（大きいほど粗い）
    const FREQ_RANK: Record<IndicatorFrequency, number> = {
      daily: 1, weekly: 2, monthly: 3, quarterly: 4, yearly: 5, irregular: 3,
    };

    // 各指標のデータをタイムシフト適用済みで準備（ソート済み）
    // 全日付をYYYY-MM-DD形式に正規化（YYYY-Q# → YYYY-MM-DD 変換含む）
    const normalizeDateStr = (dateStr: string): string => {
      const d = parseDate(dateStr);
      const yyyy = d.getFullYear();
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      const dd = String(d.getDate()).padStart(2, '0');
      return `${yyyy}-${mm}-${dd}`;
    };
    const shiftedSorted: Record<string, { date: string; value: number | null }[]> = {};
    for (const indicator of indicators) {
      const shift = timeShifts[indicator.id] || 0;
      const raw = dataMap[indicator.id] || [];
      const shifted = shift !== 0 ? shiftDataByMonths(raw, shift) : raw;
      // 四半期形式(YYYY-Q#)等を常にYYYY-MM-DD形式に正規化
      const normalized = shifted.map(pt => ({
        ...pt,
        date: normalizeDateStr(pt.date),
      }));
      shiftedSorted[indicator.id] = normalized.sort(
        (a, b) => getDateTimestamp(a.date) - getDateTimestamp(b.date)
      );
    }

    // 最も細かい頻度を特定（ベースタイムラインの解像度）
    let finestRank = Infinity;
    for (const indicator of indicators) {
      const rank = FREQ_RANK[indicator.frequency];
      if (rank < finestRank) finestRank = rank;
    }

    // ベースタイムライン構築: 最も細かい頻度に合わせた日付union
    // 月次の場合は月キー(YYYY-MM)でunion、日次/週次はそのまま
    const useMonthKey = finestRank === 3; // monthly/irregular のみ
    // finestRank >= 4 (全指標が四半期以上) の場合のみ四半期キー
    const useQuarterKey = finestRank >= 4;

    // タイムライン構築:
    // - 解像度は finest 頻度に合わせる（日次/週次データの動きを保持）
    // - 日付範囲は全指標をカバー（シフト含む）
    // - finest指標の範囲外に粗い指標のデータがある場合、月次補間で拡張
    let unionDates: string[];

    if (useQuarterKey) {
      const quarterDateMap = new Map<string, string>();
      for (const indicator of indicators) {
        for (const pt of shiftedSorted[indicator.id]) {
          const d = parseDate(pt.date);
          const q = Math.floor(d.getMonth() / 3) + 1;
          const qk = `${d.getFullYear()}-Q${q}`;
          if (!quarterDateMap.has(qk) || pt.date > quarterDateMap.get(qk)!) {
            quarterDateMap.set(qk, pt.date);
          }
        }
      }
      unionDates = [...quarterDateMap.values()].sort();
    } else if (useMonthKey) {
      // 全指標の最小・最大日付を求め、連続した月次タイムラインを生成
      let minDate = '';
      let maxDate = '';
      for (const indicator of indicators) {
        for (const pt of shiftedSorted[indicator.id]) {
          if (!minDate || pt.date < minDate) minDate = pt.date;
          if (!maxDate || pt.date > maxDate) maxDate = pt.date;
        }
      }
      if (minDate && maxDate) {
        const d = parseDate(minDate);
        d.setDate(1);
        const end = parseDate(maxDate);
        const dates: string[] = [];
        while (d <= end) {
          const yyyy = d.getFullYear();
          const mm = String(d.getMonth() + 1).padStart(2, '0');
          dates.push(`${yyyy}-${mm}-01`);
          d.setMonth(d.getMonth() + 1);
        }
        unionDates = dates;
      } else {
        unionDates = [];
      }
    } else {
      // 日次/週次: まずfinest指標の日付でベースを構築
      const dateSet = new Set<string>();
      const finestIndicators = indicators.filter(i => FREQ_RANK[i.frequency] <= finestRank);
      const coarserIndicators = indicators.filter(i => FREQ_RANK[i.frequency] > finestRank);

      for (const indicator of finestIndicators) {
        for (const pt of shiftedSorted[indicator.id]) {
          dateSet.add(pt.date);
        }
      }
      // finest指標がない場合は全指標を使う
      if (dateSet.size === 0) {
        for (const indicator of indicators) {
          for (const pt of shiftedSorted[indicator.id]) {
            dateSet.add(pt.date);
          }
        }
      }

      // finest指標の日付範囲を求める
      const finestDates = [...dateSet].sort();
      const finestMax = finestDates.length > 0 ? finestDates[finestDates.length - 1] : '';
      const finestMin = finestDates.length > 0 ? finestDates[0] : '';

      // 粗い指標がfinest範囲外にデータを持つ場合、月次で補間日付を生成
      let allMax = finestMax;
      let allMin = finestMin;
      for (const indicator of coarserIndicators) {
        const sorted = shiftedSorted[indicator.id];
        if (sorted.length > 0) {
          const last = sorted[sorted.length - 1].date;
          const first = sorted[0].date;
          if (last > allMax) allMax = last;
          if (first < allMin) allMin = first;
        }
      }

      // 左側の拡張（finestMin より前）
      if (allMin < finestMin) {
        const d = parseDate(allMin);
        const end = parseDate(finestMin);
        d.setDate(1); // 月初に揃える
        while (d < end) {
          const yyyy = d.getFullYear();
          const mm = String(d.getMonth() + 1).padStart(2, '0');
          dateSet.add(`${yyyy}-${mm}-01`);
          d.setMonth(d.getMonth() + 1);
        }
      }

      // 右側の拡張（finestMax より後）
      // 粗い指標の最終データを水平延長表示するため、allMaxの3ヶ月先まで補間
      if (allMax > finestMax) {
        const d = parseDate(finestMax);
        const end = parseDate(allMax);
        end.setMonth(end.getMonth() + 3); // 最終データの3ヶ月先まで拡張
        d.setDate(1);
        d.setMonth(d.getMonth() + 1); // finestMaxの翌月から開始
        while (d <= end) {
          const yyyy = d.getFullYear();
          const mm = String(d.getMonth() + 1).padStart(2, '0');
          dateSet.add(`${yyyy}-${mm}-01`);
          d.setMonth(d.getMonth() + 1);
        }
        // 粗い指標の実データ日付も追加（正確なポイントを含める）
        for (const indicator of coarserIndicators) {
          for (const pt of shiftedSorted[indicator.id]) {
            if (pt.date > finestMax) {
              dateSet.add(pt.date);
            }
          }
        }
      }

      unionDates = [...dateSet].sort();
    }

    if (unionDates.length === 0) {
      return {
        mergedData: [] as MergedDataPoint[],
        additionalLines: [],
        rightYAxes: undefined,
      };
    }

    // 各指標の値をunionDatesにマッピング
    const indicatorValues: Record<string, (number | null)[]> = {};
    for (const indicator of indicators) {
      const sorted = shiftedSorted[indicator.id];
      const freqRank = FREQ_RANK[indicator.frequency];
      const shift = timeShifts[indicator.id] || 0;
      // シフトなし指標: 実データの最終日付を超えたら前方充填しない
      const lastDataDate = sorted.length > 0 ? sorted[sorted.length - 1].date : '';

      if (freqRank <= finestRank) {
        // 同じ細かさ or それ以上に細かい → 厳密マッチ
        if (useQuarterKey) {
          const byQuarter = new Map<string, number | null>();
          for (const pt of sorted) {
            const d = parseDate(pt.date);
            const q = Math.floor(d.getMonth() / 3) + 1;
            byQuarter.set(`${d.getFullYear()}-Q${q}`, pt.value);
          }
          indicatorValues[indicator.id] = unionDates.map(date => {
            const d = parseDate(date);
            const q = Math.floor(d.getMonth() / 3) + 1;
            return byQuarter.get(`${d.getFullYear()}-Q${q}`) ?? null;
          });
        } else if (useMonthKey) {
          const byMonth = new Map<string, number | null>();
          for (const pt of sorted) {
            byMonth.set(pt.date.slice(0, 7), pt.value);
          }
          indicatorValues[indicator.id] = unionDates.map(date => {
            return byMonth.get(date.slice(0, 7)) ?? null;
          });
        } else {
          const byDate = new Map<string, number | null>();
          for (const pt of sorted) byDate.set(pt.date, pt.value);
          indicatorValues[indicator.id] = unionDates.map(date => byDate.get(date) ?? null);
        }
      } else {
        // より粗い頻度 → as-of join（ポインタ法）でベース日付にマッピング（前方充填）
        const values: (number | null)[] = [];
        let idx = 0;
        for (const baseDate of unionDates) {
          // シフトなし指標は実データの最終日付を超えたらnull（水平延長しない）
          if (shift === 0 && lastDataDate && baseDate > lastDataDate) {
            values.push(null);
            continue;
          }
          while (idx < sorted.length && sorted[idx].date <= baseDate) {
            idx++;
          }
          values.push(idx > 0 ? sorted[idx - 1].value : null);
        }
        indicatorValues[indicator.id] = values;
      }
    }

    // MergedDataPoint配列を構築
    const renamedData: MergedDataPoint[] = unionDates.map((date, idx) => {
      const point: MergedDataPoint = { date, value: null };
      for (const indicator of indicators) {
        point[indicator.id] = indicatorValues[indicator.id][idx];
      }
      point.value = indicatorValues[indicators[0].id][idx];
      return point;
    });

    // additionalLines設定（最初の指標を含む全て）
    const lines = indicators.map((indicator, index) => {
      const shift = timeShifts[indicator.id] || 0;
      const shiftLabel = shift === 0 ? '' : (shift > 0 ? ` +${shift}M` : ` ${shift}M`);
      return {
        dataKey: indicator.id,
        color: getOverlayColor(index),
        name: `${indicator.name}${shiftLabel}`,
        strokeWidth: 2,
        yAxisId: index === 0 ? 'left' : `right-${index}`,
        strokeDasharray: index > 0 ? '5 5' : undefined,
      };
    });

    // 右Y軸設定（2番目以降）
    const axes = indicators.slice(1).map((_, index) => ({
      id: `right-${index + 1}`,
      domain: ['auto', 'auto'] as [string, string],
      color: getOverlayColor(index + 1),
      tickFormatter: (v: number) => {
        if (Math.abs(v) >= 1000) return v.toLocaleString();
        if (Math.abs(v) >= 1) return v.toFixed(1);
        return v.toFixed(2);
      },
    }));

    return {
      mergedData: renamedData,
      useQuarterKey,
      additionalLines: lines,
      rightYAxes: axes.length > 0 ? axes : undefined,
    };
  }, [indicators, dataMap, timeShifts]);

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    return filterDataByRange(mergedData, range);
  }, [mergedData, range]);

  // Index100変換
  const transformedData = useMemo(() => {
    if (!index100 || filteredData.length === 0) {
      return filteredData;
    }

    // 全指標をIndex100変換
    const indicatorIds = indicators.map(i => i.id);
    return transformToIndex100(filteredData, indicatorIds);
  }, [filteredData, index100, indicators]);

  // ローディング中
  if (isLoading) {
    return (
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: DARK_THEME.bgSecondary,
          minHeight: 400,
        }}
      >
        <Spin size="large" />
      </div>
    );
  }

  // データなし
  if (indicators.length === 0) {
    return (
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: DARK_THEME.bgSecondary,
          minHeight: 400,
        }}
      >
        <Empty
          image={<LineChartOutlined style={{ fontSize: 64, color: DARK_THEME.textTertiary }} />}
          description={
            <span style={{ color: DARK_THEME.textSecondary }}>
              指標を追加してチャートを表示
            </span>
          }
        />
      </div>
    );
  }

  // データ取得失敗（isLoadingがfalseでデータが空）
  if (transformedData.length === 0) {
    return (
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: DARK_THEME.bgSecondary,
          minHeight: 400,
        }}
      >
        <Empty
          description={
            <span style={{ color: DARK_THEME.textSecondary }}>
              データの読み込みに失敗しました
            </span>
          }
        />
      </div>
    );
  }

  return (
    <div
      style={{
        flex: 1,
        padding: '16px 24px 16px',
        backgroundColor: DARK_THEME.bgSecondary,
      }}
    >
      <ZoomableChart
        data={transformedData}
        dataKey={indicators[0]?.id || 'value'}
        height={Math.max(500, window.innerHeight - 200)}
        color={getOverlayColor(0)}
        name={indicators[0]?.name || ''}
        domain={['auto', 'auto']}
        xAxisTickFormatter={useQuarterKey ? formatQuarterLabel : undefined}
        tooltipLabelFormatter={(dateStr) => {
          const d = parseDate(dateStr);
          if (isNaN(d.getTime())) return dateStr;
          if (useQuarterKey) {
            const q = Math.floor(d.getMonth() / 3) + 1;
            return `${d.getFullYear()}-Q${q}`;
          }
          return `${d.getFullYear()}/${(d.getMonth() + 1).toString().padStart(2, '0')}/${d.getDate().toString().padStart(2, '0')}`;
        }}
        tickFormatter={(v) => {
          if (index100) return v.toFixed(0);
          if (Math.abs(v) >= 1000) return v.toLocaleString();
          if (Math.abs(v) >= 1) return v.toFixed(1);
          return v.toFixed(2);
        }}
        tooltipFormatter={(v) => {
          if (index100) return v.toFixed(1);
          if (Math.abs(v) >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
          if (Math.abs(v) >= 1) return v.toFixed(2);
          return v.toFixed(4);
        }}
        showZeroLine={false}
        hideLegend={false}
        hideMainLine={false}
        additionalLines={additionalLines.slice(1)}
        rightYAxes={rightYAxes}
        enableDynamicTicks={true}
        connectNulls={true}
      />
    </div>
  );
}
