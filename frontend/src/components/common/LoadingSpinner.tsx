import { Spin } from 'antd'
import { LoadingOutlined } from '@ant-design/icons'

interface LoadingSpinnerProps {
  size?: 'small' | 'default' | 'large'
  message?: string
  showMessage?: boolean
  iconSize?: number
  padding?: number | string
}

/**
 * 統一されたローディングスピナーコンポーネント
 */
export default function LoadingSpinner({
  size = 'large',
  message = 'データを読み込み中...',
  showMessage = true,
  iconSize = 48,
  padding = 60,
}: LoadingSpinnerProps) {
  const spinIcon = <LoadingOutlined style={{ fontSize: iconSize, color: '#1890ff' }} spin />

  return (
    <div
      style={{
        textAlign: 'center',
        padding: padding,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '16px',
      }}
    >
      <Spin indicator={spinIcon} size={size} />
      {showMessage && message && (
        <div style={{ color: '#8c8c8c', fontSize: '14px' }}>{message}</div>
      )}
    </div>
  )
}
