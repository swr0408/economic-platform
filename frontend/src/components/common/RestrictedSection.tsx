/**
 * RestrictedSection - visibility に応じて子要素を表示 / 非表示するラッパ
 *
 * 用途:
 * - スクリーンショット系チャートなど special / master 限定の section を
 *   一般ユーザに対して完全に非表示にする (hash アンカー用 div ごと描画しない)
 *
 * 注意:
 * - これは UI 表示制御だけ。実際のアクセス制御は backend
 *   ReadVisibilityGuardMiddleware が担当する
 *
 * 使い方:
 *   <RestrictedSection visibility="special">
 *     <div id="ecb-rate-cuts">
 *       <ECBRateCutsExpectationChart />
 *     </div>
 *   </RestrictedSection>
 */
import type { ReactNode } from 'react'
import { useCanView } from '../../hooks/useCanView'
import type { IndicatorVisibility } from '../../constants/countryData'

interface RestrictedSectionProps {
  visibility: IndicatorVisibility
  children: ReactNode
  /**
   * 権限が無い時に表示するフォールバック (省略時は null)
   */
  fallback?: ReactNode
}

export default function RestrictedSection({
  visibility,
  children,
  fallback = null,
}: RestrictedSectionProps) {
  const canView = useCanView(visibility)
  if (!canView) return <>{fallback}</>
  return <>{children}</>
}
