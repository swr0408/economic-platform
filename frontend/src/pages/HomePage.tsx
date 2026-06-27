import { useState, useEffect, useCallback } from 'react'
import { Button, Space } from 'antd'
import { CalendarOutlined, LinkOutlined, MenuFoldOutlined } from '@ant-design/icons'
import EconomicCalendarWidgets from '../components/country/usa/EconomicCalendarWidgets'
import TickerTape from '../components/common/TickerTape'
import RecentPagesCard from '../components/home/RecentPagesCard'
import RecentUpdatesCard from '../components/home/RecentUpdatesCard'
import { useIsMaster } from '../hooks/useIsMaster'

const EXTERNAL_LINKS = [
  { label: 'IG証券', url: 'https://www.ig.com/jp/login?next=/jp/myig/dashboard' },
  { label: 'Mataf 通貨インデックス', url: 'https://www.mataf.net/en/forex/tools/currency-index' },
  { label: '世界の株価', url: 'https://sekai-kabuka.com/pc-index.html' },
  { label: 'ペンタゴン・ピザ・インデックス', url: 'https://www.pizzint.watch/' },
  { label: 'ソニーファイナンシャルグループ', url: 'https://www.sonyfg.co.jp/ja/market_report/' },
  { label: '第一ライフ資産運用経済研究所', url: 'https://www.dlri.co.jp/report_index.html' },
  { label: 'ANZオーストラリア経済ウィークリー', url: 'https://www.anz.com/institutional/global/japan/jpn/market-report/' },
  { label: 'セントラル短資ＦＸ', url: 'https://www.central-tanshifx.com/market/marketview/?morecnt=0&itemtype=3#' },
  { label: 'フィリップ証券', url: 'https://my-sso.phillip-sec-online.jp/login' },
  { label: 'UBS House View（日次）', url: 'https://www.ubs.com/global/en/wealthmanagement/insights/house-view.html' },
  { label: 'UBS CIO House View（週次（月曜））', url: 'https://www.ubs.com/global/en/wealthmanagement/insights/chief-investment-office/house-view.html' },
  { label: 'Wells Fargo Economics（週次（金曜））', url: 'https://www.wellsfargo.com/cib/insights/economics' },
  { label: 'J.P. Morgan Weekly Market Recap（株式・週次）', url: 'https://am.jpmorgan.com/us/en/asset-management/adv/insights/market-insights/market-updates/weekly-market-recap' },
  { label: 'J.P. Morgan Global Fixed Income Views（株式・四半期）', url: 'https://am.jpmorgan.com/jp/en/asset-management/institutional/insights/portfolio-insights/asset-class-views/' },
  { label: 'Goldman Sachs Insights（不定期）', url: 'https://www.goldmansachs.com/insights' },
  { label: 'Morgan Stanley Insights（不定期）', url: 'https://www.morganstanley.com/insights' },
  { label: 'Citi Global Markets & Economy（不定期）', url: 'https://www.citigroup.com/global/insights/global-markets-and-economy' },
  { label: 'Goldman Sachs Markets Outlook 2026（年次・ドル/G10 の方向感）', url: 'https://www.goldmansachs.com/insights/goldman-sachs-research/markets-outlook-2026-some-like-it-hot' },
  { label: 'Standard Chartered Global Research（年次・EM/アジア寄りのFX補完）', url: 'https://www.sc.com/en/corporate-investment-banking/global-markets/global-research/' },
  { label: 'Investing.com 経済カレンダー', url: 'https://jp.investing.com/economic-calendar/' },
  { label: 'MINKABU FX 経済指標', url: 'https://fx.minkabu.jp/indicators' },
  { label: '中東レート', url: 'https://www.xe.com/ja/currencycharts/' },
  { label: 'Weekend trading', url: 'https://www.ig.com/uk/weekend-trading' },
]

// 右サイドバー（経済カレンダー）のデフォルト幅と範囲
const CALENDAR_SIDEBAR_DEFAULT_WIDTH = 380
const CALENDAR_SIDEBAR_MIN_WIDTH = 320
const CALENDAR_SIDEBAR_MAX_WIDTH = 600

// EconAlpha カラーパレット
const colors = {
  bgPrimary: '#0f172a',
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  accent: '#10b981',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  border: '#334155',
}

type SidebarTab = 'calendar' | 'links'

