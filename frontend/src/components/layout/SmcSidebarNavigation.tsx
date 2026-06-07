import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Menu, Input } from 'antd'
import type { MenuProps } from 'antd'
import { RightOutlined, SearchOutlined } from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import { SMC_TOC, SMC_SLUG_LIST, type TocNode } from '../../content/guides/smc/toc'

type MenuItem = Required<MenuProps>['items'][number]

const colors = {
  bgTertiary: '#334155',
  accent: '#10b981',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  border: '#334155',
}

// ノード（子孫含む）が検索クエリにマッチするか判定
function matchesQuery(node: TocNode, q: string): boolean {
  if (!q) return true
  if (node.text.toLowerCase().includes(q)) return true
  return node.children?.some((c) => matchesQuery(c, q)) ?? false
}

type BuildContext = {
  onTitleNavigate: (slug: string) => void
  onToggleOpen: (key: string) => void
}

// 矢印アイコン: クリック時のみ開閉、タイトル行の onTitleClick へバブリングしないよう stopPropagation
function ExpandIcon({
  isOpen,
  submenuKey,
  onToggleOpen,
}: {
  isOpen: boolean
  submenuKey: string
  onToggleOpen: (key: string) => void
}) {
  return (
    <span
      onClick={(e) => {
        e.stopPropagation()
        onToggleOpen(submenuKey)
      }}
      style={{
        position: 'absolute',
        right: 16,
        top: '50%',
        transform: 'translateY(-50%)',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 24,
        height: 24,
        cursor: 'pointer',
      }}
    >
      <RightOutlined
        style={{
          fontSize: 10,
          transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)',
          transition: 'transform 0.2s',
        }}
      />
    </span>
  )
}

// 親ノード（祖先のテキストもマッチ判定に使う）
function buildNodeItem(node: TocNode, q: string, ancestorMatched: boolean, ctx: BuildContext): MenuItem {
  const selfMatched = ancestorMatched || node.text.toLowerCase().includes(q)
  const visibleChildren =
    node.children?.filter((c) => !q || selfMatched || matchesQuery(c, q)) ?? []

  if (visibleChildren.length > 0) {
    const submenuKey = `smc-${node.slug}`
    return {
      key: submenuKey,
      label: (
        <span
          onClick={(e) => {
            e.stopPropagation()
            ctx.onTitleNavigate(node.slug)
          }}
          style={{ display: 'block', width: '100%', cursor: 'pointer' }}
        >
          {node.text}
        </span>
      ),
      expandIcon: ({ isOpen }: { isOpen?: boolean }) => (
        <ExpandIcon isOpen={isOpen ?? false} submenuKey={submenuKey} onToggleOpen={ctx.onToggleOpen} />
      ),
      children: visibleChildren.map((c) => buildNodeItem(c, q, selfMatched, ctx)),
    }
  }
  return {
    key: `/smc#${node.slug}`,
    label: node.text,
  }
}

function buildMenuTree(query: string, ctx: BuildContext): MenuItem[] {
  const q = query.trim().toLowerCase()
  return SMC_TOC.filter((h2) => matchesQuery(h2, q)).map((h2) => buildNodeItem(h2, q, false, ctx))
}

// SubMenu になり得る（children を持つ）すべてのノードのキーを集める
function collectExpandableKeys(nodes: TocNode[]): string[] {
  const keys: string[] = []
  for (const n of nodes) {
    if (n.children && n.children.length > 0) {
      keys.push(`smc-${n.slug}`)
      keys.push(...collectExpandableKeys(n.children))
    }
  }
  return keys
}

// 指定 slug の祖先 SubMenu キー一覧（深さに関わらず）を求める
function findAncestorKeys(nodes: TocNode[], targetSlug: string, path: TocNode[] = []): string[] {
  for (const n of nodes) {
    const newPath = [...path, n]
    if (n.slug === targetSlug) {
      return path.filter((p) => p.children && p.children.length > 0).map((p) => `smc-${p.slug}`)
    }
    if (n.children && n.children.length > 0) {
      const found = findAncestorKeys(n.children, targetSlug, newPath)
      if (found.length > 0 || n.children.some((c) => c.slug === targetSlug)) {
        if (n.children.some((c) => c.slug === targetSlug)) {
          return newPath
            .filter((p) => p.children && p.children.length > 0)
            .map((p) => `smc-${p.slug}`)
        }
        return found
      }
    }
  }
  return []
}

