import React, { useMemo, useState, useEffect } from 'react'
import { Menu } from 'antd'
import type { MenuProps } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import { COUNTRIES_DATA } from '../../constants/countryData'

type MenuItem = Required<MenuProps>['items'][number]

// EconAlpha カラーパレット
const colors = {
  bgPrimary: '#0f172a',
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  accent: '#10b981',
  accentHover: '#34d399',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  border: '#334155',
}

function SidebarNavigation() {
  const navigate = useNavigate()
  const location = useLocation()
  const [openKeys, setOpenKeys] = useState<string[]>([])
  const [selectedIndicator, setSelectedIndicator] = useState<string>('')

  // 3階層メニュー: 国 > カテゴリ > 経済指標
  // 小見出し（経済指標）はカテゴリページ + ハッシュで遷移
  const menuItems: MenuItem[] = useMemo(() => {
    return COUNTRIES_DATA.map((country) => ({
      key: `/country/${country.code}`,
      icon: (
        <span
          className={`fi fi-${country.isoCode}`}
          style={{
            fontSize: '16px',
            borderRadius: '2px',
          }}
        />
      ),
      label: (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
          <span
            className={`fi fi-${country.isoCode}`}
            style={{ fontSize: '14px', borderRadius: '2px' }}
          />
          {country.name}
        </span>
      ),
      children: country.categories.map((category) => ({
        key: `/country/${country.code}/${category.code}`,
        icon: React.cloneElement(category.icon as React.ReactElement, {
          style: { color: category.color },
        }),
        label: category.name,
        children: category.indicators.map((indicator) => ({
          // 小見出しはカテゴリページ + ハッシュ
          key: `/country/${country.code}/${category.code}#${indicator.code}`,
          label: indicator.name,
        })),
      })),
    }))
  }, [])

  // 選択キー: 現在のパス + ハッシュ または selectedIndicator
  const selectedKeys = useMemo(() => {
    // ハッシュがある場合はそれを使用
    if (location.hash) {
      return [location.pathname + location.hash]
    }
    // selectedIndicatorがある場合はそれを使用
    if (selectedIndicator && selectedIndicator.startsWith(location.pathname)) {
      return [selectedIndicator]
    }
    // デフォルトはパスのみ
    return [location.pathname]
  }, [location.pathname, location.hash, selectedIndicator])

  // パスが変わったらselectedIndicatorをリセット（ハッシュがない場合）
  useEffect(() => {
    if (!location.hash) {
      setSelectedIndicator('')
    } else {
      setSelectedIndicator(location.pathname + location.hash)
    }
  }, [location.pathname, location.hash])

  // パスに基づいて開くキーを計算
  useEffect(() => {
    const path = location.pathname
    const parts = path.split('/').filter(Boolean)

    if (parts[0] === 'country' && parts.length >= 2) {
      const newOpenKeys: string[] = []

      // 国レベル
      newOpenKeys.push(`/country/${parts[1]}`)

      // カテゴリレベル
      if (parts.length >= 3) {
        newOpenKeys.push(`/country/${parts[1]}/${parts[2]}`)
      }

      setOpenKeys((prev) => {
        const merged = [...new Set([...prev, ...newOpenKeys])]
        return merged
      })
    }
  }, [location.pathname])

  const handleMenuClick: MenuProps['onClick'] = (e) => {
    const key = e.key
    // ハッシュ付きの場合は分解して遷移
    if (key.includes('#')) {
      const [path, hash] = key.split('#')
      // 選択状態を即座に更新
      setSelectedIndicator(key)
      // ページ遷移
      navigate(`${path}#${hash}`)
      // 少し遅延してからスクロール（ページ遷移後にスクロール）
      setTimeout(() => {
        const element = document.getElementById(hash)
        if (element) {
          // ヘッダーの高さ（64px）+ 余白（16px）を考慮してスクロール
          const headerOffset = 80
          const elementPosition = element.getBoundingClientRect().top
          const offsetPosition = elementPosition + window.pageYOffset - headerOffset
          window.scrollTo({
            top: offsetPosition,
            behavior: 'smooth',
          })
        }
      }, 100)
    } else {
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

export default SidebarNavigation
