/**
 * オーバーレイチップコンポーネント
 * 頻度ラベル付きの比較指標タグ
 */

import { Tag } from 'antd';
import { CloseOutlined } from '@ant-design/icons';

export interface OverlayChipProps {
  /** 表示ラベル（例: "NY連銀 月次 右軸"） */
  label: string;
  /** チップの色 */
  color: string;
  /** 削除ハンドラ */
  onRemove: () => void;
  /** クリックハンドラ（設定変更用） */
  onClick?: () => void;
}

/**
 * 色を少し暗くする（ダークモード用背景色生成）
 */
function getDarkBackground(color: string): string {
  // 色からRGBA背景を生成（透明度を下げてダークモードに合わせる）
  return `${color}20`; // 約12%の透明度
}

/**
 * 個別のオーバーレイチップ
 */
export function OverlayChip({
  label,
  color,
  onRemove,
  onClick,
}: OverlayChipProps) {
  return (
    <Tag
      closable
      closeIcon={<CloseOutlined style={{ fontSize: 10, color: color }} />}
      onClose={(e) => {
        e.preventDefault();
        onRemove();
      }}
      onClick={onClick}
      style={{
        cursor: onClick ? 'pointer' : 'default',
        marginRight: 8,
        marginBottom: 4,
        padding: '2px 8px',
        fontSize: 12,
        borderRadius: 4,
        backgroundColor: getDarkBackground(color),
        border: `1px solid ${color}`,
        color: color,
      }}
    >
      {label}
    </Tag>
  );
}

export interface OverlayChipListProps {
  /** チップ情報の配列 */
  chips: {
    id: string;
    label: string;
    color: string;
    onRemove: () => void;
  }[];
  /** 全てクリアボタンを表示するか */
  showClearAll?: boolean;
  /** 全てクリアハンドラ */
  onClearAll?: () => void;
}

/**
 * オーバーレイチップのリスト表示
 */
export function OverlayChipList({
  chips,
  showClearAll = true,
  onClearAll,
}: OverlayChipListProps) {
  if (chips.length === 0) {
    return null;
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: 4,
        marginBottom: 8,
      }}
    >
      <span
        style={{
          fontSize: 12,
          color: '#94a3b8',
          marginRight: 8,
        }}
      >
        比較中:
      </span>

      {chips.map((chip) => (
        <OverlayChip
          key={chip.id}
          label={chip.label}
          color={chip.color}
          onRemove={chip.onRemove}
        />
      ))}

      {showClearAll && onClearAll && chips.length > 1 && (
        <Tag
          style={{
            cursor: 'pointer',
            backgroundColor: '#334155',
            border: '1px solid #475569',
            color: '#94a3b8',
            fontSize: 11,
            padding: '1px 6px',
          }}
          onClick={onClearAll}
        >
          全て解除
        </Tag>
      )}
    </div>
  );
}

export default OverlayChip;
