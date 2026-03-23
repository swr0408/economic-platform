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
        handbookId="growth-value-ratio"
      >
        <div style={{ height: 610 }}>
          <TradingViewWidget
            symbol="GROWTH_VALUE_RATIO"
            height={610}
            chartStyle="2"
          />
        </div>
      </ChartContainer>
    </div>
  )
}
