/**
 * 比較ページ専用チャートコンポーネント
 * 複数指標を重ねて表示
 */

import { useMemo } from 'react';
import { Spin, Empty } from 'antd';
import { LineChartOutlined } from '@ant-design/icons';
import ZoomableChart from '../common/ZoomableChart';
import { type OverlayIndicator, getOverlayColor } from '../../constants/overlayConfig';
import { mergeWithFrequencyAwareness, type MergedDataPoint } from '../../utils/dataAlignment';
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
}

export default function CompareChart({
  indicators,
  dataMap,
  isLoading,
  range,
  index100,
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

    // 最初の指標をベースにする
    const firstIndicator = indicators[0];
    const firstData = dataMap[firstIndicator.id] || [];

    if (firstData.length === 0) {
      return {
        mergedData: [] as MergedDataPoint[],
        baseFrequency: firstIndicator.frequency,
        additionalLines: [],
        rightYAxes: undefined,
      };
    }

    // 残りの指標をオーバーレイとしてマージ
    const overlayInputs = indicators.slice(1).map(indicator => ({
      key: indicator.id,
      data: dataMap[indicator.id] || [],
      frequency: indicator.frequency,
    }));

    const { mergedData: merged } = mergeWithFrequencyAwareness(
      firstData,
      firstIndicator.frequency,
      overlayInputs
    );

    // 最初の指標のデータを 'value' から指標IDに変更
    const renamedData = merged.map(item => {
      const newItem: MergedDataPoint = { ...item };
      if ('value' in newItem && typeof newItem.value === 'number') {
        (newItem as Record<string, unknown>)[firstIndicator.id] = newItem.value;
      }
      return newItem;
    });

    // additionalLines設定（最初の指標を含む全て）
    const lines = indicators.map((indicator, index) => ({
      dataKey: indicator.id,
      color: getOverlayColor(index),
      name: indicator.name,
      strokeWidth: 2,
      yAxisId: index === 0 ? 'left' : `right-${index}`,
      strokeDasharray: index > 0 ? '5 5' : undefined,
    }));

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
  }, [indicators, dataMap]);

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

  // データがまだ取得できていない
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
              データを読み込み中...
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
