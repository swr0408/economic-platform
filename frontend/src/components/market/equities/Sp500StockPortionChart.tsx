/**
 * S&P500 移動平均線上銘柄比率チャートコンポーネント
 *
 * TradingViewウィジェットでリアルタイム表示
 * シンボル:
 *   S5TW - 20日移動平均線上銘柄比率
 *   S5FI - 50日移動平均線上銘柄比率
 *   S5TH - 200日移動平均線上銘柄比率
 *
 * データソース: TradingView
 */
import { useState } from 'react'
import ChartContainer from '../../common/ChartContainer'
import TradingViewWidget from '../../common/TradingViewWidget'
import { ViewModeButtonGroup } from '../../country/usa/common/ChartComponents'

type SymbolMode = 's5tw' | 's5fi' | 's5th'

const SYMBOL_OPTIONS = [
  { mode: 's5tw' as SymbolMode, label: '20日線上' },
  { mode: 's5fi' as SymbolMode, label: '50日線上' },
  { mode: 's5th' as SymbolMode, label: '200日線上' },
]

const SYMBOL_MAP: Record<SymbolMode, string> = {
  s5tw: 'S5TW',
  s5fi: 'S5FI',
  s5th: 'S5TH',
}

export default function Sp500StockPortionChart() {
  const [symbolMode, setSymbolMode] = useState<SymbolMode>('s5tw')

  return (
    <div id="sp500-stock-portion">
      <ChartContainer
        title="S&P500 移動平均線上銘柄比率"
        showPeriodSelector={false}
        dataSource="TradingView"
        sourceUrl="https://www.tradingview.com/symbols/S5TW/"
      >
        <ViewModeButtonGroup
          options={SYMBOL_OPTIONS}
          currentMode={symbolMode}
          onChange={(m) => setSymbolMode(m as SymbolMode)}
        />
        <div style={{ height: 500, marginTop: 8 }}>
          <TradingViewWidget
            symbol={SYMBOL_MAP[symbolMode]}
            height={500}
            theme="light"
            interval="D"
            timezone="Asia/Tokyo"
            locale="ja"
            hideTopToolbar={false}
            hideSideToolbar={true}
            hideLegend={false}
            hideVolume={false}
            allowSymbolChange={false}
            chartStyle="2"
          />
        </div>
      </ChartContainer>
    </div>
  )
}
