// TradingViewの銘柄シンボル変換マッピング
export const TRADING_VIEW_SYMBOL_MAP: Record<string, string> = {
  // 外国為替
  'USDJPY': 'OANDA:USDJPY',
  'EURJPY': 'OANDA:EURJPY',
  'GBPJPY': 'OANDA:GBPJPY',
  'AUDJPY': 'OANDA:AUDJPY',
  'NZDJPY': 'OANDA:NZDJPY',
  'CADJPY': 'OANDA:CADJPY',
  'CHFJPY': 'OANDA:CHFJPY',
  'EURUSD': 'OANDA:EURUSD',
  'GBPUSD': 'OANDA:GBPUSD',
  'AUDUSD': 'OANDA:AUDUSD',
  'NZDUSD': 'OANDA:NZDUSD',
  'USDCAD': 'OANDA:USDCAD',
  'USDCHF': 'OANDA:USDCHF',
  'AUDCAD': 'OANDA:AUDCAD',
  'AUDCHF': 'OANDA:AUDCHF',
  'AUDNZD': 'OANDA:AUDNZD',
  'CADCHF': 'OANDA:CADCHF',
  'EURAUD': 'OANDA:EURAUD',
  'EURCAD': 'OANDA:EURCAD',
  'EURCHF': 'OANDA:EURCHF',
  'EURGBP': 'OANDA:EURGBP',
  'EURNZD': 'OANDA:EURNZD',
  'GBPAUD': 'OANDA:GBPAUD',
  'GBPCAD': 'OANDA:GBPCAD',
  'GBPCHF': 'OANDA:GBPCHF',
  'GBPNZD': 'OANDA:GBPNZD',
  'NZDCAD': 'OANDA:NZDCAD',
  'NZDCHF': 'OANDA:NZDCHF',

  // 株式指数
  'S&P500': 'OANDA:SPX500USD',
  'ナスダック100': 'OANDA:NAS100USD',
  'SOX': 'NASDAQ:SOX',
  'TOPIX': 'IG:TOPIX',
  'VIX': 'CAPITALCOM:VIX',
  'ダウ平均': 'OANDA:US30USD',
  'ハンセン指数': 'CAPITALCOM:HK50',
  'ラッセル2000': 'OANDA:US2000USD',
  '日経平均': 'OANDA:JP225USD',
  'ドル建て日経平均': 'OANDA:JP225USD/OANDA:USDJPY',

  // 金利・債券
  'US10Y': 'PYTH:US10Y',
  'US30Y': 'PYTH:US30Y',
  'US02Y': 'PYTH:US02Y',

  // 通貨インデックス
  'USD_INDEX': 'TVC:DXY',           // ドルインデックス
  'EUR_INDEX': 'TVC:EXY',           // ユーロインデックス
  'GBP_INDEX': 'TVC:BXY',           // ポンドインデックス
  'JPY_INDEX': 'TVC:JXY',           // 円インデックス
  'AUD_INDEX': 'TVC:AXY',           // 豪ドルインデックス
  'CAD_INDEX': 'TVC:CXY',           // カナダドルインデックス
  'CHF_INDEX': 'TVC:SXY',           // スイスフランインデックス
  'NZD_INDEX': 'TVC:ZXY',           // NZドルインデックス

  // 商品
  'AUD建てゴールド': 'OANDA:XAUAUD',
  'CAD建てゴールド': 'OANDA:XAUCAD',
  'CHF建てゴールド': 'OANDA:XAUCHF',
  'EUR建てゴールド': 'OANDA:XAUEUR',
  'GBP建てゴールド': 'OANDA:XAUGBP',
  'NZD建てゴールド': 'OANDA:XAUNZD',
  'シルバー': 'OANDA:XAGUSD',
  'ドル建てゴールド': 'OANDA:XAUUSD',
  'ブレント原油': 'OANDA:BCOUSD',
  '円建てゴールド': 'OANDA:XAUJPY',
  '原油': 'OANDA:WTICOUSD',
  '天然ガス': 'OANDA:NATGASUSD',
  '銅': 'XCUUSD',
};

// TradingViewシンボルを取得する関数
export function getTradingViewSymbol(symbol: string): string {
  return TRADING_VIEW_SYMBOL_MAP[symbol] || `FX:${symbol}`;
}
