/**
 * Growth/Value レシオチャートコンポーネント
 *
 * TradingViewウィジェットでリアルタイム表示
 * シンボル: AMEX:IVW / AMEX:IVE (S&P 500 Growth ETF / S&P 500 Value ETF)
 *
 * データソース: TradingView
 */
import ChartContainer from '../../common/ChartContainer'
import TradingViewWidget from '../../common/TradingViewWidget'

export default function GrowthValueRatioChart() {
  return (
    <div id="growth-value-ratio">
      <ChartContainer
        title="Growth/Value レシオ (IVW/IVE)"
        showPeriodSelector={false}
        dataSource="TradingView"
        sourceUrl="https://www.tradingview.com/symbols/AMEX-IVW/AMEX-IVE/"
      >
        <div style={{ height: 500 }}>
          <TradingViewWidget
            symbol="GROWTH_VALUE_RATIO"
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
