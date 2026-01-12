import { Button, Space } from 'antd';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';

interface DataTablePaginationProps {
  currentCount: number;
  totalCount: number;
  initialCount?: number;
  incrementCount?: number;
  onShowMore: () => void;
  onReset: () => void;
  showMoreText?: string;
  resetText?: string;
  size?: 'small' | 'middle' | 'large';
}

export default function DataTablePagination({
  currentCount,
  totalCount,
  initialCount = 5,
  incrementCount = 10,
  onShowMore,
  onReset,
  showMoreText = `さらに${incrementCount}件表示`,
  resetText = 'リセット',
  size = 'small'
}: DataTablePaginationProps) {
  const hasMore = currentCount < totalCount;
  const showReset = currentCount > initialCount;

  if (!hasMore && !showReset) {
    return null;
  }

  return (
    <div style={{ textAlign: 'center', marginTop: 8 }}>
      <Space size={8}>
        {hasMore && (
          <Button
            type="dashed"
            icon={<PlusOutlined />}
            onClick={onShowMore}
            size={size}
          >
            {showMoreText}
          </Button>
        )}
        {showReset && (
          <Button
            type="default"
            icon={<ReloadOutlined />}
            onClick={onReset}
            size={size}
          >
            {resetText}
          </Button>
        )}
      </Space>
    </div>
  );
}