function HomePage() {
  const [calendarOpen, setCalendarOpen] = useState(true)
  const [sidebarWidth, setSidebarWidth] = useState(CALENDAR_SIDEBAR_DEFAULT_WIDTH)
  const [isResizing, setIsResizing] = useState(false)
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>('calendar')
  const isMaster = useIsMaster()

  // リサイズハンドラー
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsResizing(true)
  }, [])

  // マウス移動でサイドバー幅を変更
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return
      const newWidth = window.innerWidth - e.clientX
      if (newWidth >= CALENDAR_SIDEBAR_MIN_WIDTH && newWidth <= CALENDAR_SIDEBAR_MAX_WIDTH) {
        setSidebarWidth(newWidth)
      }
    }

    const handleMouseUp = () => {
      if (isResizing) {
        setIsResizing(false)
      }
    }

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
      document.body.style.userSelect = 'none'
      document.body.style.cursor = 'col-resize'
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.body.style.userSelect = ''
      document.body.style.cursor = ''
    }
  }, [isResizing])

  return (
    <div style={{ display: 'flex', minHeight: 'calc(100vh - 64px)' }}>
      {/* メインコンテンツエリア */}
      <div
        style={{
          flex: 1,
          minWidth: 0,
          maxWidth: calendarOpen ? `calc(100% - ${sidebarWidth}px)` : '100%',
          padding: '0',
          transition: 'max-width 0.3s ease',
          overflowY: 'auto',
          overflowX: 'hidden',
        }}
      >
        {/* マーケットティッカー (TradingView) */}
        <div
          style={{
            background: colors.bgSecondary,
            borderBottom: `1px solid ${colors.border}`,
          }}
        >
          <TickerTape />
        </div>

        {/* メインダッシュボード */}
        <div style={{ padding: '16px 24px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* 最近見たページ */}
          <RecentPagesCard />

          {/* 直近更新された指標 */}
          <RecentUpdatesCard />
        </div>
      </div>

      {/* リサイズ中のオーバーレイ（iframeがマウスイベントを奪うのを防ぐ） */}
      {isResizing && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            zIndex: 9999,
            cursor: 'col-resize',
          }}
        />
      )}

      {/* 右サイドバー：経済カレンダー */}
      {calendarOpen && (
        <div
          style={{
            position: 'fixed',
            right: 0,
            top: 64,
            width: sidebarWidth,
            height: 'calc(100vh - 64px)',
            background: colors.bgSecondary,
            borderLeft: `1px solid ${colors.border}`,
            boxShadow: '-4px 0 16px rgba(0,0,0,0.2)',
            overflowY: 'auto',
            zIndex: 100,
          }}
        >
          {/* リサイズハンドル */}
          <div
            onMouseDown={handleMouseDown}
            style={{
              position: 'absolute',
              left: -3,
              top: 0,
              width: 8,
              height: '100%',
              cursor: 'col-resize',
              backgroundColor: isResizing ? colors.accent : 'transparent',
              transition: 'background-color 0.2s',
              zIndex: 101,
            }}
            onMouseEnter={(e) => {
              if (!isResizing) {
                e.currentTarget.style.backgroundColor = colors.bgTertiary
              }
            }}
            onMouseLeave={(e) => {
              if (!isResizing) {
                e.currentTarget.style.backgroundColor = 'transparent'
              }
            }}
          />
          <div style={{ padding: '12px 16px' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 12,
                paddingBottom: 10,
                borderBottom: `1px solid ${colors.border}`,
              }}
            >
              <Space size={4}>
                <Button
                  type="text"
                  size="small"
                  icon={<CalendarOutlined />}
                  onClick={() => setSidebarTab('calendar')}
                  style={{
                    color: sidebarTab === 'calendar' ? colors.accent : colors.textSecondary,
                    fontWeight: sidebarTab === 'calendar' ? 600 : 400,
                    background: sidebarTab === 'calendar' ? colors.bgTertiary : 'transparent',
                    borderRadius: 6,
                    padding: '4px 10px',
                  }}
                >
                  カレンダー
                </Button>
                {isMaster && (
                  <Button
                    type="text"
                    size="small"
                    icon={<LinkOutlined />}
                    onClick={() => setSidebarTab('links')}
                    style={{
                      color: sidebarTab === 'links' ? colors.accent : colors.textSecondary,
                      fontWeight: sidebarTab === 'links' ? 600 : 400,
                      background: sidebarTab === 'links' ? colors.bgTertiary : 'transparent',
                      borderRadius: 6,
                      padding: '4px 10px',
                    }}
                  >
                    リンク集
                  </Button>
                )}
              </Space>
              <Button
                type="text"
                icon={<MenuFoldOutlined style={{ color: colors.textSecondary }} />}
                onClick={() => setCalendarOpen(false)}
                size="small"
              />
            </div>
            {sidebarTab === 'calendar' && <EconomicCalendarWidgets countryCode="all" />}
            {sidebarTab === 'links' && isMaster && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {EXTERNAL_LINKS.map((link) => (
                  <a
                    key={link.url}
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      display: 'block',
                      padding: '10px 12px',
                      borderRadius: 6,
                      color: colors.textPrimary,
                      textDecoration: 'none',
                      fontSize: 13,
                      transition: 'background 0.15s',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = colors.bgTertiary
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'transparent'
                    }}
                  >
                    {link.label}
                  </a>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* カレンダーが閉じている時の開くボタン */}
      {!calendarOpen && (
        <Button
          type="primary"
          icon={<CalendarOutlined />}
          style={{
            position: 'fixed',
            right: 16,
            top: 80,
            zIndex: 101,
            background: colors.accent,
            borderColor: colors.accent,
          }}
          onClick={() => setCalendarOpen(true)}
        >
          カレンダー
        </Button>
      )}
    </div>
  )
}

export default HomePage
