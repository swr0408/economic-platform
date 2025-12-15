import { Card, Typography } from 'antd'
import LoadingSpinner from './LoadingSpinner'

const { Title } = Typography

interface LoadingChartProps {
  title: string
  titleLevel?: 1 | 2 | 3 | 4 | 5
  message?: string
  height?: number
  showMessage?: boolean
}

export default function LoadingChart({
  title,
  titleLevel = 4,
  message = 'データを読み込み中...',
  height = 400,
  showMessage = true,
}: LoadingChartProps) {
  return (
    <Card>
      <Title level={titleLevel} style={{ marginBottom: 8, textAlign: 'center' }}>
        {title}
      </Title>
      <div style={{ height: height }}>
        <LoadingSpinner message={message} showMessage={showMessage} padding={40} />
      </div>
    </Card>
  )
}
