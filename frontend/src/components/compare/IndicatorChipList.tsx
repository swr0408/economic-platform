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
  shift: number;
  onRemove: () => void;
  onShiftChange: (months: number) => void;
}

const shiftBtnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 18,
  height: 18,
  borderRadius: '50%',
  border: 'none',
  backgroundColor: 'rgba(255,255,255,0.1)',
  color: '#94a3b8',
  fontSize: 12,
  cursor: 'pointer',
  padding: 0,
  lineHeight: 1,
};

function IndicatorChip({ indicator, color, shift, onRemove, onShiftChange }: IndicatorChipProps) {
  const shiftLabel = shift === 0 ? '' : (shift > 0 ? `+${shift}M` : `${shift}M`);

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
      {/* タイムシフトコントロール */}
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 2, marginLeft: 2 }}>
        <button
          style={{
            ...shiftBtnStyle,
            opacity: shift <= -24 ? 0.3 : 1,
          }}
          onClick={(e) => { e.stopPropagation(); onShiftChange(shift - 1); }}
          disabled={shift <= -24}
          title="遅行（-1ヶ月）"
        >
          ◀
        </button>
        {shift !== 0 && (
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: shift > 0 ? '#4caf50' : '#ef5350',
              minWidth: 28,
              textAlign: 'center',
              cursor: 'pointer',
            }}
            onClick={(e) => { e.stopPropagation(); onShiftChange(0); }}
            title="シフトをリセット"
          >
            {shiftLabel}
          </span>
        )}
        <button
          style={{
            ...shiftBtnStyle,
            opacity: shift >= 24 ? 0.3 : 1,
          }}
          onClick={(e) => { e.stopPropagation(); onShiftChange(shift + 1); }}
          disabled={shift >= 24}
          title="先行（+1ヶ月）"
        >
          ▶
        </button>
      </span>
    </Tag>
  );
}

interface IndicatorChipListProps {
  indicators: OverlayIndicator[];
  timeShifts: Record<string, number>;
  onRemove: (indicatorId: string) => void;
  onShiftChange: (indicatorId: string, months: number) => void;
  onClearAll: () => void;
}

export default function IndicatorChipList({
  indicators,
  timeShifts,
  onRemove,
  onShiftChange,
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
            shift={timeShifts[indicator.id] || 0}
            onRemove={() => onRemove(indicator.id)}
            onShiftChange={(months) => onShiftChange(indicator.id, months)}
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
