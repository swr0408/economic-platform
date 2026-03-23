import { useRef, useState, useEffect, Component, type ReactNode } from 'react'
import { Card, Skeleton, Alert } from 'antd'

// Stagger queue: prevents many charts from rendering in the same frame
let staggerQueue: (() => void)[] = []
let staggerTimer: ReturnType<typeof setTimeout> | null = null
const STAGGER_DELAY = 80 // ms between each chart render

function enqueueRender(callback: () => void) {
  staggerQueue.push(callback)
  if (!staggerTimer) {
    drainQueue()
  }
}

function drainQueue() {
  if (staggerQueue.length === 0) {
    staggerTimer = null
    return
  }
  const next = staggerQueue.shift()
  next?.()
  staggerTimer = setTimeout(drainQueue, STAGGER_DELAY)
}

// Error Boundary to isolate chart crashes
interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

class ChartErrorBoundary extends Component<
  { children: ReactNode; chartId?: string },
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return (
        <Card
          style={{
            background: '#1e293b',
            border: '1px solid #475569',
            borderRadius: 12,
            minHeight: 200,
          }}
        >
          <Alert
            type="warning"
            showIcon
            message="チャートの描画に失敗しました"
            description={this.state.error?.message}
            style={{ background: '#1e293b', border: '1px solid #475569' }}
          />
        </Card>
      )
    }
    return this.props.children
  }
}

interface LazyChartProps {
  children: ReactNode
  id?: string
  minHeight?: number
  rootMargin?: string
}

export default function LazyChart({
  children,
  id,
  minHeight = 450,
  rootMargin = '200px 0px',
}: LazyChartProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [isVisible, setIsVisible] = useState(false)
  const [shouldRender, setShouldRender] = useState(false)

  useEffect(() => {
    if (id && window.location.hash === `#${id}`) {
      setIsVisible(true)
      setShouldRender(true)
      return
    }

    const element = ref.current
    if (!element) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true)
          observer.disconnect()
        }
      },
      { rootMargin },
    )

    observer.observe(element)
    return () => observer.disconnect()
  }, [id, rootMargin])

  // Stagger actual rendering to avoid multiple heavy charts mounting at once
  useEffect(() => {
    if (!isVisible || shouldRender) return
    enqueueRender(() => setShouldRender(true))
  }, [isVisible, shouldRender])

  return (
    <div id={id} ref={ref}>
      {shouldRender ? (
        <ChartErrorBoundary chartId={id}>
          {children}
        </ChartErrorBoundary>
      ) : (
        <Card
          style={{
            background: '#1e293b',
            border: '1px solid #475569',
            borderRadius: 12,
            minHeight,
          }}
        >
          <Skeleton active paragraph={{ rows: 8 }} />
        </Card>
      )}
    </div>
  )
}
