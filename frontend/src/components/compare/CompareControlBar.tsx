/**
 * 比較ページのコントロールバー
 * 指標追加、期間選択、オプション設定
 */

import { Segmented, Switch, Space, Typography, Tooltip } from 'antd';
import { CameraOutlined, CheckOutlined } from '@ant-design/icons';
import { ComparePopover } from '../charts/ComparePopover';
import type { OverlayIndicator } from '../../constants/overlayConfig';
import type { RangeType, CompareOptions } from '../../hooks/useCompareState';

const { Text } = Typography;

// テーマカラー
const DARK_THEME = {
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textTertiary: '#64748b',
  borderLight: '#475569',
  accent: '#10b981',
};

interface CompareControlBarProps {
  selectedIndicatorIds: string[];
  maxSelections: number;
  onSelectIndicator: (indicator: OverlayIndicator) => void;
  range: RangeType;
  onRangeChange: (range: RangeType) => void;
  options: CompareOptions;
  onOptionsChange: (options: CompareOptions) => void;
  canAddMore: boolean;
  onCapture?: () => void;
  copying?: boolean;
}

export default function CompareControlBar({
  selectedIndicatorIds,
  maxSelections,
  onSelectIndicator,
  range,
  onRangeChange,
  options,
  onOptionsChange,
  canAddMore,
  onCapture,
  copying = false,
}: CompareControlBarProps) {
  return (
    <div
      style={{
        padding: '12px 24px',
        borderBottom: `1px solid ${DARK_THEME.borderLight}`,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        backgroundColor: DARK_THEME.bgSecondary,
        flexWrap: 'wrap',
        gap: 12,
      }}
    >
      {/* 左側: 指標追加 */}
      <Space size={16}>
        <ComparePopover
          selectedIndicatorIds={selectedIndicatorIds}
          mainIndicatorId=""
          onSelect={onSelectIndicator}
          maxSelections={maxSelections}
          buttonText="指標を追加"
          disabled={!canAddMore}
        />
        <Text style={{ color: DARK_THEME.textTertiary, fontSize: 11 }}>
          {selectedIndicatorIds.length} / {maxSelections} 選択中
        </Text>
      </Space>

      {/* 右側: 期間選択 + オプション */}
      <Space size={24}>
        {/* 期間選択 */}
        <Segmented
          value={range}
          onChange={(value) => onRangeChange(value as RangeType)}
          options={[
            { label: '1Y', value: '1Y' },
            { label: '3Y', value: '3Y' },
            { label: '5Y', value: '5Y' },
            { label: '10Y', value: '10Y' },
            { label: 'Max', value: 'Max' },
          ]}
          size="small"
          style={{
            backgroundColor: DARK_THEME.bgTertiary,
          }}
        />

        {/* Index100 切り替え */}
        <Space size={8}>
          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>
            Index100
          </Text>
          <Switch
            checked={options.index100}
            onChange={(checked) => onOptionsChange({ ...options, index100: checked })}
            size="small"
            style={{
              backgroundColor: options.index100 ? DARK_THEME.accent : DARK_THEME.bgTertiary,
            }}
          />
        </Space>

        {/* キャプチャボタン（master限定） */}
        {onCapture && (
          <Tooltip title={copying ? 'コピー中...' : '画像をコピー'}>
            <span
              onClick={onCapture}
              style={{
                fontSize: 16,
                color: copying ? DARK_THEME.accent : DARK_THEME.textSecondary,
                cursor: copying ? 'wait' : 'pointer',
                transition: 'color 0.2s',
                display: 'inline-flex',
                alignItems: 'center',
              }}
              onMouseEnter={(e) => { if (!copying) (e.currentTarget as HTMLElement).style.color = DARK_THEME.accent }}
              onMouseLeave={(e) => { if (!copying) (e.currentTarget as HTMLElement).style.color = DARK_THEME.textSecondary }}
            >
              {copying ? <CheckOutlined /> : <CameraOutlined />}
            </span>
          </Tooltip>
        )}
      </Space>
    </div>
  );
}
