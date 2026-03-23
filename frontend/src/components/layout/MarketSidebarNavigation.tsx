import React, { useMemo, useState, useEffect } from 'react'
import { Menu } from 'antd'
import type { MenuProps } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import { MARKET_CATEGORIES_DATA } from '../../constants/marketData'

type MenuItem = Required<MenuProps>['items'][number]

const colors = {
  bgSecondary: '#1e293b',
}

function MarketSidebarNavigation() {
  const navigate = useNavigate()
  const location = useLocation()
  const [openKeys, setOpenKeys] = useState<string[]>([])
  const [selectedIndicator, setSelectedIndicator] = useState<string>('')

  // 3階層メニュー: カテゴリ > サブカテゴリ > 銘柄
  // キー構造: カテゴリ=/markets/{cat}, サブカテゴリ=/markets/{cat}/{sub}, 銘柄=/markets/{cat}/{sub}#{indicator}
  const menuItems: MenuItem[] = useMemo(() => {
    return MARKET_CATEGORIES_DATA.map((category) => ({
      key: `/markets/${category.code}`,
      icon: React.cloneElement(category.icon as React.ReactElement, {
        style: { color: category.color },
      }),
      label: category.name,
      children:
        category.subCategories.length > 0
          ? category.subCategories.map((sub) => ({
              key: `/markets/${category.code}/${sub.code}`,
              label: sub.name,
              children:
                sub.indicators.length > 0
                  ? sub.indicators.map((indicator) => ({
                      key: `/markets/${category.code}/${sub.code}#${indicator.code}`,
                      label: indicator.name,
                    }))
                  : undefined,
            }))
          : undefined,
    }))
  }, [])

  const selectedKeys = useMemo(() => {
    if (location.hash) {
      return [location.pathname + location.hash]
    }
    if (selectedIndicator && selectedIndicator.startsWith(location.pathname)) {
      return [selectedIndicator]
    }
    return [location.pathname]
  }, [location.pathname, location.hash, selectedIndicator])

  useEffect(() => {
    if (!location.hash) {
      setSelectedIndicator('')
    } else {
      setSelectedIndicator(location.pathname + location.hash)
    }
  }, [location.pathname, location.hash])

  // パスに基づいて開くキーを計算（カテゴリ + サブカテゴリ両方を展開）
  useEffect(() => {
    const parts = location.pathname.split('/').filter(Boolean)
    // parts = ['markets', 'equities', 'us-equities']

    if (parts[0] === 'markets' && parts.length >= 2) {
      const categoryCode = parts[1]
      const newOpenKeys: string[] = [`/markets/${categoryCode}`]

      if (parts.length >= 3) {
        const subCategoryCode = parts[2]
        newOpenKeys.push(`/markets/${categoryCode}/${subCategoryCode}`)
      }

      setOpenKeys((prev) => {
        const merged = [...new Set([...prev, ...newOpenKeys])]
        return merged
      })
    }
  }, [location.pathname])

  const handleMenuClick: MenuProps['onClick'] = (e) => {
    const key = e.key
    if (key.includes('#')) {
      // 銘柄クリック: サブカテゴリページ + ハッシュスクロール
      const [path, hash] = key.split('#')
      setSelectedIndicator(key)
      navigate(`${path}#${hash}`)
      setTimeout(() => {
        const element = document.getElementById(hash)
        if (element) {
          const headerOffset = 80
          const elementPosition = element.getBoundingClientRect().top
          const offsetPosition = elementPosition + window.pageYOffset - headerOffset
          window.scrollTo({ top: offsetPosition, behavior: 'smooth' })
        }
      }, 100)
    } else {
      // サブカテゴリクリック: パスで遷移
      setSelectedIndicator('')
      navigate(key)
    }
  }

  const handleOpenChange = (keys: string[]) => {
    setOpenKeys(keys)
  }

  return (
    <Menu
      mode="inline"
      theme="dark"
      selectedKeys={selectedKeys}
      openKeys={openKeys}
      onOpenChange={handleOpenChange}
      items={menuItems}
      onClick={handleMenuClick}
      style={{
        height: '100%',
        borderRight: 0,
        background: colors.bgSecondary,
        fontSize: '13px',
      }}
    />
  )
}

export default MarketSidebarNavigation
