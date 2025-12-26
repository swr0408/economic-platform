import React, { useMemo, useState, useEffect } from 'react'
import { Menu } from 'antd'
import type { MenuProps } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  BankOutlined,
  DollarOutlined,
  TeamOutlined,
  RiseOutlined,
  HomeOutlined,
  ShoppingOutlined,
} from '@ant-design/icons'

type MenuItem = Required<MenuProps>['items'][number]

type Indicator = {
  code: string
  name: string
}

type Category = {
  code: string
  name: string
  icon: React.ReactNode
  color: string
  indicators: Indicator[]
}

type Country = {
  code: string
  name: string
  flag: string
  categories: Category[]
}

// 各国のカテゴリと経済指標の定義
const COUNTRIES_DATA: Country[] = [
  {
    code: 'usa',
    name: 'アメリカ',
    flag: '🇺🇸',
    categories: [
      {
        code: 'policy',
        name: '金融政策',
        icon: <BankOutlined />,
        color: '#1890ff',
        indicators: [
          { code: 'policy-rate', name: '政策金利' },
          { code: 'fed-watch', name: 'Fed Watch' },
          { code: 'term-premium', name: 'タームプレミアム' },
          { code: 'dot-plot', name: 'Dot Plot' },
          { code: 'fomc-projections', name: 'FOMC経済見通し' },
        ],
      },
      {
        code: 'economy',
        name: '経済',
        icon: <DollarOutlined />,
        color: '#52c41a',
        indicators: [
          { code: 'gdp-growth', name: 'GDP成長率' },
          { code: 'gdp-components-growth', name: 'GDP項目別成長率' },
          { code: 'gdp-contributions', name: 'GDP寄与度' },
          { code: 'potential-gdp', name: '潜在成長率' },
          { code: 'bank-lending', name: '銀行貸し出し態度' },
          { code: 'fci', name: 'FCI-G（金融情勢指数）' },
          { code: 'nfci', name: '金融環境指数（NFCI）' },
          { code: 'gdpnow', name: 'GDPNow' },
          { code: 'ism-manufacturing', name: 'ISM製造業景況指数' },
          { code: 'ism-components', name: 'ISM製造業サブインデックス' },
          { code: 'order-inventory-balance', name: 'ISM受注在庫バランス' },
          { code: 'ism-non-manufacturing', name: 'ISM非製造業景況指数' },
          { code: 'ism-non-manufacturing-components', name: 'ISM非製造業サブインデックス' },
          { code: 'empire-state', name: 'NY連銀製造業景気指数' },
          { code: 'philadelphia-fed', name: 'フィラデルフィア連銀製造業景気指数' },
          { code: 'nfib', name: 'NFIB中小企業楽観指数' },
          { code: 'nfib-capex', name: 'NFIB設備投資計画' },
          { code: 'industrial-production', name: '鉱工業生産' },
          { code: 'capacity-utilization', name: '設備稼働率' },
          { code: 'durable-goods', name: '耐久財受注' },
          { code: 'us-flights', name: '航空機便数' },
          { code: 'tsa-checkpoint', name: '航空機旅客者数' },
          { code: 'opentable', name: 'レストラン予約件数' },
        ],
      },
      {
        code: 'consumer',
        name: '消費',
        icon: <ShoppingOutlined />,
        color: '#13c2c2',
        indicators: [
          { code: 'retail-sales', name: '小売売上高' },
          { code: 'carts', name: 'シカゴ連銀小売指数（CARTS）' },
          { code: 'affinity-spend', name: 'クレジット / デビットカードカード支出' },
          { code: 'visa-spending', name: 'Visa支出モメンタム指数' },
          { code: 'total-vehicle-sales', name: '自動車販売台数' },
          { code: 'redbook', name: 'Redbook小売売上高指数' },
          { code: 'consumer-credit', name: 'クレジットカードローン残高' },
          { code: 'delinquency-rate', name: 'クレジットカードローン延滞率' },
          { code: 'cb-consumer-confidence', name: 'CB消費者信頼感指数' },
          { code: 'michigan-consumer-sentiment', name: 'ミシガン消費者信頼感指数' },
          { code: 'personal-saving-rate', name: '家計貯蓄率' },
          { code: 'personal-income', name: '個人所得' },
          { code: 'disposable-income', name: '可処分所得' },
          { code: 'pce', name: '個人消費支出（PCE）' },
        ],
      },
      {
        code: 'employment',
        name: '雇用',
        icon: <TeamOutlined />,
        color: '#faad14',
        indicators: [
          { code: 'unemployment', name: '失業率' },
          { code: 'unemployment-by-reason', name: '失業率内訳' },
          { code: 'job-openings-per-unemployed', name: '求人倍率' },
          { code: 'cb-jobs-labor', name: 'CB雇用機会業況判断' },
          { code: 'nonfarm-payrolls', name: '非農業部門雇用者数' },
          { code: 'fullpart-time', name: 'フルタイム / パートタイム雇用者数' },
          { code: 'multiple-jobs-parttime', name: '複数の仕事を持つ人 / 経済的理由によるパートタイム' },
          { code: 'adp-employment', name: 'ADP雇用者数' },
          { code: 'ner-pulse', name: 'ADP雇用者数（NER Pulse）' },
          { code: 'jolts-indeed', name: 'JOLTS求人 / Indeed求人件数' },
          { code: 'jolts-hires-layoffs', name: 'JOLTS採用数 / 解雇数' },
          { code: 'initial-claims', name: '新規失業保険申請件数' },
          { code: 'continued-claims', name: '継続失業保険申請件数' },
          { code: 'challenger-job-cuts', name: 'Challenger人員削減数' },
        ],
      },
      {
        code: 'inflation',
        name: '物価',
        icon: <RiseOutlined />,
        color: '#ff4d4f',
        indicators: [
          { code: 'cpi', name: 'CPI' },
          { code: 'pce', name: 'PCE' },
          { code: 'ppi', name: 'PPI' },
        ],
      },
      {
        code: 'housing',
        name: '住宅',
        icon: <HomeOutlined />,
        color: '#722ed1',
        indicators: [
          { code: 'housing-starts', name: '住宅着工件数' },
          { code: 'existing-home-sales', name: '中古住宅販売' },
          { code: 'new-home-sales', name: '新築住宅販売' },
        ],
      },
    ],
  },
  {
    code: 'japan',
    name: '日本',
    flag: '🇯🇵',
    categories: [
      {
        code: 'policy',
        name: '金融政策',
        icon: <BankOutlined />,
        color: '#1890ff',
        indicators: [
          { code: 'policy-rate', name: '政策金利' },
          { code: 'boj-statement', name: '日銀声明' },
          { code: 'tankan', name: '短観' },
        ],
      },
      {
        code: 'economy',
        name: '経済',
        icon: <DollarOutlined />,
        color: '#52c41a',
        indicators: [
          { code: 'gdp', name: 'GDP' },
          { code: 'pmi', name: 'PMI' },
          { code: 'trade-balance', name: '貿易収支' },
        ],
      },
      {
        code: 'consumer',
        name: '消費',
        icon: <ShoppingOutlined />,
        color: '#13c2c2',
        indicators: [
          { code: 'retail-sales', name: '小売売上高' },
          { code: 'consumer-confidence', name: '消費者信頼感' },
        ],
      },
      {
        code: 'employment',
        name: '雇用',
        icon: <TeamOutlined />,
        color: '#faad14',
        indicators: [
          { code: 'unemployment', name: '失業率' },
          { code: 'job-offers', name: '有効求人倍率' },
        ],
      },
      {
        code: 'inflation',
        name: '物価',
        icon: <RiseOutlined />,
        color: '#ff4d4f',
        indicators: [
          { code: 'cpi', name: 'CPI' },
          { code: 'cgpi', name: 'CGPI' },
        ],
      },
      {
        code: 'housing',
        name: '住宅',
        icon: <HomeOutlined />,
        color: '#722ed1',
        indicators: [
          { code: 'housing-starts', name: '住宅着工件数' },
        ],
      },
    ],
  },
  {
    code: 'eurozone',
    name: 'ユーロ圏',
    flag: '🇪🇺',
    categories: [
      {
        code: 'policy',
        name: '金融政策',
        icon: <BankOutlined />,
        color: '#1890ff',
        indicators: [
          { code: 'policy-rate', name: '政策金利' },
          { code: 'ecb-statement', name: 'ECB声明' },
        ],
      },
      {
        code: 'economy',
        name: '経済',
        icon: <DollarOutlined />,
        color: '#52c41a',
        indicators: [
          { code: 'gdp', name: 'GDP' },
          { code: 'pmi', name: 'PMI' },
        ],
      },
      {
        code: 'consumer',
        name: '消費',
        icon: <ShoppingOutlined />,
        color: '#13c2c2',
        indicators: [
          { code: 'retail-sales', name: '小売売上高' },
        ],
      },
      {
        code: 'employment',
        name: '雇用',
        icon: <TeamOutlined />,
        color: '#faad14',
        indicators: [
          { code: 'unemployment', name: '失業率' },
        ],
      },
      {
        code: 'inflation',
        name: '物価',
        icon: <RiseOutlined />,
        color: '#ff4d4f',
        indicators: [
          { code: 'hicp', name: 'HICP' },
          { code: 'ppi', name: 'PPI' },
        ],
      },
      {
        code: 'housing',
        name: '住宅',
        icon: <HomeOutlined />,
        color: '#722ed1',
        indicators: [
          { code: 'hpi', name: '住宅価格指数' },
        ],
      },
    ],
  },
  {
    code: 'uk',
    name: 'イギリス',
    flag: '🇬🇧',
    categories: [
      {
        code: 'policy',
        name: '金融政策',
        icon: <BankOutlined />,
        color: '#1890ff',
        indicators: [
          { code: 'policy-rate', name: '政策金利' },
          { code: 'boe-statement', name: 'BOE声明' },
        ],
      },
      {
        code: 'economy',
        name: '経済',
        icon: <DollarOutlined />,
        color: '#52c41a',
        indicators: [
          { code: 'gdp', name: 'GDP' },
          { code: 'pmi', name: 'PMI' },
        ],
      },
      {
        code: 'consumer',
        name: '消費',
        icon: <ShoppingOutlined />,
        color: '#13c2c2',
        indicators: [
          { code: 'retail-sales', name: '小売売上高' },
        ],
      },
      {
        code: 'employment',
        name: '雇用',
        icon: <TeamOutlined />,
        color: '#faad14',
        indicators: [
          { code: 'unemployment', name: '失業率' },
          { code: 'claimant-count', name: '失業保険申請件数' },
        ],
      },
      {
        code: 'inflation',
        name: '物価',
        icon: <RiseOutlined />,
        color: '#ff4d4f',
        indicators: [
          { code: 'cpi', name: 'CPI' },
          { code: 'ppi', name: 'PPI' },
        ],
      },
      {
        code: 'housing',
        name: '住宅',
        icon: <HomeOutlined />,
        color: '#722ed1',
        indicators: [
          { code: 'hpi', name: '住宅価格指数' },
        ],
      },
    ],
  },
  {
    code: 'china',
    name: '中国',
    flag: '🇨🇳',
    categories: [
      {
        code: 'policy',
        name: '金融政策',
        icon: <BankOutlined />,
        color: '#1890ff',
        indicators: [
          { code: 'lpr', name: 'LPR' },
          { code: 'rrr', name: '預金準備率' },
        ],
      },
      {
        code: 'economy',
        name: '経済',
        icon: <DollarOutlined />,
        color: '#52c41a',
        indicators: [
          { code: 'gdp', name: 'GDP' },
          { code: 'pmi', name: 'PMI' },
          { code: 'industrial-production', name: '鉱工業生産' },
        ],
      },
      {
        code: 'consumer',
        name: '消費',
        icon: <ShoppingOutlined />,
        color: '#13c2c2',
        indicators: [
          { code: 'retail-sales', name: '小売売上高' },
        ],
      },
      {
        code: 'employment',
        name: '雇用',
        icon: <TeamOutlined />,
        color: '#faad14',
        indicators: [
          { code: 'unemployment', name: '失業率' },
        ],
      },
      {
        code: 'inflation',
        name: '物価',
        icon: <RiseOutlined />,
        color: '#ff4d4f',
        indicators: [
          { code: 'cpi', name: 'CPI' },
          { code: 'ppi', name: 'PPI' },
        ],
      },
      {
        code: 'housing',
        name: '住宅',
        icon: <HomeOutlined />,
        color: '#722ed1',
        indicators: [
          { code: 'hpi', name: '住宅価格' },
        ],
      },
    ],
  },
  {
    code: 'australia',
    name: 'オーストラリア',
    flag: '🇦🇺',
    categories: [
      {
        code: 'policy',
        name: '金融政策',
        icon: <BankOutlined />,
        color: '#1890ff',
        indicators: [
          { code: 'policy-rate', name: '政策金利' },
          { code: 'rba-statement', name: 'RBA声明' },
        ],
      },
      {
        code: 'economy',
        name: '経済',
        icon: <DollarOutlined />,
        color: '#52c41a',
        indicators: [
          { code: 'gdp', name: 'GDP' },
          { code: 'trade-balance', name: '貿易収支' },
        ],
      },
      {
        code: 'consumer',
        name: '消費',
        icon: <ShoppingOutlined />,
        color: '#13c2c2',
        indicators: [
          { code: 'retail-sales', name: '小売売上高' },
        ],
      },
      {
        code: 'employment',
        name: '雇用',
        icon: <TeamOutlined />,
        color: '#faad14',
        indicators: [
          { code: 'employment-change', name: '雇用者数変化' },
          { code: 'unemployment', name: '失業率' },
        ],
      },
      {
        code: 'inflation',
        name: '物価',
        icon: <RiseOutlined />,
        color: '#ff4d4f',
        indicators: [
          { code: 'cpi', name: 'CPI' },
        ],
      },
      {
        code: 'housing',
        name: '住宅',
        icon: <HomeOutlined />,
        color: '#722ed1',
        indicators: [
          { code: 'building-permits', name: '建設許可' },
        ],
      },
    ],
  },
  {
    code: 'newzealand',
    name: 'ニュージーランド',
    flag: '🇳🇿',
    categories: [
      {
        code: 'policy',
        name: '金融政策',
        icon: <BankOutlined />,
        color: '#1890ff',
        indicators: [
          { code: 'policy-rate', name: '政策金利' },
          { code: 'rbnz-statement', name: 'RBNZ声明' },
        ],
      },
      {
        code: 'economy',
        name: '経済',
        icon: <DollarOutlined />,
        color: '#52c41a',
        indicators: [
          { code: 'gdp', name: 'GDP' },
          { code: 'trade-balance', name: '貿易収支' },
        ],
      },
      {
        code: 'consumer',
        name: '消費',
        icon: <ShoppingOutlined />,
        color: '#13c2c2',
        indicators: [
          { code: 'retail-sales', name: '小売売上高' },
        ],
      },
      {
        code: 'employment',
        name: '雇用',
        icon: <TeamOutlined />,
        color: '#faad14',
        indicators: [
          { code: 'unemployment', name: '失業率' },
        ],
      },
      {
        code: 'inflation',
        name: '物価',
        icon: <RiseOutlined />,
        color: '#ff4d4f',
        indicators: [
          { code: 'cpi', name: 'CPI' },
        ],
      },
      {
        code: 'housing',
        name: '住宅',
        icon: <HomeOutlined />,
        color: '#722ed1',
        indicators: [
          { code: 'building-permits', name: '建設許可' },
        ],
      },
    ],
  },
  {
    code: 'canada',
    name: 'カナダ',
    flag: '🇨🇦',
    categories: [
      {
        code: 'policy',
        name: '金融政策',
        icon: <BankOutlined />,
        color: '#1890ff',
        indicators: [
          { code: 'policy-rate', name: '政策金利' },
          { code: 'boc-statement', name: 'BOC声明' },
        ],
      },
      {
        code: 'economy',
        name: '経済',
        icon: <DollarOutlined />,
        color: '#52c41a',
        indicators: [
          { code: 'gdp', name: 'GDP' },
          { code: 'trade-balance', name: '貿易収支' },
        ],
      },
      {
        code: 'consumer',
        name: '消費',
        icon: <ShoppingOutlined />,
        color: '#13c2c2',
        indicators: [
          { code: 'retail-sales', name: '小売売上高' },
        ],
      },
      {
        code: 'employment',
        name: '雇用',
        icon: <TeamOutlined />,
        color: '#faad14',
        indicators: [
          { code: 'employment-change', name: '雇用者数変化' },
          { code: 'unemployment', name: '失業率' },
        ],
      },
      {
        code: 'inflation',
        name: '物価',
        icon: <RiseOutlined />,
        color: '#ff4d4f',
        indicators: [
          { code: 'cpi', name: 'CPI' },
        ],
      },
      {
        code: 'housing',
        name: '住宅',
        icon: <HomeOutlined />,
        color: '#722ed1',
        indicators: [
          { code: 'building-permits', name: '建設許可' },
          { code: 'hpi', name: '住宅価格指数' },
        ],
      },
    ],
  },
  {
    code: 'switzerland',
    name: 'スイス',
    flag: '🇨🇭',
    categories: [
      {
        code: 'policy',
        name: '金融政策',
        icon: <BankOutlined />,
        color: '#1890ff',
        indicators: [
          { code: 'policy-rate', name: '政策金利' },
          { code: 'snb-statement', name: 'SNB声明' },
        ],
      },
      {
        code: 'economy',
        name: '経済',
        icon: <DollarOutlined />,
        color: '#52c41a',
        indicators: [
          { code: 'gdp', name: 'GDP' },
          { code: 'trade-balance', name: '貿易収支' },
        ],
      },
      {
        code: 'consumer',
        name: '消費',
        icon: <ShoppingOutlined />,
        color: '#13c2c2',
        indicators: [
          { code: 'retail-sales', name: '小売売上高' },
        ],
      },
      {
        code: 'employment',
        name: '雇用',
        icon: <TeamOutlined />,
        color: '#faad14',
        indicators: [
          { code: 'unemployment', name: '失業率' },
        ],
      },
      {
        code: 'inflation',
        name: '物価',
        icon: <RiseOutlined />,
        color: '#ff4d4f',
        indicators: [
          { code: 'cpi', name: 'CPI' },
        ],
      },
      {
        code: 'housing',
        name: '住宅',
        icon: <HomeOutlined />,
        color: '#722ed1',
        indicators: [
          { code: 'hpi', name: '住宅価格指数' },
        ],
      },
    ],
  },
]

