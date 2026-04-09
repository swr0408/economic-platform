import React, { useMemo, useState, useEffect, useRef } from 'react'
import { Menu } from 'antd'
import type { MenuProps } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import { GlobalOutlined } from '@ant-design/icons'
import { EARNINGS_CATEGORIES_DATA, EARNINGS_COUNTRIES } from '../../constants/earningsData'

type MenuItem = Required<MenuProps>['items'][number]

const colors = {
  bgSecondary: '#1e293b',
}

function EarningsSidebarNavigation() {
  const navigate = useNavigate()
  const location = useLocation()
  const [openKeys, setOpenKeys] = useState<string[]>([])
  const menuWrapperRef = useRef<HTMLDivElement>(null)

  const menuItems: MenuItem[] = useMemo(() => {
    return EARNINGS_CATEGORIES_DATA.map((category) => {
      if (category.code === 'calendar') {
        // 決算カレンダー: 全体 + 各国
        return {
          key: `/earnings/calendar`,
          icon: React.cloneElement(category.icon as React.ReactElement, {
            style: { color: category.color },
          }),
          label: category.nameJa,
          children: [
            {
              key: `/earnings/calendar/all`,
              icon: <GlobalOutlined style={{ color: category.color }} />,
              label: '全体',
            },
            ...EARNINGS_COUNTRIES.map((country) => ({
              key: `/earnings/calendar/${country.code}`,
              label: `${country.flag} ${country.nameJa}`,
            })),
          ],
        }
      } else {
        // 決算データ: 各国のみ
        return {
          key: `/earnings/data`,
          icon: React.cloneElement(category.icon as React.ReactElement, {
            style: { color: category.color },
          }),
          label: category.nameJa,
          children: EARNINGS_COUNTRIES.map((country) => ({
            key: `/earnings/data/${country.code}`,
            label: `${country.flag} ${country.nameJa}`,
          })),
        }
      }
    })
  }, [])

  const selectedKeys = useMemo(() => {
    return [location.pathname]
  }, [location.pathname])

  // パスに基づいて開くキーを計算
  useEffect(() => {
    const path = location.pathname
    const parts = path.split('/').filter(Boolean)

    if (parts[0] === 'earnings' && parts.length >= 2) {
      const categoryCode = parts[1]
      setOpenKeys((prev) => {
        const key = `/earnings/${categoryCode}`
        if (prev.includes(key)) return prev
        return [...prev, key]
      })
    }
  }, [location.pathname])

  // ページ遷移時に選択中のメニュー項目をサイドバー内で表示位置までスクロール
  // 既に視界内にある場合は何もしない（block: 'nearest'）ので手動スクロールを邪魔しない
  useEffect(() => {
    if (selectedKeys.length === 0) return
    const wrapper = menuWrapperRef.current
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

  const handleMenuClick: MenuProps['onClick'] = (e) => {
    navigate(e.key)
  }

  const handleOpenChange = (keys: string[]) => {
    setOpenKeys(keys)
  }

  return (
    <div ref={menuWrapperRef} style={{ height: '100%' }}>
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
    </div>
  )
}

export default EarningsSidebarNavigation
