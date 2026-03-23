/**
 * EarningsCategory
 *
 * Routes:
 *   /earnings/calendar        → redirect to /earnings/calendar/all
 *   /earnings/calendar/all    → 全国統一カレンダー
 *   /earnings/calendar/:cc    → 国別カレンダー
 *   /earnings/data            → 国選択グリッド
 *   /earnings/data/:cc        → 国別決算データ
 */
import React, { useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { Button, Space, Typography, Alert } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { getEarningsCategory, getEarningsCountry, EARNINGS_COUNTRIES } from '../constants/earningsData'
import EarningsCalendarPage from '../components/earnings/EarningsCalendarPage'
import EarningsDataPage from '../components/earnings/EarningsDataPage'

const { Title, Text } = Typography

const colors = {
  textPrimary:  '#f1f5f9',
  textSecondary:'#94a3b8',
  bgSecondary:  '#1e293b',
  border:       '#334155',
  accent:       '#10b981',
}

export default function EarningsCategory() {
  const { categoryCode, countryCode } = useParams<{ categoryCode: string; countryCode?: string }>()
  const navigate = useNavigate()

  // /earnings/calendar → /earnings/calendar/all へリダイレクト
  useEffect(() => {
    if (categoryCode === 'calendar' && !countryCode) {
      navigate('/earnings/calendar/all', { replace: true })
    }
  }, [categoryCode, countryCode, navigate])

  if (!categoryCode) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Text style={{ color: colors.textSecondary }}>カテゴリが指定されていません。</Text>
        <br />
        <Link to="/earnings">
          <Button type="link" icon={<ArrowLeftOutlined />} style={{ color: colors.accent }}>
            決算トップへ戻る
          </Button>
        </Link>
      </div>
    )
  }

  const category = getEarningsCategory(categoryCode)

  if (!category) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Text style={{ color: colors.textSecondary }}>カテゴリが見つかりませんでした。</Text>
        <br />
        <Link to="/earnings">
          <Button type="link" icon={<ArrowLeftOutlined />} style={{ color: colors.accent }}>
            決算トップへ戻る
          </Button>
        </Link>
      </div>
    )
  }

  // -----------------------------------------------------------------------
  // /earnings/calendar/[all|countryCode]  → EarningsCalendarPage
  // -----------------------------------------------------------------------
  if (categoryCode === 'calendar') {
    const cc = countryCode ?? 'all'
    const countryDef = cc !== 'all' ? getEarningsCountry(cc) : null

    if (cc !== 'all' && !countryDef) {
      return (
        <div style={{ padding: '20px 24px' }}>
          <Alert type="error" message={`国コード "${cc}" が見つかりません`} showIcon />
        </div>
      )
    }

    return (
      <div style={{ padding: '20px 24px' }}>
        {/* パンくず */}
        <Space style={{ marginBottom: 20 }} wrap>
          <Link to="/earnings">
            <Button type="default" icon={<ArrowLeftOutlined />} size="small">
              決算トップ
            </Button>
          </Link>
        </Space>

        {/* タイトル */}
        <div style={{ marginBottom: 20 }}>
          <Space size={10} align="center">
            {React.cloneElement(category.icon as React.ReactElement, {
              style: { fontSize: 22, color: category.color },
            })}
            <Title level={3} style={{ margin: 0, color: colors.textPrimary }}>
              {category.nameJa}
              {countryDef && (
                <span style={{ fontSize: 18, marginLeft: 8 }}>
                  — {countryDef.flag} {countryDef.nameJa}
                </span>
              )}
            </Title>
          </Space>
          <Text style={{ fontSize: 13, color: colors.textSecondary, display: 'block', marginTop: 4, marginLeft: 32 }}>
            {category.description}
          </Text>
        </div>

        <EarningsCalendarPage countryCode={cc} />
      </div>
    )
  }

  // -----------------------------------------------------------------------
  // /earnings/data  → 国選択グリッド
  // -----------------------------------------------------------------------
  if (categoryCode === 'data' && !countryCode) {
    return (
      <div style={{ padding: '20px 24px' }}>
        <Space style={{ marginBottom: 20 }} wrap>
          <Link to="/earnings">
            <Button type="default" icon={<ArrowLeftOutlined />} size="small">
              決算トップ
            </Button>
          </Link>
        </Space>

        <div style={{ marginBottom: 24 }}>
          <Space size={10} align="center">
            {React.cloneElement(category.icon as React.ReactElement, {
              style: { fontSize: 22, color: category.color },
            })}
            <Title level={3} style={{ margin: 0, color: colors.textPrimary }}>
              {category.nameJa}
            </Title>
          </Space>
          <Text style={{ fontSize: 13, color: colors.textSecondary, display: 'block', marginTop: 4, marginLeft: 32 }}>
            {category.description}
          </Text>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
            gap: 12,
          }}
        >
          {EARNINGS_COUNTRIES.map((country) => (
            <Link
              key={country.code}
              to={`/earnings/data/${country.code}`}
              style={{ textDecoration: 'none' }}
            >
              <div
                style={{
                  background: colors.bgSecondary,
                  border: `1px solid ${colors.border}`,
                  borderRadius: 8,
                  padding: '14px 18px',
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = country.color
                  e.currentTarget.style.background = `${country.color}10`
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = colors.border
                  e.currentTarget.style.background = colors.bgSecondary
                }}
              >
                <span style={{ fontSize: 22 }}>{country.flag}</span>
                <div>
                  <Text style={{ color: colors.textPrimary, fontSize: 13, fontWeight: 500 }}>
                    {country.nameJa}
                  </Text>
                  <br />
                  <Text style={{ color: colors.textSecondary, fontSize: 11 }}>
                    {country.companies.length} 社
                  </Text>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    )
  }

  // -----------------------------------------------------------------------
  // /earnings/data/:countryCode  → EarningsDataPage
  // -----------------------------------------------------------------------
  if (categoryCode === 'data' && countryCode) {
    const countryDef = getEarningsCountry(countryCode)

    if (!countryDef) {
      return (
        <div style={{ padding: '20px 24px' }}>
          <Alert type="error" message={`国コード "${countryCode}" が見つかりません`} showIcon />
        </div>
      )
    }

    return (
      <div style={{ padding: '20px 24px' }}>
        <Space style={{ marginBottom: 20 }} wrap>
          <Link to="/earnings/data">
            <Button type="default" icon={<ArrowLeftOutlined />} size="small">
              国選択
            </Button>
          </Link>
        </Space>

        <div style={{ marginBottom: 24 }}>
          <Space size={10} align="center">
            <span style={{ fontSize: 24 }}>{countryDef.flag}</span>
            {React.cloneElement(category.icon as React.ReactElement, {
              style: { fontSize: 20, color: category.color },
            })}
            <Title level={3} style={{ margin: 0, color: colors.textPrimary }}>
              {countryDef.nameJa} — {category.nameJa}
            </Title>
          </Space>
          <Text style={{ fontSize: 13, color: colors.textSecondary, display: 'block', marginTop: 4, marginLeft: 44 }}>
            {category.description}
          </Text>
        </div>

        <EarningsDataPage countryCode={countryCode} />
      </div>
    )
  }

  return (
    <div style={{ padding: '20px 24px' }}>
      <Alert type="info" message="該当するページが見つかりません" showIcon />
    </div>
  )
}
