/**
 * 選択中の指標を表示するチップリスト
 */

import { Tag, Button, Space, Typography } from 'antd';
import { CloseOutlined, ClearOutlined } from '@ant-design/icons';
import { type OverlayIndicator, getFrequencyLabel, getOverlayColor } from '../../constants/overlayConfig';

const { Text } = Typography;

// テーマカラー
const DARK_THEME = {
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textTertiary: '#64748b',
  borderLight: '#475569',
};

interface IndicatorChipProps {
  indicator: OverlayIndicator;
  color: string;
  onRemove: () => void;
}

function IndicatorChip({ indicator, color, onRemove }: IndicatorChipProps) {
  return (
    <Tag
      closable
      closeIcon={<CloseOutlined style={{ fontSize: 10, color: DARK_THEME.textSecondary }} />}
      onClose={(e) => {
        e.preventDefault();
        onRemove();
      }}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '4px 10px',
        margin: 0,
        backgroundColor: DARK_THEME.bgTertiary,
        border: `1px solid ${color}`,
        borderRadius: 16,
        color: DARK_THEME.textPrimary,
        fontSize: 12,
      }}
    >
      <span
        style={{
          display: 'inline-block',
          width: 8,
          height: 8,
          borderRadius: '50%',
          backgroundColor: color,
        }}
      />
      <span style={{ fontWeight: 500 }}>{indicator.name}</span>
      <span style={{ color: DARK_THEME.textTertiary, fontSize: 11 }}>
        {getFrequencyLabel(indicator.frequency)}
      </span>
    </Tag>
  );
}

interface IndicatorChipListProps {
  indicators: OverlayIndicator[];
  onRemove: (indicatorId: string) => void;
  onClearAll: () => void;
}

export default function IndicatorChipList({
  indicators,
  onRemove,
  onClearAll,
}: IndicatorChipListProps) {
  if (indicators.length === 0) {
    return (
      <div
        style={{
          padding: '12px 24px',
          borderBottom: `1px solid ${DARK_THEME.borderLight}`,
          backgroundColor: DARK_THEME.bgSecondary,
        }}
      >
        <Text style={{ color: DARK_THEME.textTertiary, fontSize: 13 }}>
          指標が選択されていません。「指標を追加」ボタンから指標を選択してください。
        </Text>
      </div>
    );
  }

  return (
    <div
      style={{
        padding: '10px 24px',
        borderBottom: `1px solid ${DARK_THEME.borderLight}`,
        backgroundColor: DARK_THEME.bgSecondary,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        flexWrap: 'wrap',
      }}
    >
      <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12, flexShrink: 0 }}>
        比較中:
      </Text>
      <Space size={8} wrap>
        {indicators.map((indicator, index) => (
          <IndicatorChip
            key={indicator.id}
            indicator={indicator}
            color={getOverlayColor(index)}
            onRemove={() => onRemove(indicator.id)}
          />
        ))}
      </Space>
      {indicators.length > 1 && (
        <Button
          type="text"
          size="small"
          icon={<ClearOutlined />}
          onClick={onClearAll}
          style={{
            color: DARK_THEME.textTertiary,
            fontSize: 11,
            marginLeft: 'auto',
          }}
        >
          全て解除
        </Button>
      )}
    </div>
  );
}
