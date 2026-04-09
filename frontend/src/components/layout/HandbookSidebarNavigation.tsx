import { useMemo, useState, useEffect, useRef } from 'react'
import { Menu, Input } from 'antd'
import type { MenuProps } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  HANDBOOK_ENTRIES,
  HANDBOOK_COUNTRY_LABELS,
  HANDBOOK_CATEGORY_LABELS,
  HANDBOOK_COUNTRY_ORDER,
  HANDBOOK_CATEGORY_ORDER,
} from '../../content/handbookRegistry'

type MenuItem = Required<MenuProps>['items'][number]

const colors = {
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  accent: '#10b981',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  border: '#334155',
}

// 国→カテゴリ→指標の3階層構造を組み立てる
function buildMenuTree(searchQuery: string): MenuItem[] {
  const filteredEntries = searchQuery
    ? HANDBOOK_ENTRIES.filter((e) => {
        const q = searchQuery.toLowerCase()
        return (
          e.title.toLowerCase().includes(q) ||
          e.summary.toLowerCase().includes(q) ||
          (e.tags || []).some((t) => t.toLowerCase().includes(q))
        )
      })
    : HANDBOOK_ENTRIES

  // 国ごとにグループ化
  const byCountry = new Map<string, Map<string, typeof filteredEntries>>()
  for (const entry of filteredEntries) {
    if (!byCountry.has(entry.country)) {
      byCountry.set(entry.country, new Map())
    }
    const categoryMap = byCountry.get(entry.country)!
    if (!categoryMap.has(entry.category)) {
      categoryMap.set(entry.category, [])
    }
    categoryMap.get(entry.category)!.push(entry)
  }

  // 国順序になく登録された国があれば末尾に追加
  const orderedCountries = [
    ...HANDBOOK_COUNTRY_ORDER.filter((c) => byCountry.has(c)),
    ...[...byCountry.keys()].filter((c) => !HANDBOOK_COUNTRY_ORDER.includes(c)),
  ]

  return orderedCountries
    .map((countryCode) => {
      const categoryMap = byCountry.get(countryCode)!
      // カテゴリ順序になく登録されたカテゴリがあれば末尾に追加
      const orderedCategories = [
        ...HANDBOOK_CATEGORY_ORDER.filter((c) => categoryMap.has(c)),
        ...[...categoryMap.keys()].filter((c) => !HANDBOOK_CATEGORY_ORDER.includes(c)),
      ]

      return {
        key: `handbook-${countryCode}`,
        label: HANDBOOK_COUNTRY_LABELS[countryCode] || countryCode,
        children: orderedCategories
          .map((categoryCode) => {
            const entries = categoryMap.get(categoryCode)!
            return {
              key: `handbook-${countryCode}-${categoryCode}`,
              label: HANDBOOK_CATEGORY_LABELS[categoryCode] || categoryCode,
              children: entries.map((entry) => ({
                key: `/handbook#${entry.indicatorId}`,
                label: entry.title,
              })),
            }
          }),
      }
    })
}

export default function HandbookSidebarNavigation() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchQuery, setSearchQuery] = useState('')
  const [openKeys, setOpenKeys] = useState<string[]>([])
  const menuScrollRef = useRef<HTMLDivElement>(null)

  const menuItems = useMemo(() => buildMenuTree(searchQuery), [searchQuery])

  // 検索時はすべて展開
  useEffect(() => {
    if (searchQuery) {
      const allKeys: string[] = []
      const collectKeys = (items: MenuItem[]) => {
        for (const item of items) {
          if (item && 'key' in item && item.key) {
            allKeys.push(item.key as string)
          }
          if (item && 'children' in item && item.children) {
            collectKeys(item.children as MenuItem[])
          }
        }
      }
      collectKeys(menuItems)
      setOpenKeys(allKeys)
    }
  }, [searchQuery, menuItems])

  const selectedKeys = useMemo(() => {
    if (location.hash) {
      return [`/handbook${location.hash}`]
    }
    return []
  }, [location.hash])

  // ハッシュに対応する国・カテゴリの SubMenu を自動展開
  useEffect(() => {
    if (searchQuery) return // 検索中は別ロジックで全展開
    if (!location.hash) return
    const indicatorId = location.hash.slice(1)
    const entry = HANDBOOK_ENTRIES.find((e) => e.indicatorId === indicatorId)
    if (!entry) return
    const countryKey = `handbook-${entry.country}`
    const categoryKey = `handbook-${entry.country}-${entry.category}`
    setOpenKeys((prev) => {
      const merged = new Set(prev)
      merged.add(countryKey)
      merged.add(categoryKey)
      return Array.from(merged)
    })
  }, [location.hash, searchQuery])

  // ページ遷移時に選択中のメニュー項目をサイドバー内で表示位置までスクロール
  // 既に視界内にある場合は何もしない（block: 'nearest'）ので手動スクロールを邪魔しない
  useEffect(() => {
    if (selectedKeys.length === 0) return
    const wrapper = menuScrollRef.current
    if (!wrapper) return

    const timer = setTimeout(() => {
      const targetKey = selectedKeys[0]
      const safeKey = targetKey.replace(/\\/g, '\\\\').replace(/"/g, '\\"')
      const el = wrapper.querySelector<HTMLElement>(
        `[data-menu-id$="${safeKey}"]`,
      )
      if (el) {
        el.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
      }
    }, 250)

    return () => clearTimeout(timer)
  }, [selectedKeys, openKeys])

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    if (key.includes('#')) {
      const [path, hash] = key.split('#')
      navigate(`${path}#${hash}`)
      // スクロール
      setTimeout(() => {
        const el = document.getElementById(hash)
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }
      }, 100)
    } else {
      navigate(key)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* 検索バー */}
      <div style={{ padding: '12px 12px 8px' }}>
        <Input
          placeholder="指標を検索..."
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

      {/* メニュー */}
      <div ref={menuScrollRef} style={{ flex: 1, overflow: 'auto' }}>
        <Menu
          mode="inline"
          theme="dark"
          items={menuItems}
          selectedKeys={selectedKeys}
          openKeys={openKeys}
          onOpenChange={setOpenKeys}
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
