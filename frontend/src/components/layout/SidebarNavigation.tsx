import React, { useMemo, useState, useEffect, useRef } from 'react'
import { Menu } from 'antd'
import type { MenuProps } from 'antd'
import { GlobalOutlined } from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import { COUNTRIES_DATA } from '../../constants/countryData'
import { useCanViewFn } from '../../hooks/useCanView'

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
  const canView = useCanViewFn()
  const menuWrapperRef = useRef<HTMLDivElement>(null)

  // 3階層メニュー: 国 > カテゴリ > 経済指標
  // 小見出し（経済指標）はカテゴリページ + ハッシュで遷移
  // visibility に応じて閲覧できない指標 / カテゴリ / 国は丸ごと非表示にする
  const menuItems: MenuItem[] = useMemo(() => {
    return COUNTRIES_DATA.flatMap((country) => {
      // グローバル: 単一カテゴリ + 指標フラット
      if (country.code === 'global') {
        const visibleIndicators = country.categories[0].indicators.filter((i) =>
          canView(i.visibility),
        )
        if (visibleIndicators.length === 0) return []
        return [{
          key: `/country/${country.code}`,
          icon: country.isoCode === 'globe' ? (
            <GlobalOutlined style={{ fontSize: '16px', color: '#10b981' }} />
          ) : (
            <span
              className={`fi fi-${country.isoCode}`}
              style={{ fontSize: '16px', borderRadius: '2px' }}
            />
          ),
          label: (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
              {country.isoCode === 'globe' ? (
                <GlobalOutlined style={{ fontSize: '14px', color: '#10b981' }} />
              ) : (
                <span
                  className={`fi fi-${country.isoCode}`}
                  style={{ fontSize: '14px', borderRadius: '2px' }}
                />
              )}
              {country.name}
            </span>
          ),
          children: visibleIndicators.map((indicator) => ({
            key: `/country/global/economy#${indicator.code}`,
            label: indicator.name,
          })),
        }]
      }

      // 通常国: カテゴリ → 指標
      const visibleCategories = country.categories
        .map((category) => {
          const visibleIndicators = category.indicators.filter((i) =>
            canView(i.visibility),
          )
          if (visibleIndicators.length === 0) return null
          return {
            key: `/country/${country.code}/${category.code}`,
            icon: React.cloneElement(category.icon as React.ReactElement, {
              style: { color: category.color },
            }),
            label: category.name,
            children: visibleIndicators.map((indicator) => ({
              // 小見出しはカテゴリページ + ハッシュ
              key: `/country/${country.code}/${category.code}#${indicator.code}`,
              label: indicator.name,
            })),
          }
        })
        .filter((c): c is NonNullable<typeof c> => c !== null)

      if (visibleCategories.length === 0) return []
      return [{
        key: `/country/${country.code}`,
        icon: country.isoCode === 'globe' ? (
          <GlobalOutlined style={{ fontSize: '16px', color: '#10b981' }} />
        ) : (
          <span
            className={`fi fi-${country.isoCode}`}
            style={{ fontSize: '16px', borderRadius: '2px' }}
          />
        ),
        label: (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
            {country.isoCode === 'globe' ? (
              <GlobalOutlined style={{ fontSize: '14px', color: '#10b981' }} />
            ) : (
              <span
                className={`fi fi-${country.isoCode}`}
                style={{ fontSize: '14px', borderRadius: '2px' }}
              />
            )}
            {country.name}
          </span>
        ),
        children: visibleCategories,
      }]
    })
  }, [canView])

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

  // ページ遷移時に選択中のメニュー項目をサイドバー内で表示位置までスクロール
  // 既に視界内にある場合は何もしない（block: 'nearest'）ので手動スクロールを邪魔しない
  useEffect(() => {
    if (selectedKeys.length === 0) return
    const wrapper = menuWrapperRef.current
    if (!wrapper) return

    // サブメニューの展開アニメーション完了後にスクロール
    const timer = setTimeout(() => {
      const targetKey = selectedKeys[0]
      // antd Menu の data-menu-id は `${uuid}-${eventKey}` の形式
      // CSS 引用符内では `/` や `#` などはエスケープ不要だが、`"` と `\` は不可
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

export default SidebarNavigation