export default function SmcSidebarNavigation() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchQuery, setSearchQuery] = useState('')
  const [openKeys, setOpenKeys] = useState<string[]>(() =>
    // 初期状態は H2 SubMenu のみ展開（H3 の SubMenu は閉じる）
    SMC_TOC.filter((h2) => h2.children && h2.children.length > 0).map((h2) => `smc-${h2.slug}`),
  )
  const [activeSlug, setActiveSlug] = useState<string | null>(null)
  const menuScrollRef = useRef<HTMLDivElement>(null)

  const navigateToSlug = useCallback(
    (slug: string) => {
      navigate(`/smc#${slug}`)
      setTimeout(() => {
        document.getElementById(slug)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 80)
    },
    [navigate],
  )

  const toggleOpenKey = useCallback((key: string) => {
    setOpenKeys((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]))
  }, [])

  const menuItems = useMemo(
    () => buildMenuTree(searchQuery, { onTitleNavigate: navigateToSlug, onToggleOpen: toggleOpenKey }),
    [searchQuery, navigateToSlug, toggleOpenKey],
  )

  // 検索時はすべて展開（H3 SubMenu も含む）
  useEffect(() => {
    if (!searchQuery) return
    setOpenKeys(collectExpandableKeys(SMC_TOC))
  }, [searchQuery])

  // スクロール位置で現在のセクションをハイライト
  useEffect(() => {
    if (!location.pathname.startsWith('/smc')) return

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        if (visible.length > 0) {
          const id = visible[0].target.id
          if (id) setActiveSlug(id)
        }
      },
      {
        rootMargin: '-80px 0px -70% 0px',
        threshold: 0,
      },
    )

    const attach = () => {
      for (const slug of SMC_SLUG_LIST) {
        const el = document.getElementById(slug)
        if (el) observer.observe(el)
      }
    }
    const t = setTimeout(attach, 200)

    return () => {
      clearTimeout(t)
      observer.disconnect()
    }
  }, [location.pathname])

  // ハッシュ遷移時、対応する祖先 SubMenu を展開
  useEffect(() => {
    if (!location.hash) return
    const slug = decodeURIComponent(location.hash.replace('#', ''))
    const ancestorKeys = findAncestorKeys(SMC_TOC, slug)
    if (ancestorKeys.length > 0) {
      setOpenKeys((prev) => Array.from(new Set([...prev, ...ancestorKeys])))
    }
    setActiveSlug(slug)
  }, [location.hash])

  const selectedKeys = useMemo(() => {
    if (activeSlug) return [`/smc#${activeSlug}`]
    if (location.hash) return [`/smc${location.hash}`]
    return []
  }, [activeSlug, location.hash])

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    if (key.includes('#')) {
      const [, hash] = key.split('#')
      navigateToSlug(hash)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '12px 12px 8px' }}>
        <Input
          placeholder="SMCを検索..."
          prefix={<SearchOutlined style={{ color: colors.textSecondary }} />}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          allowClear
          size="small"
          style={{
            background: colors.bgTertiary,
            borderColor: colors.border,
            color: colors.textPrimary,
          }}
        />
      </div>

      <div ref={menuScrollRef} style={{ flex: 1, overflow: 'auto' }}>
        <Menu
          mode="inline"
          theme="dark"
          items={menuItems}
          selectedKeys={selectedKeys}
          openKeys={openKeys}
          onOpenChange={() => {
            // 開閉は expandIcon クリックのみで制御するため、antd 内部のトグルは無視
          }}
          onClick={handleMenuClick}
          style={{
            background: 'transparent',
            borderRight: 'none',
            fontSize: '13px',
          }}
        />
      </div>
    </div>
  )
}
