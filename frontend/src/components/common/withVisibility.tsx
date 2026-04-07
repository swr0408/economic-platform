/**
 * withVisibility - visibility に応じて子コンポーネントをガードする HOC
 *
 * 用途:
 * - スクリーンショット系チャート 15 種を 1 行で「special 限定」にする
 *
 * 効果:
 * - 権限が無い時は元のコンポーネントを完全に呼び出さない (= fetch も走らない)
 * - 権限が有る時はそのまま元のコンポーネントを描画
 *
 * 注意:
 * - これは UI 表示制御のみ。実際のアクセス制御は backend
 *   ReadVisibilityGuardMiddleware が担当する
 *
 * 使い方:
 *   const Wrapped = withVisibility(MyChart, 'special')
 *   export default Wrapped
 */
import type { ComponentType } from 'react'
import { useCanView } from '../../hooks/useCanView'
import type { IndicatorVisibility } from '../../constants/countryData'

export function withVisibility<P extends object>(
  Component: ComponentType<P>,
  visibility: IndicatorVisibility,
): ComponentType<P> {
  function VisibilityGuarded(props: P) {
    const canView = useCanView(visibility)
    if (!canView) return null
    return <Component {...props} />
  }
  VisibilityGuarded.displayName = `withVisibility(${Component.displayName ?? Component.name ?? 'Component'})`
  return VisibilityGuarded
}
