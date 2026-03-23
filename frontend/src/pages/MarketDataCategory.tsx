import React, { Suspense, useEffect } from 'react'
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom'
import { Button, Space, Typography, Tooltip } from 'antd'
import { ArrowLeftOutlined, QuestionCircleOutlined } from '@ant-design/icons'
import { getMarketCategory, getFirstSubCategoryCode, getMarketSubCategory } from '../constants/marketData'
import { useHandbook } from '../contexts/HandbookContext'
import LoadingChart from '../components/common/LoadingChart'

const { Title, Text } = Typography

const colors = {
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
}

const CATEGORY_HANDBOOK_MAP: Record<string, string> = {
  cot: 'cftc-positioning',
  options: 'options-guide',
}

// React.lazy で各サブカテゴリチャートをコード分割
const SUBCATEGORY_CHARTS: Record<string, Record<string, React.LazyExoticComponent<React.ComponentType>>> = {
  equities: {
    'us-equities': React.lazy(() => import('../components/market/equities/UsEquitiesCharts')),
    'jp-equities': React.lazy(() => import('../components/market/equities/JpEquitiesCharts')),
    'eu-equities': React.lazy(() => import('../components/market/equities/EuEquitiesCharts')),
    'tw-semiconductor': React.lazy(() => import('../components/market/equities/TwSemiconductorCharts')),
  },
  forex: {
    'usd-pairs': React.lazy(() => import('../components/market/forex/UsdPairsCharts')),
    'jpy-crosses': React.lazy(() => import('../components/market/forex/JpyCrossesCharts')),
    'eur-crosses': React.lazy(() => import('../components/market/forex/EurCrossesCharts')),
    'gbp-crosses': React.lazy(() => import('../components/market/forex/GbpCrossesCharts')),
    'other-crosses': React.lazy(() => import('../components/market/forex/OtherCrossesCharts')),
    'currency-index': React.lazy(() => import('../components/market/forex/CurrencyIndexCharts')),
  },
  commodities: {
    'precious-metals': React.lazy(() => import('../components/market/commodities/PreciousMetalsCharts')),
    'industrial-metals': React.lazy(() => import('../components/market/commodities/IndustrialMetalsCharts')),
  },
  energy: {
    'crude-oil': React.lazy(() => import('../components/market/energy/CrudeOilCharts')),
    'natural-gas': React.lazy(() => import('../components/market/energy/NaturalGasCharts')),
  },
  cot: {
    'cot-equities': React.lazy(() => import('../components/market/cot/CotEquitiesCharts')),
    'cot-forex': React.lazy(() => import('../components/market/cot/CotForexCharts')),
    'cot-bonds': React.lazy(() => import('../components/market/cot/CotBondsCharts')),
    'cot-commodities': React.lazy(() => import('../components/market/cot/CotCommoditiesCharts')),
    'cot-energy': React.lazy(() => import('../components/market/cot/CotEnergyCharts')),
  },
  options: {
    'equity-options': React.lazy(() => import('../components/market/options/EquityOptionsCharts')),
    'fx-options': React.lazy(() => import('../components/market/options/FxOptionsCharts')),
    'commodity-options': React.lazy(() => import('../components/market/options/CommodityOptionsCharts')),
  },
}

