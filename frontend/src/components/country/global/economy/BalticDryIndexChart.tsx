/**
 * バルチック海運指数（BDI）チャートコンポーネント
 *
 * TradingViewウィジェットでリアルタイム表示
 * シンボル: INDEX:BDI
 *
 * データソース: TradingView (Baltic Exchange)
 */
import ChartContainer from '../../../common/ChartContainer'
import TradingViewWidget from '../../../common/TradingViewWidget'

export default function BalticDryIndexChart() {
  return (
    <div id="baltic-dry-index">
      <ChartContainer
        title="バルチック海運指数（BDI）"
        showPeriodSelector={false}
        dataSource="Baltic Exchange"
        sourceUrl="https://www.balticexchange.com/en/data-services/WeeklyRoundup.html"
      >
        <div style={{ height: 500 }}>
          <TradingViewWidget
            symbol="BDI"
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
