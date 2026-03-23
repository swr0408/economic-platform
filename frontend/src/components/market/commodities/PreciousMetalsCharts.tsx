import GoldEtfHoldingsChart from './GoldEtfHoldingsChart'
import GoldPremiumChart from './GoldPremiumChart'
import WgcGoldEtfChart from './WgcGoldEtfChart'
import SgeGoldChart from './SgeGoldChart'
import ChinaGoldEtfBalanceChart from './ChinaGoldEtfBalanceChart'
import CnGoldReservesChart from './CnGoldReservesChart'
import LbmaStockChart from './LbmaStockChart'
import SilverEtfHoldingsChart from './SilverEtfHoldingsChart'
import ComexGoldStockChart from './ComexGoldStockChart'
import ComexSilverStockChart from './ComexSilverStockChart'
import CftcPositioningChart from '../cot/CftcPositioningChart'
import LazyChart from '../../common/LazyChart'

export default function PreciousMetalsCharts() {
  return (
    <div className="country-chart-stack">
      <LazyChart id="gold-etf-holdings"><GoldEtfHoldingsChart /></LazyChart>
      <LazyChart id="wgc-gold-etf"><WgcGoldEtfChart /></LazyChart>
      <LazyChart id="gold-premium"><GoldPremiumChart /></LazyChart>
      <LazyChart id="sge-gold"><SgeGoldChart /></LazyChart>
      <LazyChart id="china-gold-etf-balance"><ChinaGoldEtfBalanceChart /></LazyChart>
      <LazyChart id="cn-gold-reserves"><CnGoldReservesChart /></LazyChart>
      <LazyChart id="lbma-stock"><LbmaStockChart /></LazyChart>
      <LazyChart id="comex-gold-inventory"><ComexGoldStockChart /></LazyChart>
      <LazyChart id="cot-gold"><CftcPositioningChart asset="gold" assetLabel="金（ゴールド）" reportType="disagg" compareId="cftc_gold" handbookId="cot-gold" /></LazyChart>
      <LazyChart id="silver-etf-holdings"><SilverEtfHoldingsChart /></LazyChart>
      <LazyChart id="comex-silver-inventory"><ComexSilverStockChart /></LazyChart>
      <LazyChart id="cot-silver"><CftcPositioningChart asset="silver" assetLabel="銀（シルバー）" reportType="disagg" compareId="cftc_silver" handbookId="cot-silver" /></LazyChart>
    </div>
  )
}