function MarketDataCategory() {
  const { categoryCode, subCategoryCode } = useParams<{
    categoryCode: string
    subCategoryCode?: string
  }>()
  const navigate = useNavigate()
  const location = useLocation()
  const { openHandbook } = useHandbook()

  const category = categoryCode ? getMarketCategory(categoryCode) : undefined

  // リダイレクト: /markets/equities → /markets/equities/us-equities
  // 後方互換: /markets/equities#sp500 → /markets/equities/us-equities#sp500
  useEffect(() => {
    if (!categoryCode || !category || subCategoryCode) return

    const hash = location.hash?.replace('#', '')

    if (hash) {
      // ハッシュがサブカテゴリコード自体の場合
      const sub = category.subCategories.find((s) => s.code === hash)
      if (sub) {
        navigate(`/markets/${categoryCode}/${sub.code}`, { replace: true })
        return
      }
      // ハッシュがインジケーターコードの場合、所属サブカテゴリを検索
      for (const sub of category.subCategories) {
        if (sub.indicators.some((ind) => ind.code === hash)) {
          navigate(`/markets/${categoryCode}/${sub.code}#${hash}`, { replace: true })
          return
        }
      }
    }

    // デフォルト: 最初のサブカテゴリへリダイレクト
    const firstSub = getFirstSubCategoryCode(categoryCode)
    if (firstSub) {
      navigate(`/markets/${categoryCode}/${firstSub}`, { replace: true })
    }
  }, [categoryCode, subCategoryCode, category, navigate, location.hash])

  // ハッシュスクロール
  useEffect(() => {
    if (!location.hash || !subCategoryCode) return
    const hash = location.hash.replace('#', '')
    const timer = setTimeout(() => {
      const element = document.getElementById(hash)
      if (element) {
        const headerOffset = 80
        const elementPosition = element.getBoundingClientRect().top
        const offsetPosition = elementPosition + window.pageYOffset - headerOffset
        window.scrollTo({ top: offsetPosition, behavior: 'smooth' })
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [location.hash, subCategoryCode])

  if (!categoryCode || !category) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Text style={{ color: colors.textSecondary }}>カテゴリが見つかりませんでした。</Text>
        <br />
        <Link to="/markets">
          <Button type="link" icon={<ArrowLeftOutlined />} style={{ color: '#10b981' }}>
            マーケットデータ一覧へ戻る
          </Button>
        </Link>
      </div>
    )
  }

  // リダイレクト待ち
  if (!subCategoryCode) return null

  const subCategory = getMarketSubCategory(categoryCode, subCategoryCode)
  const SubCategoryCharts = SUBCATEGORY_CHARTS[categoryCode]?.[subCategoryCode]

  if (!subCategory || !SubCategoryCharts) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Text style={{ color: colors.textSecondary }}>サブカテゴリが見つかりませんでした。</Text>
        <br />
        <Link to="/markets">
          <Button type="link" icon={<ArrowLeftOutlined />} style={{ color: '#10b981' }}>
            マーケットデータ一覧へ戻る
          </Button>
        </Link>
      </div>
    )
  }

  return (
    <div style={{ padding: '20px 24px' }}>
      <Space style={{ marginBottom: 24 }} wrap>
        <Link to="/markets">
          <Button type="default" icon={<ArrowLeftOutlined />}>
            マーケットデータ一覧
          </Button>
        </Link>
      </Space>

      <div style={{ marginBottom: 24 }}>
        <Space size={12} align="center">
          {React.cloneElement(category.icon as React.ReactElement, {
            style: { fontSize: 24, color: category.color },
          })}
          <Title level={3} style={{ margin: 0, color: colors.textPrimary }}>
            {category.name}
          </Title>
          <Text style={{ color: colors.textSecondary, fontSize: 14 }}>/ {subCategory.name}</Text>
          {categoryCode && CATEGORY_HANDBOOK_MAP[categoryCode] && (
            <Tooltip title="データハンドブック">
              <QuestionCircleOutlined
                onClick={() => openHandbook(CATEGORY_HANDBOOK_MAP[categoryCode])}
                style={{ fontSize: 18, color: colors.textSecondary, cursor: 'pointer', transition: 'color 0.2s' }}
                onMouseEnter={(e) => { (e.target as HTMLElement).style.color = '#10b981' }}
                onMouseLeave={(e) => { (e.target as HTMLElement).style.color = colors.textSecondary }}
              />
            </Tooltip>
          )}
        </Space>
        <Text
          style={{
            fontSize: 13,
            color: colors.textSecondary,
            display: 'block',
            marginTop: 4,
            marginLeft: 36,
          }}
        >
          {category.description}
        </Text>
      </div>

      <Suspense fallback={<LoadingChart title={`${subCategory.name}データ読み込み中...`} />}>
        <SubCategoryCharts />
      </Suspense>
    </div>
  )
}

export default MarketDataCategory
