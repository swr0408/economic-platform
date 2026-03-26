import { Typography } from 'antd'
import CftcPositioningChart from './CftcPositioningChart'

const { Title } = Typography

export default function CotCharts() {
  return (
    <>
      {/* 株式指数 */}
      <div id="cot-equities">
        <Title level={4} style={{ color: '#f1f5f9', marginBottom: 16 }}>株式指数</Title>
      </div>
      <div id="cot-sp500">
        <CftcPositioningChart asset="sp500" assetLabel="S&P 500" reportType="tff" compareId="cftc_sp500" />
      </div>
      <div id="cot-dow">
        <CftcPositioningChart asset="dow" assetLabel="ダウ平均" reportType="tff" compareId="cftc_dow" />
      </div>
      <div id="cot-nasdaq100">
        <CftcPositioningChart asset="nasdaq100" assetLabel="ナスダック100" reportType="tff" compareId="cftc_nasdaq100" />
      </div>
      <div id="cot-russell2000">
        <CftcPositioningChart asset="russell2000" assetLabel="ラッセル2000" reportType="tff" compareId="cftc_russell2000" />
      </div>
      <div id="cot-nikkei225">
        <CftcPositioningChart asset="nikkei225" assetLabel="日経225" reportType="tff" compareId="cftc_nikkei225" />
      </div>
      <div id="cot-vix">
        <CftcPositioningChart asset="vix" assetLabel="VIX" reportType="tff" compareId="cftc_vix" />
      </div>

      {/* 為替 */}
      <div id="cot-forex">
        <Title level={4} style={{ color: '#f1f5f9', marginTop: 32, marginBottom: 16 }}>為替</Title>
      </div>
      <div id="cot-usdjpy">
        <CftcPositioningChart asset="usdjpy" assetLabel="米ドル/円" reportType="tff" compareId="cftc_usdjpy" handbookId="cot-usdjpy" />
      </div>
      <div id="cot-eurusd">
        <CftcPositioningChart asset="eurusd" assetLabel="ユーロ/米ドル" reportType="tff" compareId="cftc_eurusd" handbookId="cot-eurusd" />
      </div>
      <div id="cot-gbpusd">
        <CftcPositioningChart asset="gbpusd" assetLabel="英ポンド/米ドル" reportType="tff" compareId="cftc_gbpusd" handbookId="cot-gbpusd" />
      </div>
      <div id="cot-audusd">
        <CftcPositioningChart asset="audusd" assetLabel="豪ドル/米ドル" reportType="tff" compareId="cftc_audusd" handbookId="cot-audusd" />
      </div>
      <div id="cot-nzdusd">
        <CftcPositioningChart asset="nzdusd" assetLabel="NZドル/米ドル" reportType="tff" compareId="cftc_nzdusd" handbookId="cot-nzdusd" />
      </div>
      <div id="cot-usdcad">
        <CftcPositioningChart asset="usdcad" assetLabel="米ドル/カナダドル" reportType="tff" compareId="cftc_usdcad" handbookId="cot-usdcad" />
      </div>
      <div id="cot-usdchf">
        <CftcPositioningChart asset="usdchf" assetLabel="米ドル/スイスフラン" reportType="tff" compareId="cftc_usdchf" />
      </div>
      <div id="cot-usd-index">
        <CftcPositioningChart asset="usd_index" assetLabel="ドルインデックス" reportType="tff" compareId="cftc_usd_index" />
      </div>
      <div id="cot-eurjpy">
        <CftcPositioningChart asset="eurjpy" assetLabel="ユーロ/円" reportType="tff" compareId="cftc_eurjpy" />
      </div>
      <div id="cot-eurgbp">
        <CftcPositioningChart asset="eurgbp" assetLabel="ユーロ/ポンド" reportType="tff" compareId="cftc_eurgbp" handbookId="cot-eurgbp" />
      </div>

      {/* 債券 */}
      <div id="cot-bonds">
        <Title level={4} style={{ color: '#f1f5f9', marginTop: 32, marginBottom: 16 }}>債券</Title>
      </div>
      <div id="cot-us02y">
        <CftcPositioningChart asset="us02y" assetLabel="米国2年債" reportType="tff" compareId="cftc_us02y" />
      </div>
      <div id="cot-us10y">
        <CftcPositioningChart asset="us10y" assetLabel="米国10年債" reportType="tff" compareId="cftc_us10y" />
      </div>
      <div id="cot-us30y">
        <CftcPositioningChart asset="us30y" assetLabel="米国30年債" reportType="tff" compareId="cftc_us30y" />
      </div>

      {/* コモディティ */}
      <div id="cot-commodities">
        <Title level={4} style={{ color: '#f1f5f9', marginTop: 32, marginBottom: 16 }}>コモディティ</Title>
      </div>
      <div id="cot-gold">
        <CftcPositioningChart asset="gold" assetLabel="金（ゴールド）" reportType="disagg" compareId="cftc_gold" handbookId="cot-gold" />
      </div>
      <div id="cot-silver">
        <CftcPositioningChart asset="silver" assetLabel="銀（シルバー）" reportType="disagg" compareId="cftc_silver" handbookId="cot-silver" />
      </div>
      <div id="cot-copper">
        <CftcPositioningChart asset="copper" assetLabel="銅（カッパー）" reportType="disagg" compareId="cftc_copper" />
      </div>

      {/* エネルギー */}
      <div id="cot-energy">
        <Title level={4} style={{ color: '#f1f5f9', marginTop: 32, marginBottom: 16 }}>エネルギー</Title>
      </div>
      <div id="cot-crude-oil">
        <CftcPositioningChart asset="crude_oil" assetLabel="原油（WTI）" reportType="disagg" compareId="cftc_crude_oil" handbookId="cot-crude-oil" />
      </div>
      <div id="cot-brent">
        <CftcPositioningChart asset="brent" assetLabel="ブレント原油" reportType="disagg" compareId="cftc_brent" />
      </div>
      <div id="cot-natural-gas">
        <CftcPositioningChart asset="natural_gas" assetLabel="天然ガス" reportType="disagg" compareId="cftc_natural_gas" handbookId="cot-natural-gas" />
      </div>
    </>
  )
}