function SidebarNavigation() {
  const navigate = useNavigate()
  const location = useLocation()
  const [openKeys, setOpenKeys] = useState<string[]>([])
  const [selectedIndicator, setSelectedIndicator] = useState<string>('')

  // 国コードからISO 2文字コードへのマッピング（flag-icons用）
  const countryIsoCodes: Record<string, string> = {
    usa: 'us',
    japan: 'jp',
    eurozone: 'eu',
    uk: 'gb',
    china: 'cn',
    australia: 'au',
    newzealand: 'nz',
    canada: 'ca',
    switzerland: 'ch',
  }

  // 3階層メニュー: 国 > カテゴリ > 経済指標
  // 小見出し（経済指標）はカテゴリページ + ハッシュで遷移
  const menuItems: MenuItem[] = useMemo(() => {
    return COUNTRIES_DATA.map((country) => ({
      key: `/country/${country.code}`,
      icon: (
        <span
          className={`fi fi-${countryIsoCodes[country.code] || country.code}`}
          style={{
            fontSize: '16px',
            borderRadius: '2px',
          }}
        />
      ),
      label: (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
          <span
            className={`fi fi-${countryIsoCodes[country.code] || country.code}`}
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
          // ヘッダーの高さ（64px）+ 余白（24px）を考慮してスクロール
          const headerOffset = 88
          const elementPosition = element.getBoundingClientRect().top
          const offsetPosition = elementPosition + window.pageYOffset - headerOffset
          window.scrollTo({
            top: offsetPosition,
            behavior: 'smooth'
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
      selectedKeys={selectedKeys}
      openKeys={openKeys}
      onOpenChange={handleOpenChange}
      items={menuItems}
      onClick={handleMenuClick}
      style={{ height: '100%', borderRight: 0 }}
    />
  )
}

export default SidebarNavigation
