import { useEffect, useRef, useState } from 'react'
import { Tabs } from 'antd'

// FinancialJuice Widget用の型定義
declare global {
  interface Window {
    FJWidgets?: {
      createWidget: (options: Record<string, unknown>) => void
    }
  }
}

// 国コードとInvesting.comのcountriesパラメータのマッピング
const INVESTING_COUNTRY_CODES: Record<string, string> = {
  usa: '5',
  japan: '35',
  eurozone: '10,17,22,72', // ドイツ、フランス、イタリア、スペイン
  uk: '4',
  china: '37',
  australia: '25',
  newzealand: '43',
  canada: '6',
  switzerland: '12',
  all: '5,4,10,25,6,12,17,43,22,72,37,46,35,11', // 各国データページ・ホーム用
}

interface EconomicCalendarWidgetsProps {
  countryCode?: string
}

/**
 * 経済カレンダーウィジェット（Investing.com + FinancialJuice）
 * 右サイドバーに縦並びで表示
 */
function EconomicCalendarWidgets({ countryCode = 'usa' }: EconomicCalendarWidgetsProps) {
  const fjContainerRef = useRef<HTMLDivElement>(null)
  const fjInitialized = useRef(false)
  const [activeTab, setActiveTab] = useState('investing')

  // 国コードからInvesting.comのcountriesパラメータを取得
  const investingCountries = INVESTING_COUNTRY_CODES[countryCode] || INVESTING_COUNTRY_CODES.all

  // FinancialJuice Widgetの初期化（タブが切り替わった時に実行）
  useEffect(() => {
    if (activeTab !== 'financialjuice') return
    if (fjInitialized.current) return

    // 少し遅延させてDOMが準備されるのを待つ
    const timer = setTimeout(() => {
      // 既存のスクリプトがあれば再利用
      const existingScript = document.getElementById('FJ-Widgets')
      if (existingScript && window.FJWidgets) {
        initializeFJWidget()
        fjInitialized.current = true
        return
      }

      // スクリプトを動的に読み込み
      const script = document.createElement('script')
      script.type = 'text/javascript'
      script.id = 'FJ-Widgets'
      const r = Math.floor(Math.random() * 10000)
      script.src = `https://feed.financialjuice.com/widgets/widgets.js?r=${r}`
      script.onload = () => {
        // スクリプト読み込み後、少し待ってから初期化
        setTimeout(() => {
          initializeFJWidget()
          fjInitialized.current = true
        }, 200)
      }
      script.onerror = () => {
        console.error('Failed to load FinancialJuice widget script')
      }
      document.head.appendChild(script)
    }, 100)

    return () => clearTimeout(timer)
  }, [activeTab])

  const initializeFJWidget = () => {
    if (!window.FJWidgets) {
      console.error('FJWidgets not available')
      return
    }

    // コンテナが存在するか確認
    const container = document.getElementById('financialjuice-eco-widget-container')
    if (!container) {
      console.error('FinancialJuice container not found')
      return
    }

    // ビューポートの高さからピクセル値を計算
    const calculatedHeight = window.innerHeight - 180

    const options = {
      container: 'financialjuice-eco-widget-container',
      mode: 'table',
      width: '100%',
      height: `${calculatedHeight}px`,
      backColor: '0a0a0a',
      fontColor: 'b2b5be',
      widgetType: 'ECOCAL',
    }

    console.log('Initializing FinancialJuice widget with options:', options)
    window.FJWidgets.createWidget(options)
  }

  // EconAlpha ダークテーマ用カラー（全て黒仕様）
  const colors = {
    bgPrimary: '000000',      // 完全黒
    bgSecondary: '0a0a0a',    // ほぼ黒
    bgTertiary: '1a1a1a',     // 暗いグレー
    accent: '10b981',         // #10b981
    border: '1a1a1a',
    textPrimary: 'f1f5f9',
    textSecondary: '94a3b8',
  }

  const tabItems = [
    {
      key: 'investing',
      label: 'Investing.com',
      children: (
        <div>
          <iframe
            src={`https://sslecal2.investing.com?ecoDayBackground=%23${colors.bgSecondary}&innerBorderColor=%23${colors.bgTertiary}&borderColor=%23${colors.border}&columns=exc_flags,exc_currency,exc_importance,exc_actual,exc_forecast,exc_previous&features=datepicker,timezone,timeselector,filters&countries=${investingCountries}&calType=week&timeZone=29&lang=11`}
            width="100%"
            height="calc(100vh - 180px)"
            frameBorder="0"
            allowTransparency={true}
            style={{ display: 'block', minHeight: 700, background: '#000000' }}
            title="Investing.com Economic Calendar"
          />
          <div
            style={{
              padding: '4px 8px',
              background: '#0a0a0a',
              borderTop: '1px solid #1a1a1a',
              fontSize: 10,
              color: '#94a3b8',
            }}
          >
            <a
              href="https://jp.investing.com/"
              rel="nofollow noopener noreferrer"
              target="_blank"
              style={{ color: '#10b981' }}
            >
              Investing.com
            </a>
            {' '}提供
          </div>
        </div>
      ),
    },
    {
      key: 'financialjuice',
      label: 'FinancialJuice',
      children: (
        <div
          ref={fjContainerRef}
          id="financialjuice-eco-widget-container"
          style={{
            width: '100%',
            height: 'calc(100vh - 180px)',
            minHeight: 700,
            background: '#0a0a0a',
          }}
        />
      ),
    },
  ]

  return (
    <Tabs
      activeKey={activeTab}
      onChange={setActiveTab}
      items={tabItems}
      size="small"
      style={{ marginTop: -8 }}
    />
  )
}

export default EconomicCalendarWidgets
