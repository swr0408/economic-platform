// パフォーマンス最適化用のユーティリティ関数

/**
 * スロットリング関数 - 指定した間隔でのみ関数を実行
 */
export function throttle<T extends (...args: unknown[]) => unknown>(
  func: T,
  delay: number
): (...args: Parameters<T>) => void {
  let lastCall = 0
  let timeoutId: ReturnType<typeof setTimeout> | null = null

  return (...args: Parameters<T>) => {
    const now = Date.now()

    if (now - lastCall >= delay) {
      lastCall = now
      func(...args)
    } else {
      if (timeoutId) {
        clearTimeout(timeoutId)
      }
      timeoutId = setTimeout(() => {
        lastCall = Date.now()
        func(...args)
      }, delay - (now - lastCall))
    }
  }
}

/**
 * デバウンス関数 - 最後の呼び出しから指定時間後に実行
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
  func: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout> | null = null

  return (...args: Parameters<T>) => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    timeoutId = setTimeout(() => func(...args), delay)
  }
}

/**
 * より効果的なドラッグ用スロットリング（RequestAnimationFrame + 間隔制御）
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function dragThrottle<T extends (...args: any[]) => any>(
  func: T
): (...args: Parameters<T>) => void {
  let lastCall = 0
  let rafId: number | null = null
  const interval = 8 // より高頻度（120FPS相当）で応答性向上

  return (...args: Parameters<T>) => {
    const now = Date.now()

    // 前回実行から十分時間が経過していない場合はスキップ
    if (now - lastCall < interval) {
      return
    }

    // 既存のRAFをキャンセル
    if (rafId) {
      cancelAnimationFrame(rafId)
    }

    rafId = requestAnimationFrame(() => {
      lastCall = Date.now()
      func(...args)
      rafId = null
    })
  }
}
