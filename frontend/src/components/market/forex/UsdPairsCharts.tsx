import CftcPositioningChart from '../cot/CftcPositioningChart'
import LazyChart from '../../common/LazyChart'

export default function UsdPairsCharts() {
  return (
    <div className="country-chart-stack">
      <LazyChart id="cot-usdjpy"><CftcPositioningChart asset="usdjpy" assetLabel="米ドル/円" reportType="tff" compareId="cftc_usdjpy" handbookId="cot-usdjpy" /></LazyChart>
      <LazyChart id="cot-eurusd"><CftcPositioningChart asset="eurusd" assetLabel="ユーロ/米ドル" reportType="tff" compareId="cftc_eurusd" handbookId="cot-eurusd" /></LazyChart>
      <LazyChart id="cot-gbpusd"><CftcPositioningChart asset="gbpusd" assetLabel="英ポンド/米ドル" reportType="tff" compareId="cftc_gbpusd" handbookId="cot-gbpusd" /></LazyChart>
      <LazyChart id="cot-audusd"><CftcPositioningChart asset="audusd" assetLabel="豪ドル/米ドル" reportType="tff" compareId="cftc_audusd" handbookId="cot-audusd" /></LazyChart>
      <LazyChart id="cot-nzdusd"><CftcPositioningChart asset="nzdusd" assetLabel="NZドル/米ドル" reportType="tff" compareId="cftc_nzdusd" handbookId="cot-nzdusd" /></LazyChart>
      <LazyChart id="cot-usdcad"><CftcPositioningChart asset="usdcad" assetLabel="米ドル/カナダドル" reportType="tff" compareId="cftc_usdcad" handbookId="cot-usdcad" /></LazyChart>
      <LazyChart id="cot-usdchf"><CftcPositioningChart asset="usdchf" assetLabel="米ドル/スイスフラン" reportType="tff" compareId="cftc_usdchf" /></LazyChart>
    </div>
  )
}
