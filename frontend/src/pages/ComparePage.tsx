/**
 * データ比較ページ
 * 複数の経済指標を自由に選択・比較できる専用ワークスペース
 *
 * URL: /compare
 * URLパラメータ:
 *   - s: 指標ID（複数可）
 *   - range: 期間（1Y, 3Y, 5Y, 10Y, Max）
 *   - index100: Index100変換（true/false）
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { Layout, message } from 'antd';
import html2canvas from 'html2canvas';
import { useCompareState } from '../hooks/useCompareState';
import { useIsMaster } from '../hooks/useIsMaster';
import { useMultipleOverlayData } from '../hooks/useOverlayData';
import CompareControlBar from '../components/compare/CompareControlBar';
import IndicatorChipList from '../components/compare/IndicatorChipList';
import CompareChart from '../components/compare/CompareChart';
import type { OverlayIndicator } from '../constants/overlayConfig';

// テーマカラー
const DARK_THEME = {
  bgPrimary: '#0f172a',
  bgSecondary: '#1e293b',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  borderLight: '#475569',
  accent: '#10b981',
};

export default function ComparePage() {
  const captureRef = useRef<HTMLDivElement>(null);
  const [copying, setCopying] = useState(false);
  const isMaster = useIsMaster();

  const handleCapture = useCallback(async () => {
    if (!isMaster) return;
    if (!captureRef.current || copying) return;
    setCopying(true);
    try {
      const canvas = await html2canvas(captureRef.current, {
        backgroundColor: DARK_THEME.bgSecondary,
        scale: 2,
        useCORS: true,
        logging: false,
      });
      canvas.toBlob(async (blob) => {
        if (!blob) {
          message.error('画像の生成に失敗しました');
          setCopying(false);
          return;
        }
        try {
          await navigator.clipboard.write([
            new ClipboardItem({ 'image/png': blob }),
          ]);
          message.success('クリップボードにコピーしました');
        } catch {
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = 'データ比較.png';
          a.click();
          URL.revokeObjectURL(url);
          message.success('画像をダウンロードしました');
        }
        setCopying(false);
      }, 'image/png');
    } catch {
      message.error('画像の生成に失敗しました');
      setCopying(false);
    }
  }, [copying, isMaster]);

  const {
    selectedIndicatorIds,
    selectedIndicators,
    range,
    options,
    addIndicator,
    removeIndicator,
    setRange,
    setOptions,
    setTimeShift,
    clearAll,
    maxSelections,
    canAddMore,
  } = useCompareState();

  // 複数指標のデータを取得
  const { data: dataMap, isLoading } = useMultipleOverlayData(selectedIndicators);

  // 指標選択時のハンドラ
  const handleSelectIndicator = (indicator: OverlayIndicator) => {
    addIndicator(indicator.id);
  };

  // ページタイトル更新
  useEffect(() => {
    const indicatorNames = selectedIndicators.map(i => i.name).join(' vs ');
    if (indicatorNames) {
      document.title = `${indicatorNames} - データ比較 | EconAlpha`;
    } else {
      document.title = 'データ比較 | EconAlpha';
    }
    return () => {
      document.title = 'EconAlpha';
    };
  }, [selectedIndicators]);

  return (
    <Layout
      style={{
        minHeight: 'calc(100vh - 64px)',
        backgroundColor: DARK_THEME.bgPrimary,
      }}
    >
      {/* コントロールバー */}
      <CompareControlBar
        selectedIndicatorIds={selectedIndicatorIds}
        maxSelections={maxSelections}
        onSelectIndicator={handleSelectIndicator}
        range={range}
        onRangeChange={setRange}
        options={options}
        onOptionsChange={setOptions}
        canAddMore={canAddMore}
        onCapture={isMaster && selectedIndicators.length > 0 ? handleCapture : undefined}
        copying={copying}
      />

      {/* 選択中の指標チップ */}
      <IndicatorChipList
        indicators={selectedIndicators}
        timeShifts={options.timeShifts}
        onRemove={removeIndicator}
        onShiftChange={setTimeShift}
        onClearAll={clearAll}
      />

      {/* チャートエリア（キャプチャ対象） */}
      <div
        ref={captureRef}
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: DARK_THEME.bgSecondary,
        }}
      >
        <CompareChart
          indicators={selectedIndicators}
          dataMap={dataMap || {}}
          isLoading={isLoading}
          range={range}
          index100={options.index100}
          timeShifts={options.timeShifts}
        />
      </div>
    </Layout>
  );
}
