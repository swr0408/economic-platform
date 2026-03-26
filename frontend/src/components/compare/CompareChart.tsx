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
  const { mergedData, additionalLines, rightYAxes } = useMemo(() => {
    if (indicators.length === 0 || Object.keys(dataMap).length === 0) {
      return {
        mergedData: [] as MergedDataPoint[],
        baseFrequency: 'monthly' as const,
        additionalLines: [],
        rightYAxes: undefined,
      };
    }

    // 頻度の優先順位（大きいほど粗い）
    const FREQ_RANK: Record<IndicatorFrequency, number> = {
      daily: 1, weekly: 2, monthly: 3, quarterly: 4, yearly: 5, irregular: 3,
    };

    // 各指標のデータをタイムシフト適用済みで準備（ソート済み）
    const shiftedSorted: Record<string, { date: string; value: number | null }[]> = {};
    for (const indicator of indicators) {
      const shift = timeShifts[indicator.id] || 0;
      const raw = dataMap[indicator.id] || [];
      const shifted = shift !== 0 ? shiftDataByMonths(raw, shift) : raw;
      shiftedSorted[indicator.id] = [...shifted].sort(
        (a, b) => getDateTimestamp(a.date) - getDateTimestamp(b.date)
      );
    }

    // 最も粗い頻度を特定（ベースタイムラインの解像度）
    let coarsestRank = 0;
    for (const indicator of indicators) {
      const rank = FREQ_RANK[indicator.frequency];
      if (rank > coarsestRank) coarsestRank = rank;
    }

    // ベースタイムライン構築: 最も粗い頻度に合わせた日付union
    // 月次以上の粗さの場合は月キー(YYYY-MM)でunion
    // 四半期の場合は四半期キー(YYYY-QN)でunion
    const useMonthKey = coarsestRank >= 3; // monthly, quarterly, yearly
    const useQuarterKey = coarsestRank >= 4; // quarterly, yearly

    let unionDates: string[];

    if (useQuarterKey) {
      // 四半期キーでunion
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
      // 月キーでunion
      const monthDateMap = new Map<string, string>();
      for (const indicator of indicators) {
        for (const pt of shiftedSorted[indicator.id]) {
          const mk = pt.date.slice(0, 7);
          if (!monthDateMap.has(mk) || pt.date > monthDateMap.get(mk)!) {
            monthDateMap.set(mk, pt.date);
          }
        }
      }
      unionDates = [...monthDateMap.values()].sort();
    } else {
      // 日次/週次: 日付そのままunion
      const dateSet = new Set<string>();
      for (const indicator of indicators) {
        for (const pt of shiftedSorted[indicator.id]) {
          dateSet.add(pt.date);
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

      if (freqRank >= coarsestRank) {
        // 同じ粗さ or それ以上 → 月/四半期キーの厳密マッチ
        if (useQuarterKey) {
          // 四半期マッチ
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
          // 月マッチ
          const byMonth = new Map<string, number | null>();
          for (const pt of sorted) {
            byMonth.set(pt.date.slice(0, 7), pt.value);
          }
          indicatorValues[indicator.id] = unionDates.map(date => {
            return byMonth.get(date.slice(0, 7)) ?? null;
          });
        } else {
          // 日付exact match
          const byDate = new Map<string, number | null>();
          for (const pt of sorted) byDate.set(pt.date, pt.value);
          indicatorValues[indicator.id] = unionDates.map(date => byDate.get(date) ?? null);
        }
      } else {
        // より細かい頻度 → as-of join（ポインタ法）でベース日付にマッピング
        const values: (number | null)[] = [];
        let idx = 0;
        for (const baseDate of unionDates) {
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
        padding: '16px 24px',
        backgroundColor: DARK_THEME.bgSecondary,
      }}
    >
      <ZoomableChart
        data={transformedData}
        dataKey={indicators[0]?.id || 'value'}
        height={Math.max(500, window.innerHeight - 280)}
        color={getOverlayColor(0)}
        name={indicators[0]?.name || ''}
        domain={['auto', 'auto']}
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
