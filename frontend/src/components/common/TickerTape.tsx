/**
 * TradingView Ticker Tape ウィジェット
 *
 * カスタム要素 <tv-ticker-tape> を使う方式。
 * 外部スクリプト (widgets.tradingview-widget.com/w/en/tv-ticker-tape.js) を
 * 一度だけロードし、カスタム要素を描画する。
 */
import { useEffect, useRef } from 'react'

const SCRIPT_SRC = 'https://widgets.tradingview-widget.com/w/en/tv-ticker-tape.js'
const SCRIPT_ID = 'tv-ticker-tape-script'

const DEFAULT_SYMBOLS =
  'PYTH:US10Y,FOREXCOM:JP225,FOREXCOM:US30,FOREXCOM:SPX500,FOREXCOM:NAS100,FOREXCOM:USOIL,FOREXCOM:NATURALGAS,FOREXCOM:XAUUSD,FOREXCOM:XAGUSD,FOREXCOM:USDJPY,FOREXCOM:EURUSD'

interface TickerTapeProps {
  symbols?: string
  showHover?: boolean
}

// カスタム要素 tv-ticker-tape の型宣言 (TypeScript JSX 対応)
declare global {
  namespace JSX {
    interface IntrinsicElements {
      'tv-ticker-tape': React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement> & {
          symbols?: string
          'show-hover'?: boolean | string
        },
        HTMLElement
      >
    }
  }
}

function TickerTape({ symbols = DEFAULT_SYMBOLS, showHover = true }: TickerTapeProps) {
  const hostRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // スクリプトが未ロードなら一度だけ挿入
    if (!document.getElementById(SCRIPT_ID)) {
      const script = document.createElement('script')
      script.id = SCRIPT_ID
      script.type = 'module'
      script.src = SCRIPT_SRC
      script.async = true
      document.head.appendChild(script)
    }
  }, [])

  return (
    <div ref={hostRef} style={{ width: '100%' }}>
      {/* @ts-expect-error - TradingView custom element */}
      <tv-ticker-tape symbols={symbols} {...(showHover ? { 'show-hover': '' } : {})} />
    </div>
  )
}

export default TickerTape
