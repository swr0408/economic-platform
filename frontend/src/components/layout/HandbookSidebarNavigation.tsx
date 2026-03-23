import { useMemo, useState, useEffect } from 'react'
import { Menu, Input } from 'antd'
import type { MenuProps } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  HANDBOOK_ENTRIES,
  HANDBOOK_COUNTRY_LABELS,
  HANDBOOK_CATEGORY_LABELS,
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

  const countryOrder = ['usa', 'japan', 'eurozone', 'uk', 'china', 'australia', 'newzealand', 'canada', 'switzerland', 'global', 'market']

  return countryOrder
    .filter((code) => byCountry.has(code))
    .map((countryCode) => {
      const categoryMap = byCountry.get(countryCode)!
      const categoryOrder = ['policy', 'economy', 'consumer', 'employment', 'inflation', 'housing', 'equities', 'forex', 'commodities', 'energy', 'cot', 'flow', 'rebalance', 'anomaly', 'options']

      return {
        key: `handbook-${countryCode}`,
        label: HANDBOOK_COUNTRY_LABELS[countryCode] || countryCode,
        children: categoryOrder
          .filter((cat) => categoryMap.has(cat))
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
      <div style={{ flex: 1, overflow: 'auto' }}>
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
