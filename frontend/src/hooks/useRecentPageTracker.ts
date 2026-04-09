/**
 * ルート遷移を検知して、最近見たページの履歴を localStorage に記録する。
 *
 * MainLayout で 1 度だけ呼び出す想定。
 * document.title は全ページ "EconAlpha" 固定で意味のある情報にならないため、
 * routeTitleResolver でパスから日本語タイトルを生成する。
 */
import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { recordPageVisit } from '../utils/recentPages'
import { resolveRouteTitle } from '../utils/routeTitleResolver'

export function useRecentPageTracker(): void {
  const location = useLocation()

  useEffect(() => {
    const title = resolveRouteTitle(location.pathname)
    if (title) {
      recordPageVisit(location.pathname, title)
    }
  }, [location.pathname])
}
